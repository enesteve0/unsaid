"""HTTP API and static web app.

Public and free: no sign-up. A random session cookie isolates each visitor's runs. An access code (shared with
judges in the Devpost testing instructions) unlocks a lane with its own capacity and budget.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gates, media
from .asr import SpeechRecognizer
from .config import Settings, get_settings
from .jobs import RunQueue
from .pipeline import STAGES, RunOptions
from .schemas import Interval
from .store import Store
from .tf_client import TokenFactory

SESSION_COOKIE = "unsaid_sid"
JUDGE_COOKIE = "unsaid_judge"
RUN_FILES = {
    "descriptions.vtt",
    "captions.vtt",
    "captions.srt",
    "transcript.html",
    "markers.fcpxml",
    "result.json",
}
VIDEO_TYPES = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}


class JudgeCode(BaseModel):
    code: str


class CueEdit(BaseModel):
    text: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.provider != "tokenfactory" and not settings.allow_non_tokenfactory:
        raise RuntimeError(
            "The web app only runs against Nebius Token Factory (set ALLOW_NON_TOKENFACTORY=1 to override locally)."
        )

    app = FastAPI(title="Unsaid", docs_url="/api/docs", openapi_url="/api/openapi.json")
    store = Store(settings.data_dir)
    tf = TokenFactory(settings)
    asr = SpeechRecognizer(Path("models"))
    queue = RunQueue(settings, tf, asr, store)
    samples_dir = settings.samples_dir.resolve()
    model_status: dict[str, Any] = {"checked": 0, "models": {}}

    async def refresh_models() -> None:
        with contextlib.suppress(Exception):
            listed = await tf.list_models()
            model_status["models"] = {
                m["id"]: m.get("status", "active") for m in listed if m["id"].startswith("nvidia/")
            }
            model_status["checked"] = time.time()

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.get_running_loop().run_in_executor(None, asr.warm_up)
        await refresh_models()

        async def housekeeping() -> None:
            while True:
                await asyncio.sleep(6 * 3600)
                await refresh_models()
                store.purge_uploads()

        asyncio.create_task(housekeeping())

    @app.middleware("http")
    async def session_cookie(request: Request, call_next):
        sid = request.cookies.get(SESSION_COOKIE) or secrets.token_urlsafe(16)
        request.state.sid = sid
        response = await call_next(request)
        if SESSION_COOKIE not in request.cookies:
            response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 60)
        return response

    def lane_of(request: Request) -> str:
        code = request.cookies.get(JUDGE_COOKIE, "")
        return (
            "judge" if settings.judge_code and secrets.compare_digest(code, settings.judge_code) else "public"
        )

    def client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        return (
            forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
        )

    # ---- status ----------------------------------------------------------------------------------------------

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "provider": settings.provider,
            "demo_mode": "recorded"
            if (settings.demo_mode == "recorded" or queue.credit_exhausted)
            else "live",
            "models": model_status["models"],
            "models_checked": model_status["checked"],
            "stages": [{"key": k, "label": label, "detail": d} for k, label, d in STAGES],
        }

    @app.post("/api/judge")
    async def judge(body: JudgeCode, response: Response) -> dict[str, Any]:
        if not settings.judge_code or not secrets.compare_digest(body.code.strip(), settings.judge_code):
            raise HTTPException(403, "That access code is not valid.")
        response.set_cookie(
            JUDGE_COOKIE, body.code.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 60
        )
        return {"lane": "judge"}

    # ---- samples (precomputed, instant) --------------------------------------------------------------------------

    def sample_manifest() -> list[dict[str, Any]]:
        path = samples_dir / "manifest.json"
        return json.loads(path.read_text()) if path.exists() else []

    @app.get("/api/samples")
    async def samples() -> list[dict[str, Any]]:
        return [s for s in sample_manifest() if (samples_dir / s["id"] / "result.json").exists()]

    @app.get("/api/samples/{sample_id}/result")
    async def sample_result(sample_id: str) -> JSONResponse:
        path = samples_dir / Path(sample_id).name / "result.json"
        if not path.exists():
            raise HTTPException(404, "No such sample")
        return JSONResponse(json.loads(path.read_text()))

    # ---- live runs -------------------------------------------------------------------------------------------

    @app.post("/api/runs")
    async def create_run(
        request: Request,
        file: UploadFile | None = File(None),
        sample_id: str | None = Form(None),
        title: str = Form("My lecture"),
        source_url: str | None = Form(None),
    ) -> dict[str, Any]:
        if settings.demo_mode == "recorded" or queue.credit_exhausted:
            raise HTTPException(
                503, "Live describing is paused right now. The recorded examples show real runs."
            )
        lane, sid, ip = lane_of(request), request.state.sid, client_ip(request)
        if lane == "public":
            if (
                store.count_recent(session=sid, seconds=600) >= 3
                or store.count_recent(ip=ip, seconds=3600) >= 5
            ):
                raise HTTPException(
                    429,
                    "You have reached the limit of live runs for now. Try again in a few minutes, or explore the examples.",
                )
        daily_cap = settings.judge_daily_usd if lane == "judge" else settings.public_daily_usd
        if store.spend_today(lane) >= daily_cap or store.spend_this_month() >= settings.monthly_ceiling_usd:
            raise HTTPException(
                429, "Today's budget for live runs is used up. The examples are always available."
            )

        run_id = uuid.uuid4().hex[:12]
        workdir = store.run_dir(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
        if file is not None:
            suffix = Path(file.filename or "video.mp4").suffix.lower()
            if suffix not in VIDEO_TYPES:
                raise HTTPException(415, "Please upload an MP4, MOV, WebM or MKV video.")
            target = workdir / f"source{suffix}"
            size = 0
            with target.open("wb") as out:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > settings.max_upload_mb * 1024 * 1024:
                        raise HTTPException(413, f"Videos up to {settings.max_upload_mb} MB, please.")
                    out.write(chunk)
        elif sample_id:
            source = samples_dir / Path(sample_id).name / "video.mp4"
            if not source.exists():
                raise HTTPException(404, "No such sample")
            target = source
            title = next((s["title"] for s in sample_manifest() if s["id"] == sample_id), title)
        else:
            raise HTTPException(400, "Upload a video or choose a sample.")

        try:
            info = await media.probe(target)
        except Exception as exc:
            raise HTTPException(415, "That file does not look like a playable video.") from exc
        if info.duration > settings.max_upload_seconds + 1:
            raise HTTPException(
                413,
                f"Live runs take clips up to {int(settings.max_upload_seconds // 60)} minutes. Trim it, or use the overnight backlog.",
            )

        store.create_run(run_id, sid, lane, title[:120], ip)
        queue.submit(
            run_id, target, RunOptions(title=title[:120], source_url=source_url or None, session_id=sid), lane
        )
        return {"run_id": run_id, "position": queue.position(run_id), "lane": lane}

    def own_run(request: Request, run_id: str) -> dict[str, Any]:
        run = store.get_run(run_id)
        if run is None or run["session"] != request.state.sid:
            raise HTTPException(404, "No such run")
        return run

    @app.get("/api/runs")
    async def my_runs(request: Request) -> list[dict[str, Any]]:
        return [
            {k: r[k] for k in ("id", "title", "status", "created", "cost_usd")}
            for r in store.runs_for_session(request.state.sid)
        ]

    @app.get("/api/runs/{run_id}")
    async def run_status(request: Request, run_id: str) -> dict[str, Any]:
        run = own_run(request, run_id)
        return {
            **{k: run[k] for k in ("id", "title", "status", "created", "finished", "cost_usd", "error")},
            "position": queue.position(run_id),
        }

    @app.get("/api/runs/{run_id}/events")
    async def run_events(request: Request, run_id: str) -> StreamingResponse:
        own_run(request, run_id)

        async def stream():
            async for event in queue.events(run_id):
                if event.get("type") == "heartbeat":
                    yield ": keep-alive\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(request: Request, run_id: str) -> dict[str, Any]:
        own_run(request, run_id)
        return {"cancelled": queue.cancel(run_id)}

    @app.get("/api/runs/{run_id}/result")
    async def run_result(request: Request, run_id: str) -> JSONResponse:
        own_run(request, run_id)
        result = store.result(run_id)
        if result is None:
            raise HTTPException(404, "Not finished yet")
        return JSONResponse(result)

    @app.get("/api/runs/{run_id}/files/{name}")
    async def run_file(request: Request, run_id: str, name: str) -> FileResponse:
        own_run(request, run_id)
        if name not in RUN_FILES and not name.startswith("source."):
            raise HTTPException(404, "No such file")
        path = store.run_dir(run_id) / name
        if not path.exists():
            raise HTTPException(404, "No such file")
        return FileResponse(path, filename=name if name != "transcript.html" else None)

    @app.patch("/api/runs/{run_id}/cues/{cue_id}")
    async def edit_cue(request: Request, run_id: str, cue_id: str, body: CueEdit) -> dict[str, Any]:
        """A describer's edit is re-checked by the same code gates before it is saved."""
        own_run(request, run_id)
        result = store.result(run_id)
        if result is None:
            raise HTTPException(404, "Not finished yet")
        cue = next((c for c in result["cues"] if c["id"] == cue_id), None)
        if cue is None:
            raise HTTPException(404, "No such cue")
        gap = next((g for g in result["gaps"] if g["id"] == cue.get("gap_id")), None)
        speech = [Interval(**s) for s in result["speech"]]
        screen = [t for facts in result["observations"].values() for t in facts["on_screen_text"]]
        spoken = " ".join(w["text"] for w in result["transcript"])
        allowed = set().union(*(gates.numbers_in(t) for t in [*screen, spoken]))
        vocab = gates.vocabulary(
            screen, [spoken], result["context"]["names"], [r["name"] for r in result["bible"]["registry"]]
        )
        report = gates.check_cue(
            body.text,
            cue["start"],
            gap["end"] if gap else cue["start"] + 60,
            speech=speech,
            allowed_numbers=allowed,
            known_vocabulary=vocab,
            words_per_second=settings.words_per_second,
            guard=settings.speech_guard_seconds,
            lead=settings.speech_lead_seconds,
            extended=cue["extended"],
        )
        if report.passed:
            cue.update(
                text=body.text,
                gate_failures=[],
                gate_warnings=report.warnings,
                tier="auto" if not report.warnings else "review",
                edited=True,
            )
            (store.run_dir(run_id) / "result.json").write_text(json.dumps(result, indent=1))
        return {
            "passed": report.passed,
            "failures": report.failures,
            "warnings": report.warnings,
            "estimated_seconds": round(report.estimated_seconds, 2),
        }

    # ---- evaluation report -------------------------------------------------------------------------------------

    @app.get("/api/eval")
    async def eval_report() -> JSONResponse:
        path = Path("eval/report.json")
        return JSONResponse(json.loads(path.read_text()) if path.exists() else {"available": False})

    # ---- static files ---------------------------------------------------------------------------------------------

    if samples_dir.exists():
        app.mount("/media/samples", StaticFiles(directory=samples_dir), name="samples")
    web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa(path: str) -> FileResponse:
            candidate = web_dist / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(web_dist / "index.html")

    return app


app = None


def main() -> None:
    import uvicorn

    uvicorn.run(
        "unsaid.api:create_app",
        factory=True,
        host="0.0.0.0",
        port=8080,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
