from unsaid.gates import (
    check_cue,
    estimate_seconds,
    numbers_in,
    numbers_seen,
    says_nothing,
    spoken_word_count,
    unknown_names,
    vocabulary,
)
from unsaid.schemas import Interval

SPEECH = [Interval(start=0.0, end=10.0), Interval(start=15.0, end=20.0)]


def run(text, start=10.2, window_end=15.0, allowed=None, vocab=None, extended=False):
    return check_cue(
        text,
        start,
        window_end,
        speech=SPEECH,
        allowed_numbers=allowed or set(),
        known_vocabulary=vocab or set(),
        words_per_second=2.6,
        guard=0.15,
        extended=extended,
    )


def test_numbers_are_normalized():
    assert numbers_in("Error falls from 40% to 5.0% across 2,000 steps") == {"40", "5", "2000"}


def test_spoken_word_count_expands_numerals():
    assert spoken_word_count("2,000") == 2
    assert spoken_word_count("40%") == 2
    assert spoken_word_count("150") == 3
    assert spoken_word_count("0.05") == 4


def test_short_cue_in_silence_passes():
    report = run("Line chart: error falls from 40% to 5%.", allowed={"40", "5"})
    assert report.passed, report.failures


def test_cue_that_runs_into_speech_fails():
    report = run("A long description that keeps going well beyond the silence and into the next sentence.")
    assert any(f.startswith("too_long") for f in report.failures)
    assert "talks_over_speech" in report.failures


def test_extended_cues_skip_timing_checks():
    report = run(
        "A long description that keeps going well beyond the silence and into the next sentence.",
        extended=True,
    )
    assert report.passed


def test_banned_phrasing():
    report = run("We see a red arrow.")
    assert "banned_phrase: we see" in report.failures


def test_number_not_on_screen_fails_but_small_counts_pass():
    assert "number_not_on_screen: 73" in run("Accuracy reaches 73%.").failures
    assert run("3 arrows point left.").passed


def test_unknown_name_fails_known_name_passes():
    vocab = vocabulary(["Bayes rule", "posterior"])
    assert unknown_names("The slide titles it Bayes rule.", vocab) == []
    # The sentence-initial word is exempt; "Smith" is printed nowhere and was never spoken.
    assert unknown_names("Professor Smith points at it.", vocab) == ["Smith"]


def test_estimate_seconds_counts_pauses():
    assert estimate_seconds("One, two.", 2.0) > estimate_seconds("One two.", 2.0)


def test_warnings_do_not_fail():
    report = run("The curve appears to flatten.")
    assert report.passed
    assert "speculation" in report.warnings


def test_extended_cues_are_limited_to_thirty_words():
    words = " ".join(["word"] * 33) + "."
    report = run(words, extended=True)
    assert not report.passed and report.failures[0].startswith("too_long: 33 spoken words")


def test_numbers_seen_include_values_read_off_charts():
    # capacitor: the fact said "~13 V" but only "13.40" was printed; the review editor refused 13.4 before.
    facts = {
        "on_screen_text": ["Voltage (V)"],
        "visuals": [{"description": "Line graph", "values": ["13.40", "14.89"]}],
        "events": [{"description": "Pointer at 20 s"}],
    }
    assert {"13.4", "14.89", "20"} <= numbers_seen([facts], "about two volts")


def test_a_description_must_say_what_it_shows():
    assert run("Title card shows title.").failures == ["says_nothing"]
    assert says_nothing("Slide displays text.") and says_nothing("The screen shows a new image.")
    assert not says_nothing("Title: Harmonic Analyzer, Analysis.")
    assert not says_nothing("Yellow box around the left half.")


def test_a_stored_cue_rechecks_cleanly_despite_millisecond_rounding():
    speech = [Interval(start=0.0, end=12.3454), Interval(start=16.0, end=20.0)]
    start = round(12.3454 + 0.15, 3)  # 12.495, a hair before speech end + guard
    report = check_cue(
        "Gears turn behind glass.",
        start,
        16.0,
        speech=speech,
        allowed_numbers=set(),
        known_vocabulary=set(),
        words_per_second=2.5,
        guard=0.15,
    )
    assert "talks_over_speech" not in report.failures


def test_names_match_whole_words_only():
    from unsaid.gates import mentions

    assert mentions("Li", "Figure from Li et al.") and not mentions("Li", "A line rises.")
    assert not mentions("Chang", "The slope changes.") and mentions(
        "Hammack", "Bill Hammack turns the crank."
    )


def test_a_title_does_not_hide_the_name_after_it():
    assert unknown_names("Photo of Dr. Smith at the board.", set()) == ["Smith"]
    assert unknown_names("The pulse lasts 200 ms. Hand turns the crank.", set()) == []
    assert unknown_names("The answer is no. Hand turns the crank.", set()) == []
