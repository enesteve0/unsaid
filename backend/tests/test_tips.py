import json
from types import SimpleNamespace

from unsaid.ledger import Ledger
from unsaid.schemas import (
    ClaimCheck,
    Cue,
    LessonBible,
    PointerResolution,
    PointingMoment,
    TipBatch,
    Verification,
    VisualFact,
)
from unsaid.tips import lecturer_tips


class Recording:
    async def chat(self, role, messages, **kwargs):
        self.items = json.loads(messages[-1]["content"])
        return SimpleNamespace(parsed=TipBatch(items=[]))


def fact(fid: str, text: str) -> VisualFact:
    return VisualFact(
        id=fid, t=10.0, segment_id="s1", fact=text, importance=3, already_spoken=False, moment_id="p1"
    )


async def test_tips_leave_out_what_the_frames_contradict_and_use_corrections():
    # laser: the frame shows the fully mirrored end on the left, but the plan said right.
    moment = PointingMoment(
        id="p1", t=9.0, phrase="here", sentence="This end here.", strength="weak", segment_id="s1"
    )
    bible = LessonBible(
        summary="",
        registry=[],
        notation=[],
        visual_facts=[
            fact("f1", "Fully mirrored end on the right."),
            fact("f2", "Rod is pink."),
            fact("f3", "11 dots."),
        ],
        cue_plan=[],
        style_notes=[],
    )
    contradicted = Verification(
        claims=[ClaimCheck(claim="on the right", verdict="contradicted")], identifies_person=False
    )
    cues = [
        Cue(
            id="ad-001",
            gap_id="g1",
            start=10.0,
            end=12.0,
            text="x",
            fact_ids=["f1"],
            origin="",
            verification=contradicted,
        ),
        Cue(
            id="ad-002",
            gap_id="g2",
            start=20.0,
            end=22.0,
            text="10 dots.",
            fact_ids=["f3"],
            origin="",
            corrected_from="11 dots.",
        ),
    ]
    resolutions = {
        "p1": PointerResolution(
            moment_id="p1", refers_to_visual=True, target="rod", unsaid="", confidence=0.9
        )
    }
    tf = Recording()
    await lecturer_tips(tf, Ledger(), [moment], resolutions, bible, cues)
    assert tf.items[0]["visual_facts"] == ["Rod is pink.", "10 dots."]
