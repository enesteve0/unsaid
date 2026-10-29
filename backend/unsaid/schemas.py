"""Data shapes shared by the pipeline stages.

Classes used as `schema=` for Token Factory structured output keep every field required and avoid defaults,
because strict JSON-schema decoding requires all properties.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class Word(BaseModel):
    text: str
    start: float
    end: float


class Interval(BaseModel):
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


class Gap(Interval):
    id: str


class Segment(BaseModel):
    id: str
    start: float
    end: float
    keyframes: list[float] = Field(default_factory=list)
    moment_frames: list[float] = Field(default_factory=list)  # just after each pointing moment in the segment


class PointingMoment(BaseModel):
    id: str
    t: float
    phrase: str
    sentence: str
    strength: Literal["strong", "weak"]
    segment_id: str | None = None


# ---- Nemotron 3.5 Super VL: what each segment shows -------------------------------------------------------------

VisualKind = Literal[
    "chart", "equation", "diagram", "code", "table", "photo", "demo", "handwriting", "text", "other"
]


class VisualElement(BaseModel):
    kind: VisualKind
    label: str = Field(description="Short handle, e.g. 'loss curve' or 'Bayes rule'")
    description: str = Field(description="What it shows, objectively, in present tense")
    values: list[str] = Field(description="Numbers, axis labels and data labels exactly as printed")


class TimedEvent(BaseModel):
    t: float = Field(description="Seconds from the start of the whole video")
    description: str


class SegmentFacts(BaseModel):
    on_screen_text: list[str] = Field(description="Every legible line of text, verbatim")
    visuals: list[VisualElement]
    events: list[TimedEvent] = Field(description="Actions, pointing, slide builds, writing on the board")
    setting: str
    people: list[str] = Field(
        description="Appearance and action only; a name only if it is printed on screen"
    )


# ---- Nemotron 3 Nano: does a pointing phrase refer to something on screen? ---------------------------------------


class PointerResolution(BaseModel):
    moment_id: str
    refers_to_visual: bool
    target: str = Field(description="Label of the visual element referred to, or empty")
    unsaid: str = Field(description="The visual information the speaker relies on but does not say, or empty")
    confidence: float


class PointerResolutions(BaseModel):
    items: list[PointerResolution]


# ---- Nemotron 3 Ultra: the lesson bible ----------------------------------------------------------------------------


class RegistryName(BaseModel):
    name: str
    source: Literal["slide", "speech", "context"]


class VisualFact(BaseModel):
    id: str
    t: float = Field(description="Seconds from the start of the video when the fact becomes visible")
    segment_id: str
    fact: str
    importance: int = Field(ge=1, le=3, description="3 = needed to follow the lecture")
    already_spoken: bool
    moment_id: str = Field(description="Pointing moment this fact resolves, or empty")

    @property
    def moment_ids(self) -> list[str]:
        """Ultra sometimes writes several ids into moment_id ("p2,p3")."""
        return [m for m in re.split(r"[,;\s]+", self.moment_id) if m]


class CuePlan(BaseModel):
    gap_id: str
    fact_ids: list[str]
    draft: str = Field(description="The description to speak, within the silence's word budget")


class LessonBible(BaseModel):
    summary: str
    registry: list[RegistryName]
    notation: list[str]
    visual_facts: list[VisualFact]
    cue_plan: list[CuePlan]
    style_notes: list[str]


# ---- Nemotron 3.5 Lightning: one cue -----------------------------------------------------------------------------


class CueText(BaseModel):
    text: str


# ---- Verifier (Super VL) -------------------------------------------------------------------------------------------


class ClaimCheck(BaseModel):
    claim: str
    verdict: Literal["supported", "contradicted", "not_visible"]
    observed: str = Field(
        default="", description="For a contradicted claim, what the frames show instead; else empty"
    )


class Verification(BaseModel):
    claims: list[ClaimCheck] = Field(description="Every factual claim in the description, checked one by one")
    identifies_person: bool = Field(
        description="True if the description names a person or says who someone is"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supported(self) -> bool:
        return all(c.verdict == "supported" for c in self.claims)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unsupported_claims(self) -> list[str]:
        return [f"{c.claim} ({c.verdict.replace('_', ' ')})" for c in self.claims if c.verdict != "supported"]


class TipText(BaseModel):
    moment_id: str
    suggestion: str


class TipBatch(BaseModel):
    items: list[TipText]


class ContextNames(BaseModel):
    title: str
    people: list[str] = Field(description="People credited as presenters or authors on the page")
    terms: list[str] = Field(description="Proper nouns and product names that may appear in the video")


# ---- Pipeline outputs ----------------------------------------------------------------------------------------------

Tier = Literal["auto", "review", "never"]


class Source(BaseModel):
    url: str
    title: str
    request_id: str
    used_for: str


class Cue(BaseModel):
    id: str
    gap_id: str | None
    start: float
    end: float
    text: str
    extended: bool = False
    fact_ids: list[str] = Field(default_factory=list)
    moment_ids: list[str] = Field(default_factory=list)
    gate_failures: list[str] = Field(default_factory=list)
    gate_warnings: list[str] = Field(default_factory=list)
    repairs: int = 0
    origin: str = ""
    corrected_from: str = ""
    verification: Verification | None = None
    tier: Tier = "review"
    sources: list[Source] = Field(default_factory=list)

    @property
    def published(self) -> bool:
        """Spoken and exported: not withheld, and no hard rule still broken after repair (a person can fix it)."""
        return self.tier != "never" and not self.gate_failures


class Tip(BaseModel):
    moment_id: str
    t: float
    said: str
    suggestion: str
