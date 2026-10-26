"""Stage 3, Watch: Nemotron 3.5 Super VL reports what each segment shows.

Each request carries a low-frame-rate clip (motion, pointing, builds) and up to three full-resolution stills
(slide text, chart labels, numbers). Thinking is off: this is perception, not deliberation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import media
from .config import Role
from .ledger import Ledger
from .schemas import Segment, SegmentFacts, Word
from .segments import said_between
from .tf_client import TokenFactory

SYSTEM = (
    "You are the eyes of an audio describer for blind and low-vision students. You watch one segment of a recorded "
    "lecture and report only what is visible.\n"
    "Rules:\n"
    "- Copy on-screen text, labels and numbers exactly as printed; skip interface chrome such as menu items.\n"
    "- For every chart, equation, diagram, table or code block, say what it shows: axes and units, the trend, "
    "key values, highlighted parts.\n"
    "- Report events (actions, pointing, slide builds, writing) with their time in seconds from the start of the "
    "whole video.\n"
    "- Never identify a person from their face. Describe appearance and action; use a name only if it is printed "
    "on screen.\n"
    "- Present tense, objective, no guesses about intent. If something is unreadable, say it is illegible.\n"
    "- The transcript is context only: never report something because it was said."
)


@dataclass
class Observation:
    segment: Segment
    facts: SegmentFacts
    stills: list[tuple[float, Path]] = field(default_factory=list)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


async def perceive(
    tf: TokenFactory, ledger: Ledger, video: Path, segment: Segment, words: list[Word], workdir: Path
) -> Observation:
    clip = await media.cut_clip(video, segment.start, segment.end, workdir / f"{segment.id}.mp4")
    times = segment.keyframes[-3:] if len(segment.keyframes) > 3 else segment.keyframes
    stills = [
        (t, await media.still(video, t, workdir / f"{segment.id}_{i}.jpg")) for i, t in enumerate(times)
    ]
    said = said_between(words, segment.start, segment.end) or "(no speech)"
    user = [
        {
            "type": "text",
            "text": (
                f"Segment {segment.id}: {segment.start:.1f}s to {segment.end:.1f}s of the video.\n"
                f'Said during it: "{said[:1500]}"\n'
                "The clip is low frame rate. The still images are full-resolution frames at "
                + ", ".join(f"{t:.1f}s" for t, _ in stills)
                + ": read text and numbers from them."
            ),
        },
        {"type": "video_url", "video_url": {"url": media.data_url(clip)}},
        *[{"type": "image_url", "image_url": {"url": media.data_url(p)}} for _, p in stills],
    ]
    result = await tf.chat(
        Role.VISION,
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        stage="watch",
        ledger=ledger,
        schema=SegmentFacts,
        max_tokens=3500,
    )
    facts: SegmentFacts = result.parsed  # type: ignore[assignment]
    facts.on_screen_text = _dedupe(facts.on_screen_text)
    for event in facts.events:
        # Models sometimes answer relative to the clip; anything before the segment start is treated that way.
        if event.t < segment.start - 0.5:
            event.t += segment.start
        event.t = round(min(max(event.t, segment.start), segment.end), 2)
    return Observation(segment=segment, facts=facts, stills=stills)
