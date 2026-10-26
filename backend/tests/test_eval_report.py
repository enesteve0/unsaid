from eval.run_eval import aggregate


def clip(clip_id: str, split: str, coverage: float) -> dict:
    row = {
        "cues": 4,
        "talk_over": 0.0,
        "in_silence": 4,
        "pauses": 0,
        "coverage": coverage,
        "checked": 4,
        "unsupported": 1,
        "ungrounded": 0,
        "usd": 0.01,
        "seconds": 60.0,
        "minutes": 2.0,
        "texts": [],
    }
    return {
        "id": clip_id,
        "title": clip_id,
        "split": split,
        "unsaid": row,
        "oneshot": row | {"talk_over": 30.0},
        "failures": [],
    }


def unsaid_metrics(systems: list[dict]) -> dict:
    return next(s for s in systems if s["key"] == "unsaid")["metrics"]


def test_held_out_clips_are_summarized_separately():
    report = aggregate([clip("a", "dev", 1.0), clip("b", "heldout", 0.5), clip("c", "dev", 0.0)])
    heldout, dev = report["splits"]
    assert (heldout["key"], heldout["clips"], dev["key"], dev["clips"]) == ("heldout", 1, "dev", 2)
    assert unsaid_metrics(heldout["systems"])["coverage"] == 0.5
    assert unsaid_metrics(report["systems"])["coverage"] == 0.5  # all three clips together
    assert any("never used to tune" in note for note in report["notes"])


def test_without_held_out_clips_the_report_says_they_are_development_results():
    report = aggregate([clip("a", "dev", 1.0)])
    assert [s["key"] for s in report["splits"]] == ["dev"]
    assert any("development results" in note for note in report["notes"])
