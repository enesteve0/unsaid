"""Check, then correct.

When Nemotron 3.5 Super VL finds claims the frames do not support, Nemotron 3.5 Lightning rewrites the cue without
them (or corrects them from the facts), code re-applies every gate, and Super VL looks once more. One round only:
a cue that still fails keeps its original text and stays in review, so a person decides.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import gates
from .bible import PUNCTUATION_ALLOWANCE
from .config import Role, Settings
from .cues import EXTENDED_WORDS, MIN_INLINE_WORDS, build_context, verified_names
from .ledger import Ledger
from .perceive import Observation
from .schemas import Cue, CueText, Gap, Interval, LessonBible, Word
from .tf_client import AuthFailure, CreditExhausted, TokenFactory
from .verify import assign_tier, check_times, verify_cue

SYSTEM = """You fix an audio description for a blind student that a checker compared with the video frames. \
The frames win: never repeat a contradicted claim, even if the facts say it. Replace it with what the frames show \
(given as observed) or drop it; drop claims that are not visible. Keep everything that was fine and add nothing new. \
Stay within max_words, present tense, no "we see". If nothing reliable remains, return an empty text.
Reply with JSON: {"text": "..."}."""


async def correct_unsupported(
    tf: TokenFactory,
    ledger: Ledger,
    settings: Settings,
    *,
    video: Path,
    cues: list[Cue],
    bible: LessonBible,
    gaps: list[Gap],
    speech: list[Interval],
    observations: dict[str, Observation],
    words: list[Word],
    context_names: list[str],
    duration: float,
    workdir: Path,
    moment_times: dict[str, float] | None = None,
) -> int:
    facts_by_id = {f.id: f for f in bible.visual_facts}
    gaps_by_id = {g.id: g for g in gaps}
    allowed_names = verified_names(bible, observations, words, context_names)

    async def fix(cue: Cue) -> bool:
        v = cue.verification
        if v is None or v.supported or v.identifies_person:
            return False
        facts = [facts_by_id[i] for i in cue.fact_ids if i in facts_by_id]
        if not facts:
            return False
        context = build_context(facts, observations, words, allowed_names)
        gap = gaps_by_id.get(cue.gap_id or "")
        if cue.extended or gap is None:
            window_end, budget = cue.start + EXTENDED_WORDS / settings.words_per_second, EXTENDED_WORDS
        else:
            window_end = gap.end
            usable = (
                gap.end
                - settings.speech_guard_seconds
                - cue.start
                - settings.speech_lead_seconds
                - PUNCTUATION_ALLOWANCE
            )
            budget = max(2, int(usable * settings.words_per_second))
        brief = {
            "description": cue.text,
            "problems": [
                f"{c.claim} ({c.verdict.replace('_', ' ')})"
                + (f"; observed: {c.observed}" if c.observed else "")
                for c in v.claims
                if c.verdict != "supported"
            ],
            "facts": [f.fact for f in facts],
            "max_words": budget,
            "allowed_names": allowed_names[:60],
        }
        result = await tf.chat(
            Role.FAST,
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
            ],
            stage="correct",
            ledger=ledger,
            schema=CueText,
            max_tokens=300,
        )
        text = result.parsed.text.strip()  # type: ignore[union-attr]
        if not text or text == cue.text:
            return False
        if not cue.extended and len(text.split()) < MIN_INLINE_WORDS:
            # What survives is a fragment ("rock bars adjusted"); keep the original in review for a person.
            return False
        report = gates.check_cue(
            text,
            cue.start,
            window_end,
            speech=speech,
            # The frames win: numbers the checker read in them count as printed.
            allowed_numbers=context.allowed_numbers
            | set().union(*(gates.numbers_in(c.observed) for c in v.claims if c.observed)),
            known_vocabulary=context.vocabulary,
            words_per_second=settings.words_per_second,
            guard=settings.speech_guard_seconds,
            lead=settings.speech_lead_seconds,
            extended=cue.extended,
        )
        if not report.passed:
            return False
        before_text, before_verdict, before_end = cue.text, cue.verification, cue.end
        cue.text = text
        if not cue.extended:
            cue.end = round(cue.start + report.estimated_seconds, 3)
        try:
            await verify_cue(tf, ledger, video, cue, check_times(cue, bible, duration, moment_times), workdir)
        except BaseException:
            cue.text, cue.verification, cue.end = before_text, before_verdict, before_end
            raise
        after = cue.verification
        unsupported_before = sum(c.verdict != "supported" for c in v.claims)
        if after is not None and not any(c.verdict == "contradicted" for c in after.claims):
            unsupported_after = sum(c.verdict != "supported" for c in after.claims)
            if after.supported or unsupported_after < unsupported_before:
                # Strictly better: no contradictions left and fewer unsupported claims. Anything still unverified
                # keeps the description in review.
                cue.corrected_from = before_text
                cue.gate_failures = report.failures
                cue.gate_warnings = report.warnings
                step = "corrected" if after.supported else "partly corrected"
                cue.origin = f"{cue.origin} + {step} after the frame check".lstrip(" +")
                return True
        cue.text, cue.verification, cue.end = before_text, before_verdict, before_end
        return False

    async def guarded(cue: Cue) -> bool:
        try:
            return await fix(cue)
        except (CreditExhausted, AuthFailure):
            raise
        except Exception:
            return False

    fixed = sum(await asyncio.gather(*(guarded(c) for c in cues)))
    for cue in cues:
        assign_tier(cue, allowed_names)
    return fixed
