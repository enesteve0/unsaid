"""HTTP API and static web app.

Public and free: no sign-up. A random session cookie isolates each visitor's runs. An access code (shared with
judges in the Devpost testing instructions) unlocks a lane with its own budget and a run slot public runs never use.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import export, gates, media
from .asr import SpeechRecognizer
from .config import Settings, get_settings
from .jobs import RunQueue
from .pipeline import STAGES, RunOptions
from .schemas import Cue, Interval, Word
from .store import Store
from .tf_client import TokenFactory

log = logging.getLogger(__name__)

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
FORM_OVERHEAD_BYTES = 1 << 20  # multipart boundaries and the other form fields
JUDGE_ATTEMPTS_PER_HOUR = 10


class JudgeCode(BaseModel):
    code: str


class CueEdit(BaseModel):
    text: str


class UploadLimit:
    """Refuse an upload by its declared size before the body is read (the form parser would spool all of it)."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == "/api/runs":
            declared = dict(scope["headers"]).get(b"content-length", b"0")
            if declared.isdigit() and int(declared) > self.max_bytes:
                response = JSONResponse(
                    {"detail": f"Videos up to {self.max_bytes // (1 << 20) - 1} MB, please."}, status_code=413
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def client_ip(request: Request) -> str:
    """The visitor's address as the hosting proxy saw it.

    On Fly.io (FLY_APP_NAME is set) the proxy writes Fly-Client-IP itself; anywhere else that header is the client's
    word and is ignored. Otherwise the last X-Forwarded-For entry is the one the nearest proxy appended; earlier
    entries come from the client and can be forged.
    """
    fly = request.headers.get("fly-client-ip", "").strip() if os.environ.get("FLY_APP_NAME") else ""
    if fly:
        return fly
    forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if forwarded:
        return forwarded[-1]
    return request.client.host if request.client else ""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.provider != "tokenfactory" and not settings.allow_non_tokenfactory:
        raise RuntimeError(
            "The web app only runs against Nebius Token Factory (set ALLOW_NON_TOKENFACTORY=1 to override locally)."
        )

    app = FastAPI(title="Unsaid", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(UploadLimit, max_bytes=settings.max_upload_mb * (1 << 20) + FORM_OVERHEAD_BYTES)
    store = Store(settings.data_dir)
    store.fail_orphans()
    tf = TokenFactory(settings)
    asr = SpeechRecognizer(Path("models"))
    queue = RunQueue(settings, tf, asr, store)
    samples_dir = settings.samples_dir.resolve()
    model_status: dict[str, Any] = {"checked": 0, "models": {}}

    judge_attempts: dict[str, deque[float]] = {}
    judge_token = (
        hmac.new(settings.judge_code.encode(), b"unsaid judge lane", hashlib.sha256).hexdigest()
        if settings.judge_code
        else ""
    )

    async def refresh_models() -> None:
        try:
            listed = await tf.list_models()
        except Exception as exc:
            log.warning("model list unavailable: %s", exc)
            return
        model_status["models"] = {
            m["id"]: m.get("status", "active") for m in listed if m["id"].startswith("nvidia/")
        }
        model_status["checked"] = time.time()

    def purge() -> None:
        try:
            removed = store.purge_media(settings.keep_media_hours * 3600)
            if removed:
                log.info("deleted %d media files older than %.0f h", removed, settings.keep_media_hours)
        except Exception:
            log.exception("media purge failed")

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.get_running_loop().run_in_executor(None, asr.warm_up)
        purge()
        await refresh_models()

        async def housekeeping() -> None:
            while True:
                await asyncio.sleep(3600)
                purge()
                await refresh_models()

        app.state.housekeeping = asyncio.create_task(housekeeping())

    @app.middleware("http")
    async def session_cookie(request: Request, call_next):
        sid = request.cookies.get(SESSION_COOKIE) or secrets.token_urlsafe(16)
        request.state.sid = sid
        response = await call_next(request)
        if SESSION_COOKIE not in request.cookies:
            response.set_cookie(
                SESSION_COOKIE,
                sid,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
                max_age=60 * 60 * 24 * 60,
            )
        return response

    def live_status(lane: str) -> str:
        """'live', or why a lane serves only the recorded examples: paused, ended or judges_only."""
        if settings.demo_mode == "recorded" or queue.paused_for(lane):
            return "paused"
        if settings.live_until and time.strftime("%Y-%m-%d", time.gmtime()) > settings.live_until:
            return "ended"
        if lane != "judge" and not settings.public_live:
            return "judges_only"
        return "live"

    def lane_of(request: Request) -> str:
        token = request.cookies.get(JUDGE_COOKIE, "")
        return "judge" if judge_token and secrets.compare_digest(token, judge_token) else "public"

    # ---- status ----------------------------------------------------------------------------------------------

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        status = live_status(lane_of(request))
        return {
            "ok": True,
            "provider": settings.provider,
            "host": settings.host,
            "demo_mode": "live" if status == "live" else "recorded",
            "live_status": status,
            "models": model_status["models"],
            "models_checked": model_status["checked"],
            "live_runs": queue.active(),
            "stages": [{"key": k, "label": label, "detail": d} for k, label, d in STAGES],
        }

    @app.post("/api/judge")
    async def judge(body: JudgeCode, request: Request, response: Response) -> dict[str, Any]:
        if len(judge_attempts) > 10_000:  # forged or many addresses: forget everyone's old attempts
            for ip in [k for k, v in judge_attempts.items() if not v or v[-1] < time.time() - 3600]:
                del judge_attempts[ip]
        attempts = judge_attempts.setdefault(client_ip(request), deque())
        while attempts and attempts[0] < time.time() - 3600:
            attempts.popleft()
        if len(attempts) >= JUDGE_ATTEMPTS_PER_HOUR:
            raise HTTPException(429, "Too many attempts. Try again later.")
        attempts.append(time.time())
        if not settings.judge_code or not secrets.compare_digest(body.code.strip(), settings.judge_code):
            raise HTTPException(403, "That access code is not valid.")
        response.set_cookie(
            JUDGE_COOKIE,
            judge_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=60 * 60 * 24 * 60,
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
        file: Annotated[UploadFile | None, File()] = None,
        sample_id: Annotated[str | None, Form()] = None,
        title: Annotated[str, Form()] = "My lecture",
        source_url: Annotated[str | None, Form()] = None,
    ) -> dict[str, Any]:
        status = live_status(lane_of(request))
        if status != "live":
            raise HTTPException(
                503,
                {
                    "judges_only": "During the hackathon, live describing is open to judges (access code). "
                    "The examples are real recorded runs.",
                    "ended": "Live describing has ended for this demo. The examples are real recorded runs.",
                }.get(status, "Live describing is paused right now. The recorded examples show real runs."),
            )
        if file is None and not sample_id:
            raise HTTPException(400, "Upload a video or choose a sample.")
        suffix = Path(file.filename or "video.mp4").suffix.lower() if file is not None else ".mp4"
        if suffix not in VIDEO_TYPES:
            raise HTTPException(415, "Please upload an MP4, MOV, WebM or MKV video.")
        sample = samples_dir / Path(sample_id).name / "video.mp4" if file is None and sample_id else None
        if sample is not None and not sample.exists():
            raise HTTPException(404, "No such sample")

        lane, sid, ip = lane_of(request), request.state.sid, client_ip(request)
        if lane == "public":
            if store.count_pending(session=sid, ip=ip) >= 1:
                raise HTTPException(
                    429, "You already have a lecture being described. It will finish in a few minutes."
                )
            if (
                store.count_recent(session=sid, seconds=600) >= 3
                or store.count_recent(ip=ip, seconds=3600) >= 5
            ):
                raise HTTPException(
                    429,
                    "You have reached the limit of live runs for now. Try again in a few minutes, or explore the examples.",
                )
        if queue.over_budget(lane, reserve_new=True):
            raise HTTPException(
                429, "Live runs are at today's budget right now. The examples are always available."
            )
        if sample is not None:
            title = next((s["title"] for s in sample_manifest() if s["id"] == sample_id), title)

        # The run is registered before any await, so concurrent requests see it in the checks above.
        run_id = uuid.uuid4().hex[:12]
        store.create_run(run_id, sid, lane, title[:120], ip)
        workdir = store.run_dir(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
        target = workdir / f"source{suffix}"
        try:
            if file is not None:
                size = 0
                with target.open("wb") as out:
                    while chunk := await file.read(1 << 20):
                        size += len(chunk)
                        if size > settings.max_upload_mb * 1024 * 1024:
                            raise HTTPException(413, f"Videos up to {settings.max_upload_mb} MB, please.")
                        out.write(chunk)
            else:
                await asyncio.to_thread(shutil.copyfile, sample, target)
            try:
                info = await media.probe(target)
            except Exception as exc:
                raise HTTPException(415, "That file does not look like a playable video.") from exc
            if info.duration > settings.max_upload_seconds + 1:
                raise HTTPException(
                    413,
                    f"Live runs take clips up to {int(settings.max_upload_seconds // 60)} minutes. Trim it, or use the overnight backlog.",
                )
        except BaseException:
            store.delete_run(run_id)
            shutil.rmtree(workdir, ignore_errors=True)
            raise

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
        run = own_run(request, run_id)

        async def stream():
            if not queue.knows(run_id):  # finished long ago, or before a restart: report how it ended
                status = run["status"] if run["status"] in ("done", "cancelled") else "failed"
                yield f"data: {json.dumps({'type': 'finished', 'status': status})}\n\n"
                return
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

    @app.get("/api/runs/{run_id}/video")
    async def run_video(request: Request, run_id: str) -> FileResponse:
        own_run(request, run_id)
        source = next(iter(sorted(store.run_dir(run_id).glob("source.*"))), None)
        if source is None:
            raise HTTPException(404, "The uploaded video has been deleted (uploads are kept for 24 hours).")
        return FileResponse(source)

    @app.patch("/api/runs/{run_id}/cues/{cue_id}")
    async def edit_cue(request: Request, run_id: str, cue_id: str, body: CueEdit) -> dict[str, Any]:
        """A describer's edit is re-checked by the same code gates before it is saved, and the tracks are rebuilt."""
        own_run(request, run_id)
        if len(body.text) > 600:
            raise HTTPException(413, "A description has at most 600 characters.")
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
        allowed = gates.numbers_seen(result["observations"].values(), spoken)
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
            workdir = store.run_dir(run_id)
            (workdir / "result.json").write_text(json.dumps(result, indent=1))
            cues = [Cue(**c) for c in result["cues"]]
            words = [Word(**w) for w in result["transcript"]]
            video = result["video"]
            (workdir / "descriptions.vtt").write_text(export.descriptions_vtt(cues))
            (workdir / "transcript.html").write_text(export.transcript_html(words, cues, result["title"]))
            (workdir / "markers.fcpxml").write_text(
                export.fcpxml_markers(
                    cues,
                    name=result["title"],
                    duration=video["duration"],
                    fps=video["fps"],
                    width=video["width"],
                    height=video["height"],
                )
            )
        return {
            "passed": report.passed,
            "failures": report.failures,
            "warnings": report.warnings,
            "estimated_seconds": round(report.estimated_seconds, 2),
        }

    # ---- overnight backlog (Nebius Serverless Job output) -------------------------------------------------------

    @app.get("/api/backlog")
    async def backlog() -> JSONResponse:
        path = settings.backlog_dir / "digest.json"
        return JSONResponse(
            {"available": True, **json.loads(path.read_text())} if path.exists() else {"available": False}
        )

    # ---- evaluation report -------------------------------------------------------------------------------------

    @app.get("/api/eval")
    async def eval_report() -> JSONResponse:
        path = settings.eval_report
        return JSONResponse(json.loads(path.read_text()) if path.exists() else {"available": False})

    # ---- static files ---------------------------------------------------------------------------------------------

    if samples_dir.exists():
        app.mount("/media/samples", StaticFiles(directory=samples_dir), name="samples")
    web_dist = (settings.web_dist or Path(__file__).resolve().parent.parent.parent / "web" / "dist").resolve()
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.api_route("/{path:path}", methods=["GET", "HEAD"])
        async def spa(path: str) -> FileResponse:
            candidate = (web_dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(web_dist):
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
