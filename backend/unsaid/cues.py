"""Stage 7, Write & fit: Ultra drafts, Lightning repairs, code decides.

Nemotron 3 Ultra drafts every cue inside the lesson bible, with each silence's word budget in view. Code checks the
draft. When a draft breaks a rule, Nemotron 3.5 Lightning repairs it (up to two turns quoting the exact failure), all
cues in parallel. If the timing still fails, code trims trailing clauses, keeping the most important first clause.
Only facts Ultra marked essential may become extended descriptions (the player pauses the video); anything else that
cannot fit is left out and listed, never squeezed into a meaningless fragment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from . import gates
from .bible import word_budget
from .config import Role, Settings
from .ledger import Ledger
from .perceive import Observation
from .schemas import Cue, CuePlan, CueText, Gap, Interval, LessonBible, VisualFact, Word
from .tf_client import AuthFailure, CreditExhausted, TokenFactory

log = logging.getLogger(__name__)

MAX_REPAIRS = 2
EXTENDED_WORDS = gates.EXTENDED_WORDS
MIN_INLINE_WORDS = 4  # a silence that holds fewer words than this only produces fragments like "Yellow box."

SYSTEM = """You write or repair one audio description cue for a blind student watching a lecture video. The cue is \
spoken by a synthetic voice in a pause in the lecture.
Rules:
- Describe only the facts given, most important first. Never add details that are not in the facts.
- The on-screen text and printed values are only for copying spellings and numbers exactly.
- At most max_words words, counting each number as the words it takes to say. Shorter is better.
- Present tense, objective, concrete: what is visible, never an explanation.
- Start by naming what the thing is (a graph, a slide, a machine part, an action), then the key detail.
- Never say "we see", "you can see", "the image shows" or "in this video".
- Use digits for numbers. Name things only with names from allowed_names; otherwise describe them.
Reply with JSON: {"text": "..."}."""


@dataclass
class CueContext:
    allowed_numbers: set[str]
    vocabulary: set[str]
    on_screen_text: list[str]
    printed_values: list[str] = field(default_factory=list)  # values read off charts and tables


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
    values = [
        x
        for fact in facts
        if (o := observations.get(fact.segment_id))
        for v in o.facts.visuals
        for x in v.values
    ]
    return CueContext(
        allowed_numbers=allowed,
        vocabulary=vocab,
        on_screen_text=screen[:40],
        printed_values=list(dict.fromkeys(values))[:40],
    )


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
    names = [r.name for r in bible.registry if r.name and gates.mentions(r.name, haystack)]
    return list(dict.fromkeys([*names, *context_names]))


def pause_point(anchor: float, words: list[Word], max_wait: float = 6.0) -> float:
    """When to pause the video for an extended description about `anchor`: right away if nobody is speaking then,
    otherwise at the end of the sentence being spoken, so no word is cut (or at the end of the current word if
    that sentence runs on for more than max_wait seconds)."""
    upcoming = [w for w in words if w.end > anchor]
    if not upcoming or upcoming[0].start > anchor:
        return anchor
    for w in upcoming:
        if w.end - anchor > max_wait:
            break
        if w.text.rstrip().endswith((".", "?", "!")):
            return w.end
    return upcoming[0].end


def trim_candidates(text: str) -> Iterator[str]:
    """Shorter versions of a cue that keep its opening: drop trailing sentences, then trailing clauses."""
    sentences = [x for x in re.split(r"(?<=[.!?;])\s+", text.strip()) if x]
    for k in range(len(sentences) - 1, 0, -1):
        yield " ".join(sentences[:k])
    clauses = [x for x in re.split(r",\s+|\s+[—–]\s+", sentences[0]) if x] if sentences else []
    for k in range(len(clauses) - 1, 0, -1):
        candidate = ", ".join(clauses[:k]).rstrip(".;:,") + "."
        if len(candidate.split()) >= MIN_INLINE_WORDS:
            yield candidate


def _window(gap: Gap | None, start_hint: float, settings: Settings) -> tuple[float, float, int]:
    if gap is None:
        return start_hint, start_hint + EXTENDED_WORDS / settings.words_per_second, EXTENDED_WORDS
    return gap.start + settings.speech_guard_seconds, gap.end, word_budget(gap, settings)


TIMING = ("too_long", "talks_over_speech")
# A description of something the speaker points at starts within this window around the pointing moment.
POINTING_WINDOW = (-3.0, 10.0)


@dataclass
class _Placement:
    n: int
    plan: CuePlan
    facts: list[VisualFact]
    anchor: float  # the later of the pointing moment and when its facts are on screen, else when they appear
    gap: Gap | None
    pointed: bool  # resolves a pointing moment and still needs its silence checked or moved
    earliest: float = 0.0  # a pointing description starts no earlier than 3 s before the pointing, nor before
    latest: float = 0.0  # its facts are on screen, and no later than 10 s after the pointing

    def fits(self, gap: Gap, guard: float) -> bool:
        return self.earliest <= gap.start + guard <= self.latest


def _timing_only(report: gates.GateReport) -> bool:
    return bool(report.failures) and all(f.startswith(TIMING) for f in report.failures)


async def write_cue(
    tf: TokenFactory,
    ledger: Ledger,
    settings: Settings,
    *,
    cue_id: str,
    facts: list[VisualFact],
    draft: str,
    gap: Gap | None,
    speech: list[Interval],
    context: CueContext,
    bible: LessonBible,
    allowed_names: list[str],
    pause_at: float | None = None,
) -> Cue | None:
    """`pause_at` is where an extended description pauses the video; by default, where its first fact appears.

    Only an essential fact, or one the speaker points at, may pause the video; anything else that does not fit a
    silence is left out. A pause is never earlier than `pause_at`, so it never comes before the thing is on screen.
    """
    essential = max(f.importance for f in facts) >= 3
    may_pause = essential or any(f.moment_ids for f in facts)
    start_hint = pause_at if pause_at is not None else min(f.t for f in facts)
    if gap is None and not may_pause:
        return None
    start, window_end, budget = _window(gap, start_hint, settings)
    extended = gap is None
    if gap is not None and budget < MIN_INLINE_WORDS:
        if not essential:
            return None
        extended = True
        start, window_end, budget = _window(
            None, max(gap.start + settings.speech_guard_seconds, start_hint), settings
        )

    def check(text: str, as_extended: bool) -> gates.GateReport:
        return gates.check_cue(
            text,
            start,
            window_end,
            speech=speech,
            allowed_numbers=context.allowed_numbers,
            known_vocabulary=context.vocabulary,
            words_per_second=settings.words_per_second,
            guard=settings.speech_guard_seconds,
            lead=settings.speech_lead_seconds,
            extended=as_extended,
        )

    brief = {
        "facts": [f.fact for f in facts],
        "max_words": budget,
        "allowed_names": allowed_names[:60],
        "on_screen_text": context.on_screen_text,
        "printed_values": context.printed_values,
        "how_to_read_symbols": bible.notation,
    }
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]
    origin = ["Ultra draft"]
    text = draft.strip()
    if not text:
        result = await tf.chat(
            Role.FAST, messages, stage="write", ledger=ledger, schema=CueText, max_tokens=300
        )
        text = result.parsed.text.strip()  # type: ignore[union-attr]
        origin = ["Lightning"]
    report = check(text, extended)

    repairs = 0
    while not report.passed and repairs < MAX_REPAIRS:
        repairs += 1
        spoken = round(gates.spoken_word_count(text))
        notes = []
        for failure in report.failures:
            if failure.startswith(TIMING) and spoken <= budget:
                notes.append(
                    f"Its {spoken} spoken words fit, but the pauses at its commas, colons and dashes make it too "
                    "long. Use fewer of them, or drop one word, and keep every detail."
                )
            elif failure.startswith(TIMING):
                notes.append(
                    f"It takes {spoken} spoken words; the pause allows {budget}. Rewrite it in "
                    f"{max(budget - 1, 2)} words or fewer, keeping the most important detail."
                )
            elif failure.startswith("number_not_on_screen"):
                notes.append(
                    f"{failure}. Use a number only exactly as printed in on_screen_text or printed_values, "
                    "or leave it out."
                )
            elif failure.startswith("unknown_name"):
                notes.append(f"{failure}. Describe it instead of naming it.")
            elif failure == "says_nothing":
                notes.append(
                    "It names the kind of picture but not what it shows. Say what the facts say: the words, values "
                    "or objects themselves."
                )
            else:
                notes.append(failure)
        messages = [
            *messages,
            {"role": "assistant", "content": json.dumps({"text": text}, ensure_ascii=False)},
            {"role": "user", "content": "Revise. " + " ".join(dict.fromkeys(notes))},
        ]
        result = await tf.chat(
            Role.FAST, messages, stage="write", ledger=ledger, schema=CueText, max_tokens=300
        )
        text = result.parsed.text.strip()  # type: ignore[union-attr]
        report = check(text, extended)
    if repairs:
        origin.append(f"{repairs} Lightning repair{'s' if repairs > 1 else ''}")

    if not extended and _timing_only(report):
        for candidate in trim_candidates(text):
            trial = check(candidate, False)
            if trial.passed:
                text, report = candidate, trial
                origin.append("trimmed to fit")
                break

    if not extended and any(f.startswith(TIMING) for f in report.failures):
        if not essential:
            return None
        extended = True
        start, window_end, _ = _window(None, max(start, start_hint), settings)
        report = check(text, True)
        origin.append("extended: video pauses")

    end = start + report.estimated_seconds if not extended else start + 0.5
    return Cue(
        id=("ext-" if extended else "ad-") + cue_id,
        gap_id=gap.id if gap else None,
        start=round(start, 3),
        end=round(min(end, window_end) if not extended else end, 3),
        text=text,
        extended=extended,
        fact_ids=[f.id for f in facts],
        moment_ids=list(dict.fromkeys(m for f in facts for m in f.moment_ids)),
        gate_failures=report.failures,
        gate_warnings=report.warnings,
        repairs=repairs,
        origin=" + ".join(origin),
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
    moment_times: dict[str, float] | None = None,
) -> list[Cue]:
    moment_times = moment_times or {}
    facts_by_id = {f.id: f for f in bible.visual_facts if not f.already_spoken}
    gaps_by_id = {g.id: g for g in gaps}
    allowed_names = verified_names(bible, observations, words, context_names)

    # A description of what the speaker points at belongs where they point, not where the thing first appeared, and
    # not before it is on screen either: speakers often announce a picture ("here's a picture of...") before it shows.
    placed: list[_Placement] = []
    for n, plan in enumerate(bible.cue_plan, start=1):
        facts = [facts_by_id[i] for i in plan.fact_ids if i in facts_by_id]
        if not facts:
            continue
        pointed = [moment_times[m] for f in facts for m in f.moment_ids if m in moment_times]
        gap = gaps_by_id.get(plan.gap_id)
        if pointed:
            moment, visible = min(pointed), max(f.t for f in facts)
            placed.append(
                _Placement(
                    n,
                    plan,
                    facts,
                    max(moment, visible),
                    gap,
                    gap is not None,
                    earliest=max(moment + POINTING_WINDOW[0], visible),
                    latest=moment + POINTING_WINDOW[1],
                )
            )
        else:
            placed.append(_Placement(n, plan, facts, min(f.t for f in facts), gap, False))

    # One cue per silence. Silences that Ultra chose well are taken first; a second plan for the same silence
    # becomes extended. A pointing description that Ultra put far from its moment then moves to the first free
    # silence near the moment, or pauses the video there.
    used: set[str] = set()
    for p in placed:
        if p.gap is None:
            continue
        if p.pointed and not p.fits(p.gap, settings.speech_guard_seconds):
            p.gap = None
            continue
        p.pointed = False  # placed well: nothing to move
        if p.gap.id in used:
            p.gap = None
        else:
            used.add(p.gap.id)
    for p in placed:
        if p.pointed:
            p.gap = next(
                (g for g in gaps if g.id not in used and p.fits(g, settings.speech_guard_seconds)), None
            )
            if p.gap is not None:
                used.add(p.gap.id)

    jobs = [
        write_cue(
            tf,
            ledger,
            settings,
            cue_id=f"{p.n:03d}",
            facts=p.facts,
            draft=p.plan.draft,
            gap=p.gap,
            speech=speech,
            context=build_context(p.facts, observations, words, allowed_names),
            bible=bible,
            allowed_names=allowed_names,
            pause_at=pause_point(p.anchor, words),
        )
        for p in placed
    ]
    # One description whose repair fails is dropped; it does not take the others with it.
    written = await asyncio.gather(*jobs, return_exceptions=True)
    for outcome in written:
        if isinstance(outcome, (CreditExhausted, AuthFailure)):
            raise outcome
        if isinstance(outcome, BaseException):
            log.warning("a description was dropped: %s: %s", type(outcome).__name__, outcome)
    cues = sorted((c for c in written if isinstance(c, Cue)), key=lambda c: c.start)
    for cue in cues:
        if cue.extended:
            speaking = next((c for c in cues if not c.extended and c.start <= cue.start < c.end), None)
            if speaking is not None:  # inline descriptions sit in silences, so its end is still silent
                cue.start, cue.end = speaking.end, round(speaking.end + 0.5, 3)
    return sorted(cues, key=lambda c: c.start)
