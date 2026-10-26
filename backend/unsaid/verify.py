"""Stage 8, Check: Nemotron 3.5 Super VL re-watches each segment and checks every cue against the frames.

The writer only saw text facts; the checker sees the pixels again. One call per segment covers all of that
segment's cues. The verdict, together with the code gates, sets each cue's tier:

* auto: passed every gate, supported by the frames, identifies no one;
* review: a gate warning, a failed gate that repairs could not fix, or a claim the frames do not support;
* never: identifies a person who is not named on screen, in speech or on the source page.
"""

from __future__ import annotations

import asyncio
import json

from . import media
from .config import Role
from .ledger import Ledger
from .perceive import Observation
from .schemas import Cue, VerificationBatch
from .segments import segment_at
from .tf_client import TokenFactory

SYSTEM = (
    "You check audio descriptions written for a lecture video. For each cue, compare every claim with the clip and "
    "the frames. supported is false if any claim is not visible (wrong number, wrong colour, invented object, "
    "wrong direction). List each unsupported claim briefly. identifies_person is true if the cue names a person "
    "or states who someone is; describing appearance or action is fine."
)


async def verify_segment(
    tf: TokenFactory, ledger: Ledger, obs: Observation, cues: list[Cue], workdir
) -> None:
    clip = workdir / f"{obs.segment.id}.mp4"
    content = [
        {
            "type": "text",
            "text": "Cues to check:\n"
            + json.dumps(
                [{"cue_id": c.id, "time": c.start, "text": c.text} for c in cues], ensure_ascii=False
            ),
        },
        *([{"type": "video_url", "video_url": {"url": media.data_url(clip)}}] if clip.exists() else []),
        *[{"type": "image_url", "image_url": {"url": media.data_url(p)}} for _, p in obs.stills],
    ]
    result = await tf.chat(
        Role.VISION,
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        stage="check",
        ledger=ledger,
        schema=VerificationBatch,
        max_tokens=1500,
    )
    verdicts = {v.cue_id: v for v in result.parsed.items}  # type: ignore[union-attr]
    for cue in cues:
        verdict = verdicts.get(cue.id)
        if verdict is not None:
            cue.verification = verdict


def assign_tier(cue: Cue, allowed_names: list[str]) -> None:
    v = cue.verification
    names_known = any(name.lower() in cue.text.lower() for name in allowed_names)
    if v is not None and v.identifies_person and not names_known:
        cue.tier = "never"
    elif cue.gate_failures or cue.gate_warnings or v is None or not v.supported:
        cue.tier = "review"
    else:
        cue.tier = "auto"


async def verify_all(
    tf: TokenFactory,
    ledger: Ledger,
    cues: list[Cue],
    observations: dict[str, Observation],
    allowed_names: list[str],
    workdir,
) -> None:
    segments = [o.segment for o in observations.values()]
    by_segment: dict[str, list[Cue]] = {}
    for cue in cues:
        by_segment.setdefault(segment_at(cue.start, segments).id, []).append(cue)
    await asyncio.gather(
        *(verify_segment(tf, ledger, observations[sid], group, workdir) for sid, group in by_segment.items())
    )
    for cue in cues:
        assign_tier(cue, allowed_names)
