"""Stage 5, Understand: Nemotron 3 Ultra writes the lesson bible.

This is the one judgement that needs the whole lecture at once: what the picture adds that the speech does not,
which of those facts a student needs, and which silence each one should go into. Ultra thinks (with an explicit,
generous budget) and holds the full transcript, every segment report and every silence in one context.
"""

from __future__ import annotations

import json
import math

from .config import Role, Settings
from .ledger import Ledger
from .perceive import Observation
from .schemas import Gap, LessonBible, PointerResolution, PointingMoment, Word
from .segments import timed_transcript
from .tf_client import TokenFactory

SYSTEM = """You are a senior audio describer planning description for a recorded lecture, for blind and low-vision \
students. You receive the timed transcript, a visual report for each segment (from a vision model), the pointing \
moments (where the speaker points at something instead of saying it), the silences available for description with \
their word budgets, and verified names from the video's source page.

Produce the lesson bible:
1. summary: one sentence on what the lecture is about.
2. registry: names that may be spoken in descriptions. Only names printed on screen (source "slide"), said in the \
transcript (source "speech") or listed as verified context (source "context"). Never a name inferred from a face.
3. notation: symbols and terms with how to read them aloud.
4. visual_facts: what a sighted student gets from the picture that the speech does not say. id f1, f2, ...; t is \
when the fact becomes visible (seconds from the start of the video); fact is at most 25 words, objective, present \
tense, specific (values, labels, shapes, what changes), built only from the visual reports; importance 3 = needed to follow the lecture (always 3 \
when the fact resolves a pointing moment that refers to something visible), 2 = helpful, 1 = nice to have; already_spoken is true when the speech already conveys it; moment_id is the pointing moment it resolves, or "".
5. cue_plan: assign facts to silences, at most one plan per silence, and write the draft to speak there. Prefer \
the first silence at or after the fact's time, within about 10 seconds. Use only silences with a word_budget of at \
least 4. The draft must fit the silence's word budget (count each number as the words needed to say it). A draft \
must make sense to someone who cannot see: name what the thing is, then the concrete detail a listener can picture \
(values, direction, position, what changes), e.g. "Graph: dots at 10 for the first half, then at 0." Avoid \
abstract labels such as "even symmetry" unless they are printed on screen. Present tense; no "we see". Most \
important facts first; drop \
importance-1 facts when space is short. If an importance-3 fact has no silence that fits, use gap_id "extended" \
(the player pauses the video) with a draft of at most 30 words. Never plan facts that are already_spoken. Every \
pointing moment that refers to something visible should be covered.
6. style_notes: short guidance for the writer, such as what to call recurring elements.

Rules (DCMP Description Key, WCAG 2.1 SC 1.2.5): describe what is visible and needed for comprehension; do not \
interpret or explain; do not repeat what is said; copy numbers and names exactly as printed."""


def word_budget(gap: Gap, settings: Settings) -> int:
    usable = gap.duration - 2 * settings.speech_guard_seconds - settings.speech_lead_seconds
    return max(0, math.floor(usable * settings.words_per_second))


def _observation_digest(obs: Observation) -> dict:
    f = obs.facts
    return {
        "segment": obs.segment.id,
        "start": obs.segment.start,
        "end": obs.segment.end,
        "setting": f.setting,
        "on_screen_text": f.on_screen_text[:40],
        "visuals": [v.model_dump() for v in f.visuals],
        "events": [e.model_dump() for e in f.events],
        "people": f.people,
    }


async def build_bible(
    tf: TokenFactory,
    ledger: Ledger,
    settings: Settings,
    *,
    duration: float,
    words: list[Word],
    observations: list[Observation],
    moments: list[PointingMoment],
    resolutions: dict[str, PointerResolution],
    gaps: list[Gap],
    context_names: list[str],
) -> LessonBible:
    payload = {
        "duration_seconds": round(duration, 1),
        "transcript": timed_transcript(words),
        "segments": [_observation_digest(o) for o in observations],
        "pointing_moments": [
            {
                "moment_id": m.id,
                "t": m.t,
                "phrase": m.phrase,
                "sentence": m.sentence,
                "refers_to_visual": resolutions[m.id].refers_to_visual if m.id in resolutions else None,
                "target": resolutions[m.id].target if m.id in resolutions else "",
                "unsaid": resolutions[m.id].unsaid if m.id in resolutions else "",
            }
            for m in moments
        ],
        "silences": [
            {
                "gap_id": g.id,
                "start": g.start,
                "end": g.end,
                "seconds": round(g.duration, 2),
                "word_budget": word_budget(g, settings),
            }
            for g in gaps
        ],
        "verified_context_names": context_names,
    }
    result = await tf.chat(
        Role.REASON,
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        stage="understand",
        ledger=ledger,
        thinking=True,
        schema=LessonBible,
        constrain=False,
        medium_effort=settings.reason_effort == "medium",
    )
    return result.parsed  # type: ignore[return-value]
