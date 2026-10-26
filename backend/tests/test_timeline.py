from unsaid.deixis import find_pointing_moments
from unsaid.schemas import Word
from unsaid.segments import attach_moments, build_segments, find_gaps, gap_after, speech_intervals


def words_from(text: str, start: float = 0.0, step: float = 0.4) -> list[Word]:
    out = []
    t = start
    for token in text.split():
        out.append(Word(text=token, start=round(t, 2), end=round(t + step * 0.8, 2)))
        t += step
    return out


def test_speech_intervals_merge_close_words():
    ws = [
        Word(text="a", start=0, end=0.3),
        Word(text="b", start=0.5, end=0.8),
        Word(text="c", start=3.0, end=3.2),
    ]
    intervals = speech_intervals(ws)
    assert [(i.start, i.end) for i in intervals] == [(0, 0.8), (3.0, 3.2)]


def test_gaps_include_leading_and_trailing_silence():
    ws = [Word(text="a", start=2.0, end=2.5), Word(text="b", start=6.0, end=6.5)]
    gaps = find_gaps(speech_intervals(ws), duration=10.0, min_gap=1.2)
    assert [(g.id, g.start, g.end) for g in gaps] == [("g1", 0.0, 2.0), ("g2", 2.5, 6.0), ("g3", 6.5, 10.0)]


def test_strong_pointing_phrases_are_found_with_timestamps():
    ws = words_from("So the model trains. As you can see, this curve drops quickly. Then we stop.")
    moments = find_pointing_moments(ws)
    assert moments, "expected at least one pointing moment"
    assert moments[0].strength == "strong"
    assert moments[0].phrase.lower().startswith("as you can see")
    assert moments[0].t == ws[4].start  # "As"


def test_weak_phrase_only_when_no_strong_one():
    ws = words_from("Put the value here. Then continue with the proof.")
    moments = find_pointing_moments(ws)
    assert [m.strength for m in moments] == ["weak"]


def test_segments_respect_min_and_max_length():
    segs = build_segments([1.0, 10.0, 11.0, 130.0], duration=140.0, min_len=3.0, max_len=60.0)
    assert segs[0].start == 0.0 and segs[-1].end == 140.0
    assert all(s.end - s.start <= 60.0 + 1e-6 for s in segs)
    assert all(s.end - s.start >= 3.0 - 1e-6 for s in segs)


def test_attach_moments_adds_keyframe_after_pointing():
    segs = build_segments([], duration=20.0)
    ws = words_from("Look at this graph now.", start=5.0)
    moments = find_pointing_moments(ws)
    attach_moments(moments, segs)
    assert moments[0].segment_id == "s1"
    assert round(moments[0].t + 0.8, 2) in segs[0].keyframes


def test_gap_after_finds_next_silence():
    ws = [Word(text="a", start=0.0, end=4.0), Word(text="b", start=7.0, end=9.0)]
    gaps = find_gaps(speech_intervals(ws), duration=12.0, min_gap=1.2)
    assert gap_after(3.0, gaps).id == "g1"
    assert gap_after(30.0, gaps) is None
