"""Evaluation: Unsaid against a one-shot baseline, scored by the same code.

Systems
  oneshot  Nemotron 3.5 Super VL gets the whole clip plus the timed transcript and returns timestamped
           descriptions in one call (the pattern of most AI audio-description tools).
  unsaid   The full routed pipeline.

Metrics (per system, over all clips)
  talk_over      seconds of description spoken over the lecturer, per minute of video
  in_silence     share of descriptions that start and finish inside a silence
  pauses         extended descriptions (video pauses) per minute
  coverage       share of labelled pointing moments whose referent a description conveys (judged by Nemotron 3 Ultra
                 against builder-written labels; partial = 0.5)
  unsupported    share of descriptions with a claim the frames do not support (Super VL verifier, same for both)
  ungrounded     share of descriptions with a number or name found nowhere on screen or in the speech
  usd_per_min    model cost per minute of video
  sec_per_min    wall-clock seconds per minute of video

    uv run python -m eval.run_eval --clips eval/clips.json --out eval/out
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from unsaid import gates, media
from unsaid.asr import SpeechRecognizer
from unsaid.config import Role, get_settings
from unsaid.ledger import Ledger
from unsaid.pipeline import PerceptionFailed, RunOptions, run_pipeline
from unsaid.schemas import Cue, Interval, Word
from unsaid.segments import timed_transcript
from unsaid.tf_client import AuthFailure, CreditExhausted, TokenFactory
from unsaid.verify import verify_cue

ONESHOT_SYSTEM = (
    "You are an audio describer for blind and low-vision students. You receive a lecture video clip and its timed "
    "transcript. Write audio descriptions of the important visual information, each with the time in seconds at "
    "which it should be spoken. Place descriptions in pauses between speech and do not repeat what is said."
)


class OneShotItem(BaseModel):
    t: float
    text: str


class OneShot(BaseModel):
    descriptions: list[OneShotItem]


class CoverageVerdict(BaseModel):
    verdict: Literal["yes", "partial", "no"]
    reason: str = Field(description="One short sentence")


JUDGE_SYSTEM = (
    "You grade audio description for blind students. A lecturer pointed at something instead of saying it. Given "
    "what the lecturer said, what the screen actually showed (written by a person who watched it) and the "
    "descriptions spoken nearby, answer whether a blind listener now knows what was pointed at: yes, partial or no."
)


async def oneshot(
    tf: TokenFactory, ledger: Ledger, video: Path, words: list[Word], duration: float, workdir: Path
) -> list[Cue]:
    clip = await media.cut_clip(video, 0, min(duration, 119.5), workdir / "oneshot.mp4")
    content = [
        {"type": "text", "text": "Timed transcript:\n" + timed_transcript(words)},
        {"type": "video_url", "video_url": {"url": media.data_url(clip)}},
    ]
    result = await tf.chat(
        Role.VISION,
        [{"role": "system", "content": ONESHOT_SYSTEM}, {"role": "user", "content": content}],
        stage="oneshot",
        ledger=ledger,
        schema=OneShot,
        max_tokens=3000,
    )
    cues = []
    for i, item in enumerate(sorted(result.parsed.descriptions, key=lambda d: d.t), start=1):  # type: ignore[union-attr]
        est = gates.estimate_seconds(item.text, 2.5) + 0.3
        cues.append(
            Cue(id=f"b{i:03d}", gap_id=None, start=item.t, end=item.t + est, text=item.text, tier="review")
        )
    return cues


def timing(cues: list[Cue], speech: list[Interval]) -> tuple[float, float]:
    talk_over, inside = 0.0, 0
    for c in cues:
        if c.extended:
            inside += 1
            continue
        overlap = sum(max(0.0, min(c.end, s.end) - max(c.start, s.start)) for s in speech)
        talk_over += overlap
        inside += overlap == 0
    return talk_over, inside


def grounding(cues: list[Cue], result: dict) -> int:
    """Descriptions with a number or name found nowhere on screen, in what the vision model saw, or in the speech.
    Uses the same sources as the pipeline's gates, for both systems."""
    screen = [t for o in result["observations"].values() for t in o["on_screen_text"]]
    spoken = " ".join(w["text"] for w in result["transcript"])
    allowed = gates.numbers_seen(result["observations"].values(), spoken)
    vocab = gates.vocabulary(screen, [spoken], result["context"]["names"])
    bad = 0
    for c in cues:
        numbers = {n for n in gates.numbers_in(c.text) - allowed if not (n.isdigit() and int(n) <= 12)}
        bad += bool(numbers or gates.unknown_names(c.text, vocab))
    return bad


