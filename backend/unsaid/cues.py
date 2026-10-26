"""Stage 7, Write & fit: Nemotron 3.5 Lightning writes each cue; code decides whether it may be used.

One independent call per cue (Lightning drifts over long loops), all in parallel, with the same instruction prefix
so Token Factory can cache it. A cue that fails the gates gets up to two repair turns that quote the exact failure.
If it still cannot fit its silence, it becomes an extended description (the player pauses the video).
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass

from . import gates
from .config import Role, Settings
from .ledger import Ledger
from .perceive import Observation
from .schemas import Cue, CueText, Gap, Interval, LessonBible, VisualFact, Word
from .tf_client import TokenFactory

MAX_REPAIRS = 2
EXTENDED_WORDS = 30

SYSTEM = """You write one audio description cue for a blind student watching a lecture video. The cue is spoken \
by a synthetic voice in a pause in the lecture.
Rules:
- Describe only the facts given, in order of importance. Never add details that are not in the facts.
- The on-screen text is only for copying spellings and numbers exactly; do not describe it unless a fact does.
- At most max_words words. Shorter is better; drop the least important detail first.
- Present tense, objective, concrete: what is visible, never an explanation.
- Start with the thing itself ("Line chart: ...", "Slide: ...", "The presenter presses ...").
- Never say "we see", "you can see", "the image shows" or "in this video".
- Use digits for numbers. Name things only with names from allowed_names; otherwise describe them.
Reply with JSON: {"text": "..."}."""


@dataclass
class CueContext:
    allowed_numbers: set[str]
    vocabulary: set[str]
    on_screen_text: list[str]


def build_context(
    facts: list[VisualFact],
    observations: dict[str, Observation],
    words: list[Word],
    registry_names: list[str],
) -> CueContext:
    texts: list[str] = []
    for fact in facts:
        obs = observations.get(fact.segment_id)
        if obs:
            f = obs.facts
            texts += (
                f.on_screen_text
                + [v.description for v in f.visuals]
                + [x for v in f.visuals for x in v.values]
            )
            texts += [e.description for e in f.events]
    spoken = " ".join(w.text for w in words)
    allowed = set().union(*(gates.numbers_in(t) for t in [*texts, spoken])) if texts or spoken else set()
    screen = [t for fact in facts if (o := observations.get(fact.segment_id)) for t in o.facts.on_screen_text]
    vocab = gates.vocabulary(screen, [spoken], registry_names)
    return CueContext(allowed_numbers=allowed, vocabulary=vocab, on_screen_text=screen[:40])


def verified_names(
    bible: LessonBible, observations: dict[str, Observation], words: list[Word], context_names: list[str]
) -> list[str]:
    """Registry names survive only if they literally occur on screen, in the speech or in Tavily context."""
    haystack = " ".join(
        [
            *(t for o in observations.values() for t in o.facts.on_screen_text),
            *(w.text for w in words),
            *context_names,
        ]
    ).lower()
    names = [r.name for r in bible.registry if r.name and r.name.lower() in haystack]
    return list(dict.fromkeys([*names, *context_names]))


def _window(gap: Gap | None, start_hint: float, settings: Settings) -> tuple[float, float, int]:
    if gap is None:
        return start_hint, start_hint + EXTENDED_WORDS / settings.words_per_second, EXTENDED_WORDS
    start = gap.start + settings.speech_guard_seconds
    usable = gap.end - settings.speech_guard_seconds - start - settings.speech_lead_seconds
    return start, gap.end, max(0, math.floor(usable * settings.words_per_second))


async def write_cue(
    tf: TokenFactory,
    ledger: Ledger,
    settings: Settings,
    *,
    cue_id: str,
    facts: list[VisualFact],
    gap: Gap | None,
    speech: list[Interval],
    context: CueContext,
    bible: LessonBible,
    allowed_names: list[str],
) -> Cue:
    start_hint = min(f.t for f in facts)
    start, window_end, budget = _window(gap, start_hint, settings)
    extended = gap is None or budget < 3
    if extended and gap is not None:
        start, window_end, budget = _window(None, gap.start + settings.speech_guard_seconds, settings)

    prompt = {
        "facts": [f.fact for f in facts],
        "max_words": budget,
        "allowed_names": allowed_names[:60],
        "on_screen_text": context.on_screen_text,
        "how_to_read_symbols": bible.notation,
    }
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]
    repairs = 0
    text = ""
    report = gates.GateReport()
    while True:
        result = await tf.chat(
            Role.FAST, messages, stage="write", ledger=ledger, schema=CueText, max_tokens=300
        )
        text = result.parsed.text.strip()  # type: ignore[union-attr]
        report = gates.check_cue(
            text,
            start,
            window_end,
            speech=speech,
            allowed_numbers=context.allowed_numbers,
            known_vocabulary=context.vocabulary,
            words_per_second=settings.words_per_second,
            guard=settings.speech_guard_seconds,
            lead=settings.speech_lead_seconds,
            extended=extended,
        )
        if report.passed or repairs >= MAX_REPAIRS:
            break
        repairs += 1
        words_now = round(gates.spoken_word_count(text))
        notes = []
        for failure in report.failures:
            if failure.startswith("too_long") or failure == "talks_over_speech":
                notes.append(
                    f"It is {words_now} spoken words; the pause allows {budget}. Cut it to {max(budget - 1, 2)} words or fewer."
                )
            elif failure.startswith("number_not_on_screen"):
                notes.append(f"{failure}. Use only numbers printed on screen.")
            elif failure.startswith("unknown_name"):
                notes.append(f"{failure}. Describe instead of naming.")
            else:
                notes.append(failure)
        messages = [
            *messages,
            {"role": "assistant", "content": json.dumps({"text": text}, ensure_ascii=False)},
            {"role": "user", "content": "Revise. " + " ".join(notes)},
        ]

    timing_failed = any(f.startswith("too_long") or f == "talks_over_speech" for f in report.failures)
    if timing_failed and not extended:
        # It cannot fit the silence: make it an extended description instead of talking over the lecture.
        extended = True
        report.failures = [
            f for f in report.failures if not (f.startswith("too_long") or f == "talks_over_speech")
        ]

    end = start + report.estimated_seconds if not extended else start + 0.5
    return Cue(
        id=("ext-" if extended else "ad-") + cue_id,
        gap_id=gap.id if gap else None,
        start=round(start, 3),
        end=round(min(end, window_end) if not extended else end, 3),
        text=text,
        extended=extended,
        fact_ids=[f.id for f in facts],
        moment_ids=[f.moment_id for f in facts if f.moment_id],
        gate_failures=report.failures,
        gate_warnings=report.warnings,
        repairs=repairs,
    )


async def write_all(
    tf: TokenFactory,
    ledger: Ledger,
    settings: Settings,
    *,
    bible: LessonBible,
    gaps: list[Gap],
    speech: list[Interval],
    observations: dict[str, Observation],
    words: list[Word],
    context_names: list[str],
) -> list[Cue]:
    facts_by_id = {f.id: f for f in bible.visual_facts if not f.already_spoken}
    gaps_by_id = {g.id: g for g in gaps}
    allowed_names = verified_names(bible, observations, words, context_names)
    jobs = []
    used_gaps: set[str] = set()
    for n, plan in enumerate(bible.cue_plan, start=1):
        facts = [facts_by_id[i] for i in plan.fact_ids if i in facts_by_id]
        if not facts:
            continue
        gap = gaps_by_id.get(plan.gap_id)
        if gap is not None and gap.id in used_gaps:
            gap = None  # one cue per silence; a second plan for the same silence becomes extended
        if gap is not None:
            used_gaps.add(gap.id)
        context = build_context(facts, observations, words, allowed_names)
        jobs.append(
            write_cue(
                tf,
                ledger,
                settings,
                cue_id=f"{n:03d}",
                facts=facts,
                gap=gap,
                speech=speech,
                context=context,
                bible=bible,
                allowed_names=allowed_names,
            )
        )
    cues = await asyncio.gather(*jobs)
    return sorted(cues, key=lambda c: c.start)
