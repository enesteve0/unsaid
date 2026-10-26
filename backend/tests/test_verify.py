from unsaid.schemas import Cue, LessonBible, VisualFact
from unsaid.verify import check_times


def bible_of(*facts: VisualFact) -> LessonBible:
    return LessonBible(
        summary="", registry=[], notation=[], visual_facts=list(facts), cue_plan=[], style_notes=[]
    )


def fact(fid: str, t: float, moment_id: str = "") -> VisualFact:
    return VisualFact(
        id=fid, t=t, segment_id="s1", fact="x", importance=3, already_spoken=False, moment_id=moment_id
    )


def test_check_frames_start_with_what_is_on_screen_while_the_cue_is_heard():
    # fourier-a: the planner put the dot plot at 58.3 s; it appears when the speaker says "these points" at 64.0 s.
    cue = Cue(id="ad-004", gap_id="g5", start=66.42, end=67.92, text="x", fact_ids=["f9"], origin="")
    bible = bible_of(fact("f9", 58.33, "p5"))
    assert check_times(cue, bible, 100.0, {"p5": 64.0}) == [58.63, 64.3, 66.72]
    assert check_times(cue, bible, 100.0) == [58.63, 59.63, 66.72]
    assert check_times(cue, bible, 60.0, {"p5": 64.0}) == [58.63, 59.63, 59.9]  # clamped to the video's end


def test_a_fact_resolving_two_moments_gets_both_frames():
    # Ultra wrote "p2,p3" into moment_id in two of three capacitor runs.
    cue = Cue(id="ad-001", gap_id="g2", start=30.0, end=33.0, text="x", fact_ids=["f1"], origin="")
    f1 = fact("f1", 20.0, "p2,p3")
    assert f1.moment_ids == ["p2", "p3"]
    assert check_times(cue, bible_of(f1), 100.0, {"p2": 25.0, "p3": 27.4}) == [25.3, 27.7, 30.3]


def test_no_frame_after_the_description_ends():
    # capacitor: "voltage curve ... falls exponentially" is heard at 15.5-22.6 s; the graph is blank until about 24 s.
    cue = Cue(id="ad-001", gap_id="g1", start=15.5, end=22.6, text="x", fact_ids=["f1"], origin="")
    assert check_times(cue, bible_of(fact("f1", 24.0)), 100.0) == [15.8]
    paused = Cue(
        id="ext-002", gap_id=None, start=86.26, end=86.76, text="x", fact_ids=["f1"], origin="", extended=True
    )
    assert check_times(paused, bible_of(fact("f1", 73.0, "p5")), 100.0, {"p5": 86.02}) == [73.3, 86.32, 86.56]
