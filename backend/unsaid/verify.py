"""Stage 8, Check: Nemotron 3.5 Super VL re-reads the frames and checks every claim in every cue.

The writer only saw text facts; the checker sees the pixels again, at the moments those facts become visible.
Each claim is judged supported, contradicted or not visible. Together with the code gates this sets the tier:

* auto: every gate passed and every claim is supported by the frames;
* review: a gate warning, a gate failure that repairs could not fix, or any claim that is not supported;
* never: identifies a person who is not named on screen, in speech or on the source page.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from . import gates, media
from .config import Role
from .ledger import Ledger
from .schemas import Cue, LessonBible, Verification
from .tf_client import AuthFailure, CreditExhausted, TokenFactory

SYSTEM = (
    "You check one audio description written for a lecture video against frames from that moment. Split the "
    "description into the factual claims it literally makes (never add claims of your own, such as names or "
    "interpretations that are not in the description) and judge each one: supported (clearly visible in the clip or the frames), "
    "contradicted (they show something different: wrong number, colour, direction, side or object) or not_visible "
    "(cannot be seen at all). The clip and frames end when the description ends, so something that is not on "
    "screen yet is not_visible. For each contradicted claim, say in observed what the frames show instead. identifies_person is true if the description names a person or says who someone is; describing "
    "appearance or action is fine."
)


def latest_frame(cue: Cue) -> float:
    """The last moment a description can be about: while it is heard. An extended one pauses the video at its start."""
    return cue.start + 0.5 if cue.extended else max(cue.end, cue.start + 0.5)


async def verify_cue(
    tf: TokenFactory, ledger: Ledger, video: Path, cue: Cue, times: list[float], workdir: Path
) -> None:
    """Judge each claim against stills plus a short clip, so motion can be checked too. Nothing after the description
    ends is shown: a description of something that only appears later is premature, not supported."""
    latest = latest_frame(cue)
    times = [t for t in times if t <= latest] or [min(cue.start + 0.3, latest)]
    stills = [await media.still(video, t, workdir / f"check_{cue.id}_{i}.jpg") for i, t in enumerate(times)]
    clip_start = max(
        min(min(times) - 1.0, latest - 1.5), 0.0
    )  # at least 2 s of motion, ending by latest + 0.5
    clip_end = min(clip_start + 7.0, latest + 0.5)
    clip = await media.cut_clip(video, clip_start, clip_end, workdir / f"check_{cue.id}.mp4", fps=4)
    content = [
        {
            "type": "text",
            "text": f'Description (heard from {cue.start:.1f}s to {cue.end:.1f}s): "{cue.text}"\n'
            f"A short clip from {clip_start:.1f}s to {clip_end:.1f}s shows any motion; "
            f"full-resolution frames at {', '.join(f'{t:.1f}s' for t in times)} show text and detail.",
        },
        {"type": "video_url", "video_url": {"url": media.data_url(clip)}},
        *[{"type": "image_url", "image_url": {"url": media.data_url(p)}} for p in stills],
    ]
    result = await tf.chat(
        Role.VISION,
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        stage="check",
        ledger=ledger,
        schema=Verification,
        max_tokens=1000,
    )
    cue.verification = result.parsed  # type: ignore[assignment]


def assign_tier(cue: Cue, allowed_names: list[str]) -> None:
    v = cue.verification
    names_known = any(gates.mentions(name, cue.text) for name in allowed_names)
    if v is not None and v.identifies_person and not names_known:
        cue.tier = "never"
    elif cue.gate_failures or cue.gate_warnings or v is None or not v.supported:
        cue.tier = "review"
    else:
        cue.tier = "auto"


def check_times(
    cue: Cue, bible: LessonBible, duration: float, moment_times: dict[str, float] | None = None
) -> list[float]:
    """At most three frames to check a cue against, none after it ends: first what is on screen while it is heard,
    then where the speaker pointed at what it describes (timed by speech recognition, so reliable), then where each
    fact became visible (the planner's estimate, which can be seconds off) and one second later."""
    facts = [f for f in bible.visual_facts if f.id in cue.fact_ids]
    moment_times = moment_times or {}
    times = [cue.start + 0.3]
    times += [moment_times[m] + 0.3 for f in facts for m in f.moment_ids if m in moment_times]
    times += [t for f in facts for t in (f.t + 0.3, f.t + 1.3)]
    latest = latest_frame(cue)
    picked: list[float] = []
    for t in times:
        t = round(min(max(t, 0.0), max(duration - 0.1, 0.0)), 2)
        if t <= latest and t not in picked:
            picked.append(t)
    return sorted(picked[:3])


async def verify_all(
    tf: TokenFactory,
    ledger: Ledger,
    video: Path,
    cues: list[Cue],
    bible: LessonBible,
    duration: float,
    allowed_names: list[str],
    workdir: Path,
    moment_times: dict[str, float] | None = None,
) -> None:
    async def one(cue: Cue) -> None:
        try:
            await verify_cue(tf, ledger, video, cue, check_times(cue, bible, duration, moment_times), workdir)
        except (CreditExhausted, AuthFailure):
            raise
        except Exception:
            cue.verification = None

    await asyncio.gather(*(one(c) for c in cues))
    for cue in cues:
        assign_tier(cue, allowed_names)
