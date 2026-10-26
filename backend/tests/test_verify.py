from unsaid.schemas import Cue, LessonBible, VisualFact
from unsaid.verify import check_times


def test_check_frames_include_the_moment_the_speaker_pointed():
    # fourier-a: the planner put the dot plot at 58.3 s, but it appears when the speaker says "these points" at 64.0 s.
    fact = VisualFact(
        id="f9", t=58.33, segment_id="s2", fact="Dot plot", importance=3, already_spoken=False, moment_id="p5"
    )
    bible = LessonBible(
        summary="", registry=[], notation=[], visual_facts=[fact], cue_plan=[], style_notes=[]
    )
    cue = Cue(id="ad-004", gap_id="g5", start=66.42, end=67.92, text="x", fact_ids=["f9"], origin="")
    assert check_times(cue, bible, 100.0, {"p5": 64.0}) == [58.63, 59.63, 64.3]
    assert check_times(cue, bible, 100.0) == [58.63, 59.63]
    assert check_times(cue, bible, 60.0, {"p5": 64.0}) == [58.63, 59.63, 59.9]  # clamped to the video's end


def test_a_fact_resolving_two_moments_gets_both_frames():
    # Ultra wrote "p2,p3" into moment_id in two of three capacitor runs.
    fact = VisualFact(
        id="f1", t=20.0, segment_id="s2", fact="Graph", importance=3, already_spoken=False, moment_id="p2,p3"
    )
    bible = LessonBible(
        summary="", registry=[], notation=[], visual_facts=[fact], cue_plan=[], style_notes=[]
    )
    cue = Cue(id="ad-001", gap_id="g2", start=30.0, end=33.0, text="x", fact_ids=["f1"], origin="")
    assert fact.moment_ids == ["p2", "p3"]
    assert check_times(cue, bible, 100.0, {"p2": 25.0, "p3": 27.4}) == [20.3, 25.3, 27.7]
