import xml.etree.ElementTree as ET

from unsaid.export import (
    captions_srt,
    captions_vtt,
    descriptions_vtt,
    fcpxml_markers,
    timestamp,
    transcript_html,
)
from unsaid.ledger import Ledger, LedgerEntry, cost_usd
from unsaid.schemas import Cue, Word


def cue(i, start, text, tier="auto", extended=False):
    return Cue(
        id=f"d{i}", gap_id=f"g{i}", start=start, end=start + 2, text=text, tier=tier, extended=extended
    )


def test_timestamp_format():
    assert timestamp(3723.456) == "01:02:03.456"
    assert timestamp(1.5, ",") == "00:00:01,500"


def test_descriptions_vtt_skips_never_tier_and_marks_extended():
    vtt = descriptions_vtt(
        [cue(1, 1.0, "Line chart."), cue(2, 5.0, "Face.", tier="never"), cue(3, 9.0, "Long.", extended=True)]
    )
    assert vtt.startswith("WEBVTT")
    assert "Line chart." in vtt and "Face." not in vtt
    assert "NOTE extended description d3" in vtt
    assert "00:00:01.000 --> 00:00:03.000" in vtt


def test_captions_and_transcript():
    words = [
        Word(text=w, start=i * 0.5, end=i * 0.5 + 0.4)
        for i, w in enumerate(["Hello", "there.", "This", "is", "a", "test."])
    ]
    assert "Hello there." in captions_vtt(words)
    assert captions_srt(words).startswith("1\n00:00:00,000 -->")
    html_doc = transcript_html(words, [cue(1, 1.2, "A slide with a table.")], "Demo")
    assert html_doc.index("Hello there.") < html_doc.index("A slide with a table.")


def test_fcpxml_is_well_formed_with_markers():
    xml = fcpxml_markers(
        [cue(1, 1.0, "A & B"), cue(2, 4.25, "Next")],
        name="Lecture",
        duration=10.0,
        fps=30,
        width=1280,
        height=720,
    )
    root = ET.fromstring(xml.split("\n", 2)[2])  # skip XML declaration and DOCTYPE
    markers = root.findall(".//marker")
    assert [m.get("value") for m in markers] == ["A & B", "Next"]
    assert markers[1].get("start") == "64/15s"  # 4.25 s at 30 fps rounds to frame 128 = 128/30 s


def test_cost_and_counterfactual():
    assert (
        cost_usd("nvidia/Nemotron-3-Ultra-550b-a55b", 20_000, 18_000, 1_000)
        == (2_000 * 1.0 + 18_000 * 0.12 + 1_000 * 3.0) / 1e6
    )
    ledger = Ledger()
    ledger.add(
        LedgerEntry(
            stage="write",
            role="fast",
            model="nvidia/Nemotron-3_5-Lightning",
            thinking=False,
            prompt_tokens=1000,
            completion_tokens=100,
        )
    )
    ledger.add(
        LedgerEntry(
            stage="watch",
            role="vision",
            model="nvidia/Nemotron-3.5-Super-VL",
            thinking=False,
            prompt_tokens=10_000,
            completion_tokens=500,
        )
    )
    summary = ledger.summary(video_minutes=1.0, accepted_cues=2)
    assert summary["calls"] == 2
    # Lightning text step costs far less than it would on Ultra; the vision step has no Ultra alternative.
    assert summary["ultra_only_usd"] > summary["total_usd"]
    assert summary["usd_per_accepted_cue"] == round(summary["total_usd"] / 2, 6)


def test_cue_text_is_escaped_for_webvtt_and_held_back_cues_are_left_out():
    cues = [
        Cue(id="ad-1", gap_id="g1", start=1, end=2, text="p < 0.05 for R&D\n--> next", tier="auto"),
        Cue(
            id="ad-2",
            gap_id="g2",
            start=3,
            end=4,
            text="Accuracy 42%.",
            tier="review",
            gate_failures=["number_not_on_screen: 42"],
        ),
    ]
    vtt = descriptions_vtt(cues)
    assert "p &lt; 0.05 for R&amp;D → next" in vtt and "42" not in vtt


def test_fcpxml_survives_a_frame_rate_below_one():
    xml = fcpxml_markers([], name="t", duration=10, fps=0.4, width=640, height=360)
    ET.fromstring(xml.split("\n", 2)[2])


def test_catalog_models_are_priced_as_their_token_factory_equivalents():
    assert cost_usd("nvidia/nemotron-3-ultra-550b-a55b", 1_000_000, 0, 0) == cost_usd(
        "nvidia/Nemotron-3-Ultra-550b-a55b", 1_000_000, 0, 0
    )
    ledger = Ledger()
    ledger.add(
        LedgerEntry(
            stage="watch",
            role="vision",
            model="nvidia/nemotron-3.5-super-vl-120b-a12b",
            thinking=False,
            prompt_tokens=1000,
        )
    )
    assert "Nemotron 3.5 Super VL" in ledger.summary()["by_model"]
