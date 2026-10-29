from eval.run_eval import aggregate


def clip(clip_id: str, split: str, coverage: float, labels: int = 4) -> dict:
    row = {
        "cues": 4,
        "talk_over": 0.0,
        "in_silence": 4,
        "pauses": 0,
        "coverage": coverage,
        "labels": labels,
        "covered": coverage * labels,
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


def test_repeated_runs_pool_metrics_but_count_each_clip_once():
    first, second = clip("a", "dev", 1.0) | {"run": 1}, clip("a", "dev", 0.5) | {"run": 2}
    report = aggregate([first, second])
    assert (report["clips"], report["minutes"]) == (1, 2.0)
    assert unsaid_metrics(report["systems"])["coverage"] == 0.75


def test_coverage_is_the_share_of_all_labelled_moments_not_a_mean_of_clips():
    report = aggregate([clip("a", "dev", 1.0, labels=1), clip("b", "dev", 0.0, labels=7)])
    assert unsaid_metrics(report["systems"])["coverage"] == 1 / 8


def test_a_partial_evaluation_keeps_the_finished_clips_and_lists_the_skipped_ones():
    from eval.run_eval import build_report

    rows = [
        clip("a", "dev", 1.0) | {"run": 1},
        {"id": "b", "title": "b", "skipped": "TimeoutError: ", "run": 1},
    ]
    report = build_report(rows, repeat=1, provider="tokenfactory")
    assert report["clips"] == 1 and report["provider"] == "tokenfactory"
    assert report["skipped"] == [{"id": "b", "run": 1, "reason": "TimeoutError: "}]
    assert build_report(rows[1:], repeat=1, provider="tokenfactory")["available"] is False
