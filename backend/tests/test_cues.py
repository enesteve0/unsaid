from types import SimpleNamespace

from unsaid.bible import word_budget
from unsaid.config import Settings
from unsaid.cues import CueContext, pause_point, trim_candidates, write_all, write_cue
from unsaid.ledger import Ledger
from unsaid.schemas import CuePlan, CueText, Gap, Interval, LessonBible, VisualFact, Word

SETTINGS = Settings(_env_file=None)
SPEECH = [Interval(start=0.0, end=10.0), Interval(start=13.0, end=30.0)]  # a 3 s silence from 10 to 13
CONTEXT = CueContext(allowed_numbers={"10", "0"}, vocabulary=set(), on_screen_text=[])
BIBLE = LessonBible(summary="", registry=[], notation=[], visual_facts=[], cue_plan=[], style_notes=[])


def fact(importance=3, moment_id="p1"):
    return VisualFact(
        id="f1",
        t=9.5,
        segment_id="s1",
        fact="Square wave from 0 to 10",
        importance=importance,
        already_spoken=False,
        moment_id=moment_id,
    )


class StubTF:
    """Answers every Lightning call with the next scripted text."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = 0

    async def chat(self, role, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(parsed=CueText(text=self.texts.pop(0)))


GAP = Gap(id="g1", start=10.0, end=13.0)


async def run(draft, tf, importance=3, gap=GAP, moment_id="p1"):
    return await write_cue(
        tf,
        Ledger(),
        SETTINGS,
        cue_id="001",
        facts=[fact(importance, moment_id)],
        draft=draft,
        gap=gap,
        speech=SPEECH,
        context=CONTEXT,
        bible=BIBLE,
        allowed_names=[],
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
    assert await run(long, tf, importance=2, moment_id="") is None


async def test_tiny_silence_never_produces_a_fragment():
    tiny = Gap(id="g9", start=10.0, end=11.5)
    assert await run("Yellow box.", StubTF(), importance=2, gap=tiny, moment_id="") is None
    cue = await run("Yellow box highlights half a period.", StubTF(), importance=3, gap=tiny)
    assert cue is not None and cue.extended


async def test_what_the_speaker_points_at_pauses_the_video_rather_than_being_left_out():
    tiny = Gap(id="g9", start=10.0, end=11.5)
    cue = await run("Yellow box highlights half a period.", StubTF(), importance=2, gap=tiny, moment_id="p1")
    assert cue is not None and cue.extended


async def test_a_pointing_description_never_moves_to_a_silence_too_short_for_one():
    # The only free silence near the pointing moment holds fewer than four words: pause instead of using it.
    silences = [Gap(id="g1", start=40.0, end=43.5), Gap(id="g2", start=11.0, end=12.4)]
    cues = await place(
        [CuePlan(gap_id="g1", fact_ids=["f2"], draft=DRAFT)],
        [plan_fact("f2", 9.0, "p2")],
        silences,
        {"p2": 10.0},
    )
    assert cues["f2"].extended and cues["f2"].gap_id is None


def words_of(*spans):
    return [Word(text=text, start=start, end=end) for text, start, end in spans]


# From the USGS clip: two back-to-back sentences, each pointing "here" at the map.
SENTENCES = words_of(
    ("This", 84.26, 84.34),
    ("is", 84.34, 84.5),
    ("deep", 85.7, 86.02),
    ("here.", 86.02, 86.26),
    ("This", 86.26, 86.34),
    ("is", 86.34, 86.5),
    ("deep", 87.86, 88.26),
    ("right", 88.26, 88.42),
    ("here.", 88.42, 88.9),
)


def test_pause_waits_for_the_end_of_the_sentence():
    assert pause_point(86.02, SENTENCES) == 86.26
    assert pause_point(88.26, SENTENCES) == 88.9
    assert pause_point(80.0, SENTENCES) == 80.0  # nobody speaking yet: pause right away
    run_on = words_of(*((f"word{i}", 10.0 + i, 10.9 + i) for i in range(12)))
    assert pause_point(10.5, run_on) == 10.9  # no sentence end within 6 s: end of the current word


async def test_paused_description_waits_for_the_pointing_moment():
    pointed = VisualFact(
        id="f5",
        t=73.0,
        segment_id="s3",
        fact="Pointer on the shallow area",
        importance=3,
        already_spoken=False,
        moment_id="p5",
    )
    bible = BIBLE.model_copy(
        update={
            "visual_facts": [pointed],
            "cue_plan": [
                CuePlan(gap_id="extended", fact_ids=["f5"], draft="Pointer on the shallow area by the beach.")
            ],
        }
    )
    cues = await write_all(
        StubTF(),
        Ledger(),
        SETTINGS,
        bible=bible,
        gaps=[],
        speech=[],
        observations={},
        words=SENTENCES,
        context_names=[],
        moment_times={"p5": 86.02},
    )
    assert len(cues) == 1 and cues[0].extended
    assert cues[0].start == 86.26  # after "...deep here.", not at 73 s when the map first appeared


def plan_fact(fid, t, moment_id=""):
    return VisualFact(
        id=fid,
        t=t,
        segment_id="s1",
        fact="Front plate",
        importance=3,
        already_spoken=False,
        moment_id=moment_id,
    )


async def place(plans, facts, gaps, moment_times):
    bible = BIBLE.model_copy(update={"visual_facts": facts, "cue_plan": plans})
    cues = await write_all(
        StubTF(),
        Ledger(),
        SETTINGS,
        bible=bible,
        gaps=gaps,
        speech=[],
        observations={},
        words=[],
        context_names=[],
        moment_times=moment_times,
    )
    return {c.fact_ids[0]: c for c in cues}


SILENCES = [
    Gap(id="g1", start=0.0, end=3.5),
    Gap(id="g2", start=18.0, end=21.5),
    Gap(id="g3", start=40.0, end=43.5),
]
DRAFT = "Front plate shows a faint waveform."


async def test_pointing_description_moves_to_a_silence_near_the_moment():
    # Ultra put "the function plotted here on the front" (17.7 s) into the first silence, 17 s early.
    cues = await place(
        [CuePlan(gap_id="g1", fact_ids=["f2"], draft=DRAFT)],
        [plan_fact("f2", 0.0, "p2")],
        SILENCES,
        {"p2": 17.7},
    )
    assert cues["f2"].gap_id == "g2" and not cues["f2"].extended


async def test_pointing_description_pauses_when_the_nearby_silence_is_taken():
    plans = [
        CuePlan(gap_id="g1", fact_ids=["f2"], draft=DRAFT),
        CuePlan(gap_id="g2", fact_ids=["f3"], draft=DRAFT),  # placed well by Ultra: keeps its silence
    ]
    cues = await place(plans, [plan_fact("f2", 0.0, "p2"), plan_fact("f3", 17.0)], SILENCES, {"p2": 17.7})
    assert cues["f3"].gap_id == "g2"
    assert cues["f2"].extended and cues["f2"].start == 17.7


async def test_description_without_a_pointing_moment_keeps_its_silence():
    cues = await place(
        [CuePlan(gap_id="g1", fact_ids=["f1"], draft=DRAFT)], [plan_fact("f1", 0.0)], SILENCES, {}
    )
    assert cues["f1"].gap_id == "g1"


def test_budget_leaves_room_for_punctuation_pauses():
    # 3.0 s silence: 0.15 s guard each side, 0.3 s voice lead, 0.24 s for two punctuation pauses -> 2.16 s at 2.5 w/s.
    assert word_budget(GAP, SETTINGS) == 5


async def test_a_draft_that_only_punctuation_makes_too_long_is_told_so():
    class Recording(StubTF):
        async def chat(self, role, messages, **kwargs):
            self.messages = messages
            return await super().chat(role, messages, **kwargs)

    tf = Recording("Wave flat low high flat.")
    cue = await run("Wave: flat, low, high, flat.", tf)  # 5 words fit the budget; four pauses do not
    assert cue is not None and cue.text == "Wave flat low high flat."
    assert "pauses at its commas" in tf.messages[-1]["content"]


async def test_paused_description_waits_until_the_thing_is_on_screen():
    # laser: a fact that appears at 91.7 s was linked to a phrase at 76.3 s; the pause came 10 s before the rod.
    rod = VisualFact(
        id="f5", t=91.7, segment_id="s3", fact="Rod", importance=3, already_spoken=False, moment_id="p3"
    )
    bible = BIBLE.model_copy(
        update={
            "visual_facts": [rod],
            "cue_plan": [CuePlan(gap_id="extended", fact_ids=["f5"], draft="Pink rod.")],
        }
    )
    cues = await write_all(
        StubTF(),
        Ledger(),
        SETTINGS,
        bible=bible,
        gaps=[],
        speech=[],
        observations={},
        words=[],
        context_names=[],
        moment_times={"p3": 76.3},
    )
    assert cues[0].extended and cues[0].start == 91.7


async def test_pointing_description_never_starts_before_the_thing_is_on_screen():
    # Pointing at 12 s, the thing shows at 20 s: the 17.5 s silence is within 10 s of the pointing but too early.
    silences = [Gap(id="g1", start=17.5, end=21.5), Gap(id="g2", start=20.5, end=24.0)]
    cues = await place(
        [CuePlan(gap_id="g1", fact_ids=["f2"], draft=DRAFT)],
        [plan_fact("f2", 20.0, "p2")],
        silences,
        {"p2": 12.0},
    )
    assert cues["f2"].gap_id == "g2" and cues["f2"].start >= 20.0


async def test_pointing_description_never_starts_more_than_ten_seconds_after_the_pointing():
    # The thing shows 8 s after the pointing; a silence 16 s after the pointing is too late.
    silences = [Gap(id="g1", start=26.0, end=30.0)]
    cues = await place(
        [CuePlan(gap_id="g1", fact_ids=["f2"], draft=DRAFT)],
        [plan_fact("f2", 18.0, "p2")],
        silences,
        {"p2": 10.0},
    )
    assert cues["f2"].extended and cues["f2"].start == 18.0


async def test_an_unimportant_fact_never_pauses_the_video():
    unimportant = plan_fact("f1", 5.0).model_copy(update={"importance": 1})
    cues = await place(
        [CuePlan(gap_id="extended", fact_ids=["f1"], draft=DRAFT)], [unimportant], SILENCES, {}
    )
    assert cues == {}


def test_trimming_never_leaves_a_fragment():
    assert list(trim_candidates("Crank, bars, gears, and a chain drive the rods up and down.")) == []
    assert list(trim_candidates("Yellow box. A pink rod rises on the left side of the machine.")) == []
    assert list(trim_candidates("Square wave from 0 to 10. A bracket marks one period.")) == [
        "Square wave from 0 to 10."
    ]


async def test_a_pause_never_interrupts_another_description():
    plans = [
        CuePlan(gap_id="g2", fact_ids=["f1"], draft=DRAFT),
        CuePlan(gap_id="extended", fact_ids=["f2"], draft="Pink rod."),
    ]
    cues = await place(plans, [plan_fact("f1", 17.0), plan_fact("f2", 18.5)], SILENCES, {})
    inline, paused = cues["f1"], cues["f2"]
    assert not inline.extended and paused.extended and paused.start == inline.end
