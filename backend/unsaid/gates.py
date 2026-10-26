"""Deterministic audio-description rules.

Models write the descriptions; code decides whether a description may be used. A cue passes only if it:

* starts inside a silence and finishes before speech resumes (with a guard band),
* uses none of the phrasings describers avoid ("we see", "the image shows", ...),
* states no number that is not printed in the segment it describes,
* names nothing that is not on screen, in the speech, or in the verified registry.

Tense and speculation are reported as warnings rather than failures.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .schemas import Interval

NUMBER = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?%?")
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*|\d[\d,]*(?:\.\d+)?%?")
PAUSE_PER_MARK = 0.12  # seconds a voice pauses at a comma, colon, semicolon or dash

BANNED = {
    "we see": re.compile(r"\bwe (?:can |now )?see\b", re.I),
    "you see": re.compile(r"\byou (?:can |now )?see\b", re.I),
    "I see": re.compile(r"\bI (?:can )?see\b"),
    "the image shows": re.compile(
        r"\bthe (?:image|video|frame|screen|picture|clip) (?:shows|displays|depicts)\b", re.I
    ),
    "in this video": re.compile(r"\bin this (?:image|video|frame|clip|picture)\b", re.I),
}
SPECULATION = re.compile(r"\b(?:seems?|appears?|probably|maybe|perhaps|might be|likely)\b", re.I)
PAST_TENSE = re.compile(r"\b(?:was|were|had|did)\b", re.I)

# Capitalised words that are not names: sentence starters, function words, units and common lecture vocabulary.
COMMON_CAPITALISED = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "on",
    "in",
    "at",
    "to",
    "from",
    "with",
    "and",
    "or",
    "but",
    "of",
    "for",
    "by",
    "as",
    "then",
    "now",
    "here",
    "there",
    "left",
    "right",
    "top",
    "bottom",
    "above",
    "below",
    "next",
    "slide",
    "title",
    "chart",
    "graph",
    "table",
    "figure",
    "fig",
    "diagram",
    "equation",
    "line",
    "lines",
    "bar",
    "bars",
    "axis",
    "x",
    "y",
    "z",
    "arrow",
    "arrows",
    "box",
    "boxes",
    "text",
    "label",
    "labels",
    "red",
    "blue",
    "green",
    "black",
    "white",
    "yellow",
    "orange",
    "purple",
    "gray",
    "grey",
    "one",
    "two",
    "three",
    "step",
    "steps",
    "point",
    "points",
    "curve",
    "curves",
    "row",
    "rows",
    "column",
    "columns",
    "code",
    "screen",
    "board",
    "whiteboard",
    "blackboard",
    "instructor",
    "lecturer",
    "speaker",
    "presenter",
    "student",
    "students",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "i",
    "ii",
    "iii",
}


@dataclass
class GateReport:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return not self.failures


def normalize_number(token: str) -> str:
    token = token.replace(",", "").replace("−", "-").lstrip("+").rstrip("%")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token


def numbers_in(text: str) -> set[str]:
    return {normalize_number(m.group()) for m in NUMBER.finditer(text)}


def _integer_words(n: int) -> int:
    """Words needed to say a whole number in English: 7 -> 1, 42 -> 2, 150 -> 3, 2000 -> 2."""
    if n == 0:
        return 1
    words = 0
    for scale in (10**9, 10**6, 10**3):
        if n >= scale:
            words += _integer_words(n // scale) + 1
            n %= scale
    if n >= 100:
        words += 2
        n %= 100
    if n == 0:
        return words
    return words + (1 if n <= 20 or n % 10 == 0 else 2)


def _spoken_number_words(token: str) -> int:
    """Spoken words for a numeral: '2,000' -> 2, '40%' -> 2, '0.05' -> 4 ('zero point zero five')."""
    words = 1 if token.endswith("%") else 0
    token = token.rstrip("%").replace(",", "")
    integer, _, fraction = token.partition(".")
    integer = integer.lstrip("+-−") or "0"
    try:
        words += _integer_words(int(integer))
    except ValueError:
        words += 1
    if fraction:
        words += 1 + len(fraction)
    return words


def spoken_word_count(text: str) -> float:
    count = 0.0
    for token in WORD.findall(text):
        count += _spoken_number_words(token) if token[0].isdigit() else 1
    return count


def estimate_seconds(text: str, words_per_second: float) -> float:
    pauses = len(re.findall(r"[,;:—–]", text)) * PAUSE_PER_MARK
    return spoken_word_count(text) / words_per_second + pauses


def overlaps(start: float, end: float, speech: Iterable[Interval], guard: float) -> bool:
    return any(start < s.end + guard and end > s.start - guard for s in speech)


def unknown_names(text: str, known_vocabulary: set[str]) -> list[str]:
    """Capitalised tokens (not sentence-initial) that appear nowhere on screen, in speech or in the registry."""
    unknown: list[str] = []
    for sentence in re.split(r"(?<=[.!?:;])\s+", text.strip()):
        tokens = re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)
        for token in tokens[1:]:
            if not token[0].isupper():
                continue
            base = token.lower().strip("'’").removesuffix("'s").removesuffix("’s")
            if base in COMMON_CAPITALISED or base in known_vocabulary:
                continue
            unknown.append(token)
    return unknown


def vocabulary(*texts: Iterable[str]) -> set[str]:
    vocab: set[str] = set()
    for group in texts:
        for text in group:
            vocab.update(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'’-]*", text))
    return vocab


def check_cue(
    text: str,
    start: float,
    window_end: float,
    *,
    speech: list[Interval],
    allowed_numbers: set[str],
    known_vocabulary: set[str],
    words_per_second: float,
    guard: float,
    lead: float = 0.3,
    extended: bool = False,
) -> GateReport:
    report = GateReport(estimated_seconds=estimate_seconds(text, words_per_second) + lead)
    end = start + report.estimated_seconds
    if not text.strip():
        report.failures.append("empty")
    if not extended:
        if end > window_end - guard:
            report.failures.append(
                f"too_long: needs {report.estimated_seconds:.1f}s, has {window_end - guard - start:.1f}s"
            )
        if overlaps(start, end, speech, guard):
            report.failures.append("talks_over_speech")
    for label, pattern in BANNED.items():
        if pattern.search(text):
            report.failures.append(f"banned_phrase: {label}")
    for number in sorted(numbers_in(text) - allowed_numbers):
        # Small whole numbers usually count visible objects ("3 arrows") rather than quote printed data.
        if not (number.isdigit() and int(number) <= 12):
            report.failures.append(f"number_not_on_screen: {number}")
    for name in unknown_names(text, known_vocabulary):
        report.failures.append(f"unknown_name: {name}")
    if SPECULATION.search(text):
        report.warnings.append("speculation")
    if PAST_TENSE.search(text):
        report.warnings.append("past_tense")
    return report
