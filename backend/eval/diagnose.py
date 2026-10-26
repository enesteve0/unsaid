"""Trace every labelled pointing moment through the pipeline to see where coverage is lost.

    cd backend && uv run python -m eval.diagnose data/eval/proto_all2 data/eval/proto_all2_report.json

For each label it reports the first stage that dropped it: not detected (no pointing phrase near it), resolved as
not visual (Nano), no fact planned (Ultra), planned but no description, or described but judged not covering.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

NEAR = 3.0  # seconds between a label and a detected pointing phrase
WINDOW = (-12.0, 15.0)  # the coverage judge's window around a label


def trace(label: dict, result: dict, verdict: str) -> tuple[str, list[str]]:
    t = label["t"]
    moments = [m for m in result["moments"] if abs(m["t"] - t) <= NEAR]
    resolutions = [result["resolutions"].get(m["id"]) for m in moments]
    visual = [m for m, r in zip(moments, resolutions, strict=True) if r and r["refers_to_visual"]]
    facts = [f for f in result["bible"]["visual_facts"] if f["moment_id"] in {m["id"] for m in moments}]
    fact_ids = {f["id"] for f in facts}
    plans = [p for p in result["bible"]["cue_plan"] if fact_ids & set(p["fact_ids"])]
    cues = [
        c for c in result["cues"] if t + WINDOW[0] <= c["start"] <= t + WINDOW[1] and c["tier"] != "never"
    ]
    linked = [c for c in cues if fact_ids & set(c["fact_ids"])]

    lines = [f'  said: "{label["said"]}"', f"  showed: {label['referent']}"]
    for m, r in zip(moments, resolutions, strict=True):
        lines.append(
            f'  moment {m["id"]} at {m["t"]:.1f}s "{m["phrase"]}" ({m["strength"]}): '
            + (f"visual, target={r['target']!r}" if r and r["refers_to_visual"] else "resolved as NOT visual")
        )
    for f in facts:
        lines.append(
            f"  fact {f['id']} (importance {f['importance']}, spoken={f['already_spoken']}): {f['fact']}"
        )
    for p in plans:
        lines.append(f"  plan {p['gap_id']}: {p['draft']}")
    for c in cues:
        mark = "linked" if c in linked else "nearby"
        lines.append(
            f"  cue {c['id']} {mark} at {c['start']:.1f}s [{c['tier']}{', paused' if c['extended'] else ''}]: "
            f"{c['text']}" + (f" (gates: {', '.join(c['gate_failures'])})" if c["gate_failures"] else "")
        )

    if verdict == "covered":
        stage = "covered"
    elif not moments:
        stage = "not detected"
    elif not visual:
        stage = "resolved as not visual"
    elif not facts:
        stage = "no fact planned"
    elif not linked:
        stage = "planned but not described"
    else:
        stage = "described but judged " + verdict
    return stage, lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="diagnose")
    parser.add_argument("out", help="evaluation output directory (--out of run_eval)")
    parser.add_argument("report", help="its report (--report of run_eval)")
    parser.add_argument("--clips", default="eval/clips.json")
    args = parser.parse_args(argv)

    clips = {c["id"]: c for c in json.loads(Path(args.clips).read_text())}
    report = json.loads(Path(args.report).read_text())
    missed = {
        (f["clip"], f["t"]): f["problem"] for f in report["failures"] if f["text"].startswith("Missed:")
    }
    stages: Counter[str] = Counter()
    for clip_dir in sorted(Path(args.out).iterdir()):
        result_path = clip_dir / "unsaid" / "result.json"
        if clip_dir.name not in clips or not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        print(f"\n== {clip_dir.name}")
        for label in clips[clip_dir.name].get("labels", []):
            problem = missed.get((clip_dir.name, label["t"]))
            verdict = "covered" if problem is None else ("partial" if "partly" in problem else "not covering")
            stage, lines = trace(label, result, verdict)
            stages[stage] += 1
            print(f"- {label['t']:.1f}s: {stage.upper()}")
            if stage != "covered":
                print("\n".join(lines))
    print("\nWhere labels were lost:", dict(stages.most_common()))


if __name__ == "__main__":
    main()
