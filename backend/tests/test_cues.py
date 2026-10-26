from types import SimpleNamespace

from unsaid.config import Settings
from unsaid.cues import CueContext, trim_candidates, write_cue
from unsaid.ledger import Ledger
from unsaid.schemas import CueText, Gap, Interval, LessonBible, VisualFact

SETTINGS = Settings(_env_file=None)
SPEECH = [Interval(start=0.0, end=10.0), Interval(start=13.0, end=30.0)]  # a 3 s silence from 10 to 13
CONTEXT = CueContext(allowed_numbers={"10", "0"}, vocabulary=set(), on_screen_text=[])
BIBLE = LessonBible(summary="", registry=[], notation=[], visual_facts=[], cue_plan=[], style_notes=[])


def fact(importance=3):
    return VisualFact(id="f1", t=9.5, segment_id="s1", fact="Square wave from 0 to 10", importance=importance, already_spoken=False, moment_id="p1")


class StubTF:
    """Answers every Lightning call with the next scripted text."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = 0

    async def chat(self, role, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(parsed=CueText(text=self.texts.pop(0)))


async def run(draft, tf, importance=3, gap=Gap(id="g1", start=10.0, end=13.0)):
    return await write_cue(
        tf, Ledger(), SETTINGS, cue_id="001", facts=[fact(importance)], draft=draft, gap=gap,
        speech=SPEECH, context=CONTEXT, bible=BIBLE, allowed_names=[],
    )


def test_trim_candidates_keep_the_opening():
    out = list(trim_candidates("Square wave from 0 to 10. A bracket marks one period, and dots sample it."))
    assert out[0] == "Square wave from 0 to 10."


async def test_fitting_draft_is_used_without_model_calls():
    tf = StubTF()
    cue = await run("Square wave from 0 to 10.", tf)
    assert cue is not None and not cue.extended and tf.calls == 0
    assert cue.origin == "Ultra draft" and cue.start == 10.15


async def test_too_long_draft_is_repaired_by_lightning():
    tf = StubTF("Square wave, 0 to 10.")
    cue = await run("A square wave that rises from 0 up to 10 and then falls back to 0 again repeatedly.", tf)
    assert cue is not None and not cue.extended and tf.calls == 1
    assert "1 Lightning repair" in cue.origin


async def test_unfixable_timing_is_trimmed_before_pausing():
    long = "Square wave from 0 to 10. It repeats across the whole slide with many small dots on it."
    tf = StubTF(long, long)
    cue = await run(long, tf)
    assert cue is not None and not cue.extended and cue.text == "Square wave from 0 to 10."
    assert "trimmed to fit" in cue.origin


async def test_unimportant_fact_that_cannot_fit_is_left_out():
    long = "A very long description of a minor detail that goes on and on without any sentence break at all here."
    tf = StubTF(long, long)
    assert await run(long, tf, importance=2) is None


async def test_tiny_silence_never_produces_a_fragment():
    tiny = Gap(id="g9", start=10.0, end=11.5)
    assert await run("Yellow box.", StubTF(), importance=2, gap=tiny) is None
    cue = await run("Yellow box highlights half a period.", StubTF(), importance=3, gap=tiny)
    assert cue is not None and cue.extended
