from pathlib import Path
from types import SimpleNamespace

from unsaid import correct
from unsaid.config import Settings
from unsaid.ledger import Ledger
from unsaid.schemas import ClaimCheck, Cue, CueText, Gap, Interval, LessonBible, Verification, VisualFact

FACT = VisualFact(
    id="f1",
    t=10.0,
    segment_id="s1",
    fact="Fully mirrored end on the left",
    importance=3,
    already_spoken=False,
    moment_id="",
)
BIBLE = LessonBible(summary="", registry=[], notation=[], visual_facts=[FACT], cue_plan=[], style_notes=[])
GAP = Gap(id="g1", start=10.0, end=15.0)
SPEECH = [Interval(start=0.0, end=10.0), Interval(start=15.0, end=30.0)]


def flagged_cue():
    return Cue(
        id="ad-001",
        gap_id="g1",
        start=10.15,
        end=12.0,
        text="Mirrored end on the right.",
        fact_ids=["f1"],
        verification=Verification(
            claims=[ClaimCheck(claim="mirrored end on the right", verdict="contradicted")],
            identifies_person=False,
        ),
        origin="Ultra draft",
    )


class StubTF:
    def __init__(self, text):
        self.text = text

    async def chat(self, role, messages, **kwargs):
        return SimpleNamespace(parsed=CueText(text=self.text))


async def run(tf, verdict, monkeypatch):
    async def fake_verify(tf_, ledger, video, cue, times, workdir):
        cue.verification = Verification(
            claims=[ClaimCheck(claim=cue.text, verdict=verdict)], identifies_person=False
        )

    monkeypatch.setattr(correct, "verify_cue", fake_verify)
    cue = flagged_cue()
    fixed = await correct.correct_unsupported(
        tf,
        Ledger(),
        Settings(_env_file=None),
        video=Path("v.mp4"),
        cues=[cue],
        bible=BIBLE,
        gaps=[GAP],
        speech=SPEECH,
        observations={},
        words=[],
        context_names=[],
        duration=60.0,
        workdir=Path("."),
    )
    return fixed, cue


async def test_flagged_cue_is_corrected_and_rechecked(monkeypatch):
    fixed, cue = await run(StubTF("Fully mirrored end on the left."), "supported", monkeypatch)
    assert fixed == 1
    assert cue.text == "Fully mirrored end on the left."
    assert cue.corrected_from == "Mirrored end on the right."
    assert cue.tier == "auto" and "corrected after the frame check" in cue.origin


async def test_failed_correction_reverts_and_stays_in_review(monkeypatch):
    fixed, cue = await run(StubTF("Fully mirrored end on the left."), "not_visible", monkeypatch)
    assert fixed == 0
    assert cue.text == "Mirrored end on the right." and cue.corrected_from == ""
    assert cue.tier == "review"
