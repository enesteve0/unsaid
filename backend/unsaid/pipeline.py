"""End to end: a lecture video in, audio description out.

Listen → Segment → Watch → Resolve → Context → Understand → Write & fit → Check → Deliver.
Every stage reports progress, can be cancelled between stages, and writes its Token Factory calls to the ledger.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import export, gates, media
from .asr import SpeechRecognizer, Transcript
from .bible import build_bible
from .config import Settings
from .context import ContextResult, gather_context
from .correct import correct_unsupported
from .cues import separate_pauses, verified_names, write_all
from .deixis import find_pointing_moments
from .ledger import Ledger
from .perceive import Observation, perceive
from .resolve import resolve_moments
from .schemas import Cue, Interval, PointerResolution, PointingMoment, SegmentFacts
from .segments import attach_moments, build_segments, find_gaps
from .tf_client import AuthFailure, CreditExhausted, TokenFactory
from .tips import lecturer_tips
from .verify import verify_all

log = logging.getLogger(__name__)

STAGES = [
    ("listen", "Listen", "NVIDIA Parakeet speech recognition on CPU"),
    ("segment", "Segment", "slide changes, silences and pointing phrases"),
    ("watch", "Watch", "Nemotron 3.5 Super VL reads every segment"),
    ("resolve", "Resolve", "Nemotron 3 Nano (3.5 Lightning on the API catalog): what does each 'this' point at?"),
    ("context", "Context", "Tavily: names from the source page and slide citations"),
    ("understand", "Understand", "Nemotron 3 Ultra plans what is unsaid and where it fits"),
    ("write", "Write & fit", "code gates check Ultra's drafts; Nemotron 3.5 Lightning repairs failures"),
    (
        "check",
        "Check",
        "Nemotron 3.5 Super VL checks every claim against the frames; Lightning corrects what it flags",
    ),
    ("deliver", "Deliver", "tracks, transcript, editor markers and lecturer tips"),
]

ProgressFn = Callable[[dict[str, Any]], Awaitable[None] | None]


class Cancelled(Exception):
    pass


class PerceptionFailed(RuntimeError):
    """Most of the video could not be read; reporting "nothing to describe" would be false."""


@dataclass
class RunOptions:
    title: str = "Lecture"
    source_url: str | None = None
    session_id: str = "local"


async def _emit(progress: ProgressFn | None, event: dict[str, Any]) -> None:
    if progress is None:
        return
    out = progress(event)
    if inspect.isawaitable(out):
        await out


def compute_metrics(
    cues: list[Cue],
    speech: list[Interval],
    moments: list[PointingMoment],
    resolutions: dict[str, PointerResolution],
    duration: float,
) -> dict[str, Any]:
    inline = [c for c in cues if not c.extended and c.published]
    talk_over = 0.0
    for c in inline:
        for s in speech:
            talk_over += max(0.0, min(c.end, s.end) - max(c.start, s.start))
    visual_moments = [m for m in moments if m.id in resolutions and resolutions[m.id].refers_to_visual]
    covered = {mid for c in cues if c.published for mid in c.moment_ids}
    tiers = {t: sum(1 for c in cues if c.tier == t) for t in ("auto", "review", "never")}
    failures: dict[str, int] = {}
    for c in cues:
        for f in c.gate_failures:
            key = f.split(":")[0]
            failures[key] = failures.get(key, 0) + 1
    return {
        "duration_seconds": round(duration, 2),
        "cues": len(cues),
        "inline_cues": len(inline),
        "extended_cues": sum(1 for c in cues if c.extended),
        "tiers": tiers,
        "talk_over_seconds": round(talk_over, 3),
        "repairs": sum(c.repairs for c in cues),
        "gate_failures_after_repair": failures,
        "pointing_moments": len(moments),
        "pointing_moments_visual": len(visual_moments),
        "pointing_moments_covered": sum(1 for m in visual_moments if m.id in covered),
    }


async def run_pipeline(
    video: Path,
    workdir: Path,
    *,
    settings: Settings,
    tf: TokenFactory,
    asr: SpeechRecognizer,
    options: RunOptions | None = None,
    progress: ProgressFn | None = None,
    cancel: asyncio.Event | None = None,
    ledger: Ledger | None = None,
) -> dict[str, Any]:
    """`ledger` may be passed in so a caller can charge the calls of a run that fails or is stopped."""
    options = options or RunOptions()
    cancel = cancel or asyncio.Event()
    workdir.mkdir(parents=True, exist_ok=True)
    ledger = ledger if ledger is not None else Ledger()
    timings: dict[str, float] = {}
    started = time.perf_counter()

    async def stage(key: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        if cancel.is_set():
            raise Cancelled(key)
        label = next(s for s in STAGES if s[0] == key)
        await _emit(
            progress,
            {"type": "stage", "stage": key, "label": label[1], "status": "start", "detail": label[2]},
        )
        t0 = time.perf_counter()
        calls_before = len(ledger.entries)
        value = await fn()
        timings[key] = round(time.perf_counter() - t0, 2)
        new = [e.to_dict() for e in ledger.entries[calls_before:]]
        await _emit(
            progress,
            {
                "type": "stage",
                "stage": key,
                "label": label[1],
                "status": "done",
                "seconds": timings[key],
                "calls": new,
                "total_usd": round(ledger.total_cost, 6),
            },
        )
        return value

    info = await media.probe(video)

    async def listen() -> Transcript:
        if not info.has_audio:
            return Transcript(words=[], speech=[], text="")
        wav = await media.extract_audio(video, workdir / "audio.wav")
        return await asr.transcribe(wav)

    transcript: Transcript = await stage("listen", listen)

    async def segment():
        changes = await media.detect_changes(video, threshold=0.25)
        segs = build_segments(changes, info.duration, min_len=4.0, max_len=45.0)
        moments = find_pointing_moments(transcript.words)
        attach_moments(moments, segs)
        gaps = find_gaps(transcript.speech, info.duration, settings.min_gap_seconds)
        return segs, moments, gaps

    segments, moments, gaps = await stage("segment", segment)

    failures: list[dict[str, str]] = []

    async def watch_one(seg) -> Observation:
        try:
            return await perceive(tf, ledger, video, seg, transcript.words, workdir)
        except (CreditExhausted, AuthFailure):
            raise
        except Exception as exc:  # one unreadable segment must not sink the whole lecture
            failures.append(
                {"stage": "watch", "segment": seg.id, "error": f"{type(exc).__name__}: {exc}"[:300]}
            )
            empty = SegmentFacts(on_screen_text=[], visuals=[], events=[], setting="", people=[])
            return Observation(segment=seg, facts=empty, stills=[])

    async def watch() -> dict[str, Observation]:
        results = await asyncio.gather(*(watch_one(s) for s in segments))
        return {o.segment.id: o for o in results}

    observations: dict[str, Observation] = await stage("watch", watch)
    if segments and len(failures) * 2 > len(segments):
        raise PerceptionFailed(
            f"could not read {len(failures)} of {len(segments)} segments of the video; try again later"
        )

    resolutions: dict[str, PointerResolution] = await stage(
        "resolve", lambda: resolve_moments(tf, ledger, moments, observations, transcript.words)
    )

    async def context() -> ContextResult:
        if not settings.tavily_api_key:
            return ContextResult()
        screen = [t for o in observations.values() for t in o.facts.on_screen_text]
        return await gather_context(
            tf,
            ledger,
            settings.tavily_api_key,
            source_url=options.source_url,
            on_screen_texts=screen,
            session_id=options.session_id,
        )

    ctx: ContextResult = await stage("context", context)

    bible = await stage(
        "understand",
        lambda: build_bible(
            tf,
            ledger,
            settings,
            duration=info.duration,
            words=transcript.words,
            observations=list(observations.values()),
            moments=moments,
            resolutions=resolutions,
            gaps=gaps,
            context_names=ctx.names,
            # Ultra plans for minutes: a running token count shows the browser it is working, not stuck.
            on_stream=lambda n: _emit(progress, {"type": "tick", "stage": "understand", "tokens": n}),
        ),
    )

    moment_times = {m.id: m.t for m in moments}
    cues: list[Cue] = await stage(
        "write",
        lambda: write_all(
            tf,
            ledger,
            settings,
            bible=bible,
            gaps=gaps,
            speech=transcript.speech,
            observations=observations,
            words=transcript.words,
            context_names=ctx.names,
            moment_times=moment_times,
        ),
    )
    for cue in cues:
        # Credit Tavily only where a description actually uses a name it supplied.
        if any(gates.mentions(name, cue.text) for name in ctx.names):
            cue.sources = ctx.sources

    allowed_names = verified_names(bible, observations, transcript.words, ctx.names)
    check_counts: dict[str, int] = {}

    async def check() -> None:
        await verify_all(tf, ledger, video, cues, bible, info.duration, allowed_names, workdir, moment_times)
        check_counts["flagged"] = sum(
            1 for c in cues if c.verification is not None and not c.verification.supported
        )
        check_counts["corrected"] = await correct_unsupported(
            tf,
            ledger,
            settings,
            video=video,
            cues=cues,
            bible=bible,
            gaps=gaps,
            speech=transcript.speech,
            observations=observations,
            words=transcript.words,
            context_names=ctx.names,
            duration=info.duration,
            workdir=workdir,
            moment_times=moment_times,
        )
        separate_pauses(cues)  # a correction can lengthen a description that a pause was moved behind
        cues.sort(key=lambda c: c.start)

    await stage("check", check)

    async def deliver():
        (workdir / "descriptions.vtt").write_text(export.descriptions_vtt(cues))
        (workdir / "captions.vtt").write_text(export.captions_vtt(transcript.words))
        (workdir / "captions.srt").write_text(export.captions_srt(transcript.words))
        (workdir / "transcript.html").write_text(
            export.transcript_html(transcript.words, cues, options.title)
        )
        (workdir / "markers.fcpxml").write_text(
            export.fcpxml_markers(
                cues,
                name=options.title,
                duration=info.duration,
                fps=info.fps,
                width=info.width,
                height=info.height,
            )
        )
        # Tips are a bonus: the tracks above are written first, and a failed tips call costs only the tips.
        try:
            return await lecturer_tips(tf, ledger, moments, resolutions, bible, cues)
        except (CreditExhausted, AuthFailure):
            raise
        except Exception as exc:
            log.warning("lecturer tips skipped: %s: %s", type(exc).__name__, exc)
            return []

    tips = await stage("deliver", deliver)

    metrics = compute_metrics(cues, transcript.speech, moments, resolutions, info.duration)
    metrics["flagged_by_check"] = check_counts.get("flagged", 0)
    metrics["corrected_after_check"] = check_counts.get("corrected", 0)
    accepted = metrics["tiers"]["auto"]
    result = {
        "title": options.title,
        "video": {"duration": info.duration, "width": info.width, "height": info.height, "fps": info.fps},
        "transcript": [w.model_dump() for w in transcript.words],
        "speech": [s.model_dump() for s in transcript.speech],
        "gaps": [g.model_dump() for g in gaps],
        "segments": [s.model_dump() for s in segments],
        "moments": [m.model_dump() for m in moments],
        "resolutions": {k: v.model_dump() for k, v in resolutions.items()},
        "observations": {k: o.facts.model_dump() for k, o in observations.items()},
        "context": {"names": ctx.names, "sources": [s.model_dump() for s in ctx.sources]},
        "bible": bible.model_dump(),
        "cues": [c.model_dump() for c in cues],
        "tips": [t.model_dump() for t in tips],
        "metrics": metrics,
        "ledger": {
            "summary": ledger.summary(video_minutes=info.duration / 60, accepted_cues=accepted or None),
            "calls": [e.to_dict() for e in ledger.entries],
        },
        "timings": {**timings, "total": round(time.perf_counter() - started, 2)},
        "failures": failures,
        "provider": settings.provider,
    }
    (workdir / "result.json").write_text(json.dumps(result, indent=1))
    await _emit(progress, {"type": "done", "metrics": metrics, "total_usd": round(ledger.total_cost, 6)})
    return result
