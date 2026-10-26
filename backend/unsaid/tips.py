"""Stage 9, Lecturer tips: turn each unsaid pointing moment into a sentence the lecturer could say next time.

W3C calls this "integrated description": when the speaker describes the visual while recording, nothing needs
to be added afterwards. One batched Lightning call per video.
"""

from __future__ import annotations

import json

from .config import Role
from .ledger import Ledger
from .schemas import PointerResolution, PointingMoment, Tip, TipBatch
from .tf_client import TokenFactory

SYSTEM = (
    "You coach lecturers to make recordings accessible to blind students. For each moment, the lecturer pointed at "
    "something instead of saying it. Rewrite what they said so the words carry the visual information, in the "
    "lecturer's own voice, at most 30 words. Use only the facts given."
)


async def lecturer_tips(
    tf: TokenFactory,
    ledger: Ledger,
    moments: list[PointingMoment],
    resolutions: dict[str, PointerResolution],
) -> list[Tip]:
    items = [
        {"moment_id": m.id, "said": m.sentence, "unsaid": resolutions[m.id].unsaid}
        for m in moments
        if m.id in resolutions and resolutions[m.id].refers_to_visual and resolutions[m.id].unsaid
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
        if t.moment_id in by_moment
    ]
