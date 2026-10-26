"""Stage 9, Lecturer tips: turn each unsaid pointing moment into a sentence the lecturer could say next time.

W3C calls this "integrated description": when the speaker describes the visual while recording, nothing needs
to be added afterwards. One batched Lightning call per video.
"""

from __future__ import annotations

import json

from .config import Role
from .ledger import Ledger
from .schemas import LessonBible, PointerResolution, PointingMoment, Tip, TipBatch
from .tf_client import TokenFactory

SYSTEM = (
    "You coach lecturers to make recordings accessible to blind students. At each moment the lecturer pointed at "
    "something instead of saying it. Write the sentence the lecturer could say instead: natural speech in their "
    "own voice, at most 35 words, carrying the visual information (values, shapes, labels, what changes) using only "
    "the facts given. Replace the pointing words; never paste fragments of the facts or labels such as 'side view:'.\n"
    "Example 1. Said: 'As you can see, this curve drops really quickly.' Facts: 'Line graph: training error falls "
    "from 40% to 5% within 10 epochs.' Suggestion: 'The training error drops really quickly, from 40% to 5% within "
    "the first 10 epochs.'\n"
    "Example 2. Said: 'We plug these values in here.' Facts: 'Table: x equals 2 and y equals 3; formula: 2x plus y.' "
    "Suggestion: 'We plug x equals 2 and y equals 3 into 2x plus y.'\n"
    "If the facts add nothing concrete, return an empty suggestion."
)


async def lecturer_tips(
    tf: TokenFactory,
    ledger: Ledger,
    moments: list[PointingMoment],
    resolutions: dict[str, PointerResolution],
    bible: LessonBible,
) -> list[Tip]:
    facts_by_moment: dict[str, list[str]] = {}
    for fact in bible.visual_facts:
        if fact.moment_id:
            facts_by_moment.setdefault(fact.moment_id, []).append(fact.fact)
    items = [
        {
            "moment_id": m.id,
            "said": m.sentence,
            "visual_facts": [*facts_by_moment.get(m.id, []), resolutions[m.id].unsaid],
        }
        for m in moments
        if m.id in resolutions
        and resolutions[m.id].refers_to_visual
        and (facts_by_moment.get(m.id) or resolutions[m.id].unsaid)
    ]
    if not items:
        return []
    result = await tf.chat(
        Role.FAST,
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
        stage="tips",
        ledger=ledger,
        schema=TipBatch,
        max_tokens=1500,
    )
    by_moment = {m.id: m for m in moments}
    return [
        Tip(
            moment_id=t.moment_id,
            t=by_moment[t.moment_id].t,
            said=by_moment[t.moment_id].sentence,
            suggestion=t.suggestion,
        )
        for t in result.parsed.items  # type: ignore[union-attr]
        if t.moment_id in by_moment and t.suggestion.strip()
    ]
