"""Timeline structure: when people speak, where the silences are, and where the picture changes."""

from __future__ import annotations

import itertools
import math

from .schemas import Gap, Interval, PointingMoment, Segment, Word


def speech_intervals(words: list[Word], join_gap: float = 0.35) -> list[Interval]:
    """Merge word timings into continuous stretches of speech."""
    intervals: list[Interval] = []
    for w in sorted(words, key=lambda w: w.start):
        if intervals and w.start - intervals[-1].end <= join_gap:
            intervals[-1].end = max(intervals[-1].end, w.end)
        else:
            intervals.append(Interval(start=w.start, end=w.end))
    return intervals


def find_gaps(speech: list[Interval], duration: float, min_gap: float) -> list[Gap]:
    """Silences long enough to hold a description, including before the first and after the last word."""
    gaps: list[Gap] = []
    cursor = 0.0
    for s in [*speech, Interval(start=duration, end=duration)]:
        if s.start - cursor >= min_gap:
            gaps.append(Gap(id="", start=round(cursor, 3), end=round(s.start, 3)))
        cursor = max(cursor, s.end)
    for i, g in enumerate(gaps, start=1):
        g.id = f"g{i}"
    return gaps


def build_segments(
    change_times: list[float], duration: float, min_len: float = 3.0, max_len: float = 60.0
) -> list[Segment]:
    """Turn picture-change timestamps into segments no shorter than `min_len` and no longer than `max_len`."""
    cuts = [0.0]
    for t in sorted(change_times):
        if min_len <= t <= duration - min_len and t - cuts[-1] >= min_len:
            cuts.append(t)
    cuts.append(duration)

    bounds: list[tuple[float, float]] = []
    for start, end in itertools.pairwise(cuts):
        pieces = max(1, math.ceil((end - start) / max_len - 1e-9))
        step = (end - start) / pieces
        bounds.extend((start + i * step, start + (i + 1) * step) for i in range(pieces))

    segments: list[Segment] = []
    for i, (start, end) in enumerate(bounds, start=1):
        length = end - start
        keyframes = sorted(
            {round(start + 0.15 * length, 2), round(start + 0.5 * length, 2), round(end - 0.1 * length, 2)}
        )
        segments.append(Segment(id=f"s{i}", start=round(start, 3), end=round(end, 3), keyframes=keyframes))
    return segments


def segment_at(t: float, segments: list[Segment]) -> Segment:
    for s in segments:
        if s.start <= t < s.end:
            return s
    return segments[-1]


def attach_moments(moments: list[PointingMoment], segments: list[Segment]) -> None:
    """Assign each pointing moment to its segment and add a frame just after it (the thing being pointed at)."""
    for m in moments:
        seg = segment_at(m.t, segments)
        m.segment_id = seg.id
        frame = round(min(m.t + 0.8, seg.end - 0.05), 2)
        if frame not in seg.moment_frames:
            seg.moment_frames = sorted([*seg.moment_frames, frame])


def still_times(segment: Segment, cap: int = 3) -> list[float]:
    """Full-resolution stills for perception, at most `cap`: the frames just after pointing moments first (what the
    speaker points at), then each next keyframe farthest from those already chosen (the middle one if none)."""
    picked = segment.moment_frames[:cap]
    rest = list(segment.keyframes)
    middle = (segment.start + segment.end) / 2
    while len(picked) < cap and rest:
        best = max(rest, key=lambda t: min((abs(t - p) for p in picked), default=-abs(t - middle)))
        rest.remove(best)
        if all(abs(best - p) >= 1.0 for p in picked):
            picked = [*picked, best]
    return sorted(picked)


def gap_after(t: float, gaps: list[Gap], within: float = 12.0) -> Gap | None:
    """First usable silence at or after `t` (descriptions should land right after the pointing moment)."""
    for g in gaps:
        if g.end > t and g.start - t <= within:
            return g
    return None


def said_between(words: list[Word], start: float, end: float) -> str:
    """What is spoken in [start, end), as plain text."""
    return " ".join(w.text for w in words if start <= w.start < end).strip()


def timed_transcript(words: list[Word], max_line_seconds: float = 12.0) -> str:
    """Transcript as '[12.3] sentence' lines, compact enough for one long-context prompt."""
    lines: list[str] = []
    current: list[Word] = []
    for w in words:
        current.append(w)
        if w.text.endswith((".", "?", "!")) or current[-1].end - current[0].start > max_line_seconds:
            lines.append(f"[{current[0].start:.1f}] " + " ".join(x.text for x in current))
            current = []
    if current:
        lines.append(f"[{current[0].start:.1f}] " + " ".join(x.text for x in current))
    return "\n".join(lines)