async def coverage(
    tf: TokenFactory, ledger: Ledger, labels: list[dict], cues: list[Cue]
) -> tuple[float, list[float]]:
    if not labels:
        return float("nan"), []
    scores: list[float] = []
    for label in labels:
        # Describers often voice a visual when it appears, a few seconds before the speaker points at it.
        nearby = [c.text for c in cues if label["t"] - 12 <= c.start <= label["t"] + 15]
        if not nearby:
            scores.append(0.0)
            continue
        verdict = await tf.chat(
            Role.REASON,
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"said": label["said"], "screen_showed": label["referent"], "descriptions": nearby}
                    ),
                },
            ],
            stage="judge",
            ledger=ledger,
            thinking=True,
            schema=CoverageVerdict,
            constrain=False,
            max_tokens=12000,
        )
        scores.append({"yes": 1.0, "partial": 0.5, "no": 0.0}[verdict.parsed.verdict])  # type: ignore[union-attr]
    return sum(scores) / len(scores), scores


async def evaluate_clip(tf: TokenFactory, asr: SpeechRecognizer, clip: dict, out: Path) -> dict:
    settings = get_settings()
    workdir = out / clip["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    video = Path(clip["path"])

    t0 = time.perf_counter()
    try:
        result = await run_pipeline(
            video,
            workdir / "unsaid",
            settings=settings,
            tf=tf,
            asr=asr,
            options=RunOptions(title=clip["title"]),
        )
    except PerceptionFailed as exc:
        # An infrastructure failure, not a judgement on either system: leave the clip out and say why.
        return {"id": clip["id"], "title": clip["title"], "skipped": str(exc)}
    unsaid_seconds = time.perf_counter() - t0
    unsaid_cues = [Cue(**c) for c in result["cues"] if c["tier"] != "never"]
    speech = [Interval(**s) for s in result["speech"]]
    words = [Word(**w) for w in result["transcript"]]
    duration = result["video"]["duration"]

    base_ledger = Ledger()
    t0 = time.perf_counter()
    base_cues: list[Cue] | None = None
    for _ in range(2):
        try:
            base_cues = await oneshot(tf, base_ledger, video, words, duration, workdir)
            break
        except (CreditExhausted, AuthFailure):
            raise
        except Exception as exc:
            print(f"  one-shot failed on {clip['id']}: {type(exc).__name__}", flush=True)
    if base_cues is None:
        # Never score a failed baseline as an empty, perfect one: leave the clip out for both systems.
        return {"id": clip["id"], "title": clip["title"], "skipped": "one-shot baseline failed twice"}
    base_seconds = time.perf_counter() - t0
    for cue in base_cues:
        times = [min(cue.start + 0.3, duration - 0.1), min(cue.start + 1.3, duration - 0.1)]
        try:
            await verify_cue(tf, base_ledger, video, cue, times, workdir)
        except (CreditExhausted, AuthFailure):
            raise
        except Exception:
            cue.verification = None

    judge_ledger = Ledger()
    labels = clip.get("labels", [])
    rows: dict = {}
    failures: list[dict] = []
    for key, cues, seconds, cost in (
        ("unsaid", unsaid_cues, unsaid_seconds, result["ledger"]["summary"]["total_usd"]),
        ("oneshot", base_cues, base_seconds, base_ledger.total_cost),
    ):
        talk_over, inside = timing(cues, speech)
        covered, per_label = await coverage(tf, judge_ledger, labels, cues)
        if key == "unsaid":
            for c in cues:
                if c.verification is not None and not c.verification.supported:
                    failures.append(
                        {
                            "clip": clip["id"],
                            "t": c.start,
                            "text": c.text,
                            "problem": "claim not supported by the frames: "
                            + "; ".join(c.verification.unsupported_claims),
                        }
                    )
            for label, score in zip(labels, per_label, strict=False):
                if score < 1.0:
                    failures.append(
                        {
                            "clip": clip["id"],
                            "t": label["t"],
                            "text": f"Missed: {label['referent']}",
                            "problem": "pointing moment not described"
                            if score == 0
                            else "pointing moment only partly described",
                        }
                    )
        rows[key] = {
            "cues": len(cues),
            "talk_over": talk_over,
            "in_silence": inside,
            "pauses": sum(c.extended for c in cues),
            "coverage": covered,
            "checked": sum(1 for c in cues if c.verification is not None),
            "unsupported": sum(
                1 for c in cues if c.verification is not None and not c.verification.supported
            ),
            "ungrounded": grounding(cues, result),
            "usd": cost,
            "seconds": seconds,
            "minutes": duration / 60,
            "texts": [{"t": c.start, "text": c.text, "extended": c.extended} for c in cues],
        }
    (workdir / "scores.json").write_text(json.dumps(rows, indent=1))
    return {
        "id": clip["id"],
        "title": clip["title"],
        "split": clip.get("split", "dev"),
        **rows,
        "failures": failures,
        "judge_usd": judge_ledger.total_cost,
    }


SYSTEM_LABELS = {
    "oneshot": "One-shot (Super VL, whole clip + transcript)",
    "unsaid": "Unsaid (routed pipeline + code gates)",
}
METRIC_LABELS = {
    "talk_over": {"label": "Talks over lecturer", "better": "lower", "unit": "s"},
    "in_silence": {"label": "Fits a silence", "better": "higher", "unit": "%"},
    "pauses": {"label": "Video pauses / min", "better": "lower"},
    "coverage": {"label": "Pointing moments covered", "better": "higher", "unit": "%"},
    "unsupported": {"label": "Claims not in frames", "better": "lower", "unit": "%"},
    "ungrounded": {"label": "Invented numbers or names", "better": "lower", "unit": "%"},
    "usd_per_min": {"label": "Cost per video minute", "better": "lower", "unit": "$"},
    "sec_per_min": {"label": "Seconds per video minute", "better": "lower"},
}
SPLIT_LABELS = {
    "heldout": "Held-out clips: labelled blind, never used to tune Unsaid's prompts",
    "dev": "Development clips: also used to develop Unsaid's prompts",
}


def summarize(clips: list[dict]) -> list[dict]:
    """Both systems' metrics over a set of evaluated clips."""
    systems = []
    minutes = sum(c["unsaid"]["minutes"] for c in clips)
    for key in ("oneshot", "unsaid"):
        rows = [c[key] for c in clips]
        cues = sum(r["cues"] for r in rows) or 1
        covered = [r["coverage"] for r in rows if r["coverage"] == r["coverage"]]
        systems.append(
            {
                "key": key,
                "label": SYSTEM_LABELS[key],
                "metrics": {
                    "talk_over": sum(r["talk_over"] for r in rows) / minutes,
                    "in_silence": sum(r["in_silence"] for r in rows) / cues,
                    "pauses": sum(r["pauses"] for r in rows) / minutes,
                    "coverage": sum(covered) / len(covered) if covered else 0.0,
                    "unsupported": sum(r["unsupported"] for r in rows)
                    / max(sum(r["checked"] for r in rows), 1),
                    "ungrounded": sum(r["ungrounded"] for r in rows) / cues,
                    "usd_per_min": sum(r["usd"] for r in rows) / minutes,
                    "sec_per_min": sum(r["seconds"] for r in rows) / minutes,
                },
            }
        )
    return systems


def _distinct(clips: list[dict]) -> tuple[int, float]:
    """Number of clips and minutes of video, counting a clip described in several runs once."""
    by_id = {c["id"]: c for c in clips}
    return len(by_id), sum(c["unsaid"]["minutes"] for c in by_id.values())


def aggregate(clips: list[dict]) -> dict:
    """Metrics pool every clip-run: a clip described in several runs counts once per run."""
    splits = [
        {
            "key": key,
            "label": label,
            "clips": _distinct(subset)[0],
            "minutes": _distinct(subset)[1],
            "systems": summarize(subset),
        }
        for key, label in SPLIT_LABELS.items()
        if (subset := [c for c in clips if c.get("split", "dev") == key])
    ]
    provenance = (
        "Held-out clips were labelled blind and never used to tune Unsaid's prompts, and their labels include "
        "pointing moments the phrase detector misses. Unsaid ran on them once before a change to where paused "
        "descriptions start, a change that development failures also called for. Development clips were also used "
        "to develop the prompts."
        if any(s["key"] == "heldout" for s in splits)
        else "Unsaid's prompts were developed on these same clips, so these are development results."
    )
    return {
        "available": True,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "clips": _distinct(clips)[0],
        "minutes": _distinct(clips)[1],
        "systems": summarize(clips),
        "splits": splits,
        "metric_labels": METRIC_LABELS,
        "failures": [f for c in clips for f in c.get("failures", [])],
        "per_clip": [
            {k: v for k, v in c.items() if k not in ("oneshot", "unsaid")}
            | {
                s: {m: c[s][m] for m in ("cues", "talk_over", "in_silence", "coverage", "unsupported", "usd")}
                for s in ("oneshot", "unsaid")
            }
            for c in clips
        ],
        "notes": [
            "Talk-over uses the speech intervals from NVIDIA Parakeet for both systems; descriptions are timed at 2.5 words per second.",
            "Coverage labels were written by the builder after viewing the frames at each pointing moment; Nemotron 3 Ultra judges them.",
            provenance + " No phrase from any clip appears in a prompt.",
            "The same Super VL verifier checks both systems' descriptions against the frames; descriptions it could not "
            "check are excluded from that rate and counted separately.",
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="run_eval")
    parser.add_argument("--clips", default="eval/clips.json")
    parser.add_argument("--out", default="eval/out")
    parser.add_argument("--report", default="eval/report.json")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="describe every clip this many times and pool the runs (models vary)",
    )
    args = parser.parse_args(argv)
    clips = json.loads(Path(args.clips).read_text())
    out = Path(args.out)
    settings = get_settings()
    tf = TokenFactory(settings)
    asr = SpeechRecognizer(Path("models"))

    async def run_all() -> list[dict]:
        results = []
        for run in range(1, args.repeat + 1):
            for clip in clips:  # sequential: keeps rate limits and the cost ledger easy to read
                print(
                    f"→ {clip['id']}" + (f" (run {run} of {args.repeat})" if args.repeat > 1 else ""),
                    flush=True,
                )
                workdir = out / f"run{run}" if args.repeat > 1 else out
                results.append({**await evaluate_clip(tf, asr, clip, workdir), "run": run})
        return results

    results = asyncio.run(run_all())
    skipped = [r for r in results if "skipped" in r]
    done = [r for r in results if "skipped" not in r]
    report = aggregate(done)
    report["runs"] = args.repeat
    if args.repeat > 1:
        report["per_run"] = [
            {"run": run, "systems": summarize(subset)}
            for run in range(1, args.repeat + 1)
            if (subset := [r for r in done if r["run"] == run])
        ]
        report["notes"].append(
            f"Every clip was described {args.repeat} times, because model outputs vary from run to run; the "
            "metrics pool all runs, and per_run shows each run on its own."
        )
    report["skipped"] = [{"id": r["id"], "run": r["run"], "reason": r["skipped"]} for r in skipped]
    Path(args.report).write_text(json.dumps(report, indent=1))
    print(json.dumps(report["systems"], indent=1))


if __name__ == "__main__":
    main()
