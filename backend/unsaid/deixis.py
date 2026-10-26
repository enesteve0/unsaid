"""Find the moments where a speaker points at something instead of saying it.

Deictic expressions ("as you can see", "this curve", "over here") only make sense to someone who can see the
screen. They are the places a blind student loses information, so they are where Unsaid looks hardest.
"""

from __future__ import annotations

import re

from .schemas import PointingMoment, Word

VISUAL_NOUNS = (
    "curve|line|lines|graph|plot|chart|figure|diagram|picture|image|equation|formula|term|terms|point|points|"
    "region|area|arrow|arrows|box|part|value|values|number|numbers|table|column|row|bar|bars|peak|slope|axis|"
    "shape|circle|square|triangle|node|nodes|edge|edges|matrix|vector|function|map|color|colour|example|slide|"
    "result|results|step|steps|pattern|distribution|histogram|block|layer|layers|code|output|one|ones"
)

STRONG_PATTERNS = [
    r"\bas (?:you|we) can see\b",
    r"\b(?:you|we) can see (?:here|that|this|these|it)\b",
    r"\b(?:look|looking) at (?:this|that|these|those|here|the)\b",
    r"\bover here\b",
    r"\bright here\b",
    r"\bdown here\b",
    r"\bup here\b",
    r"\blike this\b",
    r"\bshown here\b",
    r"\bon (?:the|this) (?:slide|screen|board)\b",
    rf"\b(?:this|that|these|those) (?:{VISUAL_NOUNS})\b",
    r"\bhere (?:we have|is|are|you have)\b",
    r"\bhere's\b",
    r"\bnotice (?:that|how|the|this)\b",
]
WEAK_PATTERNS = [
    r"\bthis\b(?=\s*[,.?!]|$)",
    r"\bhere\b(?=\s*[,.?!]|$)",
    r"\bthere\b(?=\s*[,.?!]|$)",
]

_STRONG = [re.compile(p, re.I) for p in STRONG_PATTERNS]
_WEAK = [re.compile(p, re.I) for p in WEAK_PATTERNS]


def _sentences(words: list[Word]) -> list[list[int]]:
    """Group word indices into sentences using terminal punctuation from the ASR output."""
    groups: list[list[int]] = [[]]
    for i, w in enumerate(words):
        groups[-1].append(i)
        if w.text.rstrip().endswith((".", "?", "!")):
            groups.append([])
    return [g for g in groups if g]


def find_pointing_moments(words: list[Word], min_spacing: float = 2.0) -> list[PointingMoment]:
    moments: list[PointingMoment] = []
    for group in _sentences(words):
        sentence_words = [words[i] for i in group]
        # Map character offsets in the joined sentence back to words, so a match yields a timestamp.
        text, starts = "", []
        for w in sentence_words:
            starts.append(len(text))
            text += w.text.strip() + " "
        text = text.strip()

        def word_at(offset: int, sentence_words=sentence_words, starts=starts) -> Word:
            idx = max(i for i, s in enumerate(starts) if s <= offset)
            return sentence_words[idx]

        found = False
        for pattern in _STRONG:
            for match in pattern.finditer(text):
                w = word_at(match.start())
                moments.append(
                    PointingMoment(id="", t=w.start, phrase=match.group(), sentence=text, strength="strong")
                )
                found = True
        if not found:
            for pattern in _WEAK:
                for match in pattern.finditer(text):
                    w = word_at(match.start())
                    moments.append(
                        PointingMoment(id="", t=w.start, phrase=match.group(), sentence=text, strength="weak")
                    )

    moments.sort(key=lambda m: m.t)
    deduped: list[PointingMoment] = []
    for m in moments:
        if deduped and m.t - deduped[-1].t < min_spacing:
            if m.strength == "strong" and deduped[-1].strength == "weak":
                deduped[-1] = m
            continue
        deduped.append(m)
    for i, m in enumerate(deduped, start=1):
        m.id = f"p{i}"
    return deduped
