"""Stage 4, Resolve: Nemotron 3 Nano decides what each pointing phrase points at.

The lexicon in `deixis.py` is deliberately generous ("in the right polarity" matches "in the right"). Nano reads
each candidate with the words around it and the segment report, and returns whether it refers to something
visible, which element, and what the speaker leaves unsaid. One batched, schema-constrained call per video.
"""

from __future__ import annotations

import json

from .config import Role
from .ledger import Ledger
from .perceive import Observation
from .schemas import PointerResolution, PointerResolutions, PointingMoment, Word
from .segments import said_between
from .tf_client import TokenFactory

SYSTEM = (
    "You help an audio describer. A speaker in a lecture video sometimes relies on the viewer seeing something "
    "instead of saying it. For each candidate phrase, decide whether, at that moment, the speaker refers to "
    "something currently visible and the meaning depends on seeing it.\n"
    "True examples: 'as you can see, this curve drops', 'the data has been plotted on the screen behind me', "
    "'look at this point here', 'these values on the rocker arms'.\n"
    "False examples: figures of speech ('in the right polarity'), hypothetical or later actions ('students could "
    "look at the graph afterwards'), 'let's look at what happens' when nothing specific is shown, and anything the "
    "speech already states in full.\n"
    "When true: target is the label of the visual element from the segment report, and unsaid is the visual "
    "information itself (values, shape, labels, what changes), at most 25 words, using only facts from the report. "
    "Never write that something 'is visible' or 'is displayed' without saying what it shows. When false, leave "
    "target and unsaid empty. confidence is between 0 and 1."
)


def _segment_digest(obs: Observation, t: float) -> dict:
    facts = obs.facts
    return {
        "segment": obs.segment.id,
        "visuals": [
            {"label": v.label, "kind": v.kind, "shows": v.description, "values": v.values[:12]}
            for v in facts.visuals
        ],
        "on_screen_text": facts.on_screen_text[:30],
        "events_near": [{"t": e.t, "what": e.description} for e in facts.events if abs(e.t - t) <= 6],
    }


async def resolve_moments(
    tf: TokenFactory,
    ledger: Ledger,
    moments: list[PointingMoment],
    observations: dict[str, Observation],
    words: list[Word],
) -> dict[str, PointerResolution]:
    if not moments:
        return {}
    candidates = [
        {
            "moment_id": m.id,
            "t": m.t,
            "phrase": m.phrase,
            "words_around": said_between(words, m.t - 6, m.t + 6),
            "report": _segment_digest(observations[m.segment_id], m.t)
            if m.segment_id in observations
            else {},
        }
        for m in moments
    ]
    result = await tf.chat(
        Role.CLASSIFY,
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Candidates:\n" + json.dumps(candidates, ensure_ascii=False)},
        ],
        stage="resolve",
        ledger=ledger,
        schema=PointerResolutions,
        max_tokens=4000,
    )
    parsed: PointerResolutions = result.parsed  # type: ignore[assignment]
    by_id = {r.moment_id: r for r in parsed.items}
    # Anything the model skipped is treated as "not a visual reference" rather than silently dropped.
    return {
        m.id: by_id.get(m.id)
        or PointerResolution(moment_id=m.id, refers_to_visual=False, target="", unsaid="", confidence=0.0)
        for m in moments
    }
