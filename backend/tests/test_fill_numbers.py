import importlib.util
from pathlib import Path

from eval.run_eval import aggregate
from tests.test_eval_report import clip

spec = importlib.util.spec_from_file_location(
    "fill_numbers", Path(__file__).resolve().parents[2] / "scripts" / "fill_numbers.py"
)
fill_numbers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fill_numbers)


def test_report_numbers_are_formatted_and_the_coverage_gap_is_explained():
    report = aggregate([clip("fourier-a", "dev", 0.5), clip("yellowstone", "heldout", 0.5)])
    report["systems"][0]["metrics"]["coverage"] = 0.75  # one-shot covers more, as on the prototype runs
    values = fill_numbers.report_values(report)
    assert values["unsaid.talk_over"] == "0.0 s" and values["oneshot.talk_over"] == "15.0 s"
    assert values["unsaid.usd_per_min"] == "$0.0050"
    assert values["dev_clips_word"] == "One" and values["heldout_clips"] == "1"
    assert "one-shot approach covered more pointing moments (75% against 50%)" in values["coverage_sentence"]
    assert "held-out clips alone" in values["heldout_sentence"]


def test_missing_measurements_stay_visible():
    text, missing = fill_numbers.fill("cost {{usd_per_min}} on {{clips}} clips", {"clips": "9"})
    assert text == "cost {{usd_per_min}} on 9 clips" and missing == ["usd_per_min"]


def test_text_work_on_ultra_alone_is_compared_without_the_vision_calls():
    sample = {
        "ledger": {
            "summary": {
                "total_usd": 0.10,
                "ultra_only_usd": 0.16,
                "by_model": {
                    "Nemotron 3.5 Super VL": {"cost_usd": 0.04},
                    "Nemotron 3 Ultra": {"cost_usd": 0.05},
                    "Nemotron 3.5 Lightning": {"cost_usd": 0.01},
                },
            }
        }
    }
    values = fill_numbers.sample_values(sample)
    assert values["ultra_only_phrase"] == "2.0 times as much"  # text: $0.06 actual, $0.12 on Ultra
    assert (
        values["cost_split"] == "Nemotron 3 Ultra 50%, Nemotron 3.5 Super VL 40%, Nemotron 3.5 Lightning 10%"
    )
