"""Fill the submission texts with measured numbers, so none is typed by hand.

    python3 scripts/fill_numbers.py [--demo-url https://...] [--allow-prototype]

Reads backend/eval/report.json (the evaluation) and samples/fourier-machine/result.json (the home-page run). Renders
docs/DEVPOST.md from docs/DEVPOST.template.md and the results block between the markers in README.md. A placeholder
without a measurement stays visible as {{name}} and the script exits with status 1, so nothing unmeasured slips
through. Runs that did not go through Token Factory are refused unless --allow-prototype is given.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "backend" / "eval" / "report.json"
CLIPS = REPO / "backend" / "eval" / "clips.json"
SAMPLE = REPO / "samples" / "fourier-machine" / "result.json"
TEMPLATE = REPO / "docs" / "DEVPOST.template.md"
DEVPOST = REPO / "docs" / "DEVPOST.md"
README = REPO / "README.md"
START, END = "<!-- results:start -->", "<!-- results:end -->"
VISION = "Nemotron 3.5 Super VL"
# Where the evaluation may have run, and how the texts say so.
EVAL_PROVIDERS = {
    "tokenfactory": "on Nebius Token Factory",
    "nvidia_build": "with the same Nemotron models through NVIDIA's API catalog (build.nvidia.com), keeping our "
    "Token Factory credit for the live demo; costs are priced at Token Factory list prices",
}
WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def usd(x: float) -> str:
    return f"${x:.3f}" if x >= 0.01 else f"${x:.4f}"


FORMATS = {
    "talk_over": lambda x: f"{x:.1f} s",
    "in_silence": pct,
    "pauses": lambda x: f"{x:.2f}",
    "coverage": pct,
    "unsupported": pct,
    "ungrounded": pct,
    "usd_per_min": usd,
    "sec_per_min": lambda x: f"{x:.0f} s",
}
ROWS = [
    ("talk_over", "Spoken over the lecturer, per minute of video"),
    ("in_silence", "Descriptions that fit in a pause"),
    ("coverage", "Pointing moments covered"),
    ("ungrounded", "Descriptions with an invented number or name"),
    ("unsupported", "Claims the frames do not support"),
    ("pauses", "Video pauses for extended descriptions, per minute"),
    ("usd_per_min", "Model cost per minute of video"),
]


def metrics(systems: list[dict]) -> dict[str, dict[str, float]]:
    return {s["key"]: s["metrics"] for s in systems}


def report_values(report: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    m = metrics(report["systems"])
    for system, row in m.items():
        for key, value in row.items():
            if key in FORMATS:
                values[f"{system}.{key}"] = FORMATS[key](value)
    u, o = m["unsaid"], m["oneshot"]
    splits = {s["key"]: s for s in report.get("splits", [])}
    clip_ids = {c["id"] for c in report.get("per_clip", [])}
    labels = sum(len(c.get("labels", [])) for c in json.loads(CLIPS.read_text()) if c["id"] in clip_ids)
    values |= {
        "eval_where": EVAL_PROVIDERS.get(report.get("provider", ""), "on a prototype endpoint"),
        "clips": str(report["clips"]),
        "minutes": f"{report['minutes']:.1f}",
        "labels": str(labels),
        "runs": {1: "once", 2: "twice"}.get(report.get("runs", 1), f"{report.get('runs')} times"),
        "usd_per_min": usd(u["usd_per_min"]),
        "dev_clips_word": WORDS.get(splits["dev"]["clips"], str(splits["dev"]["clips"]))
        if "dev" in splits
        else "None",
        "heldout_clips": str(splits["heldout"]["clips"]) if "heldout" in splits else "0",
    }
    fit = "none" if o["in_silence"] == 0 else f"only {pct(o['in_silence'])}"
    if pct(u["coverage"]) == pct(o["coverage"]):
        values["coverage_sentence"] = (
            f"Both covered {pct(u['coverage'])} of the pointing moments; {fit} of the one-shot descriptions fit a "
            "pause, and Unsaid's all do."
        )
    elif u["coverage"] > o["coverage"]:
        values["coverage_sentence"] = (
            f"Unsaid covered more of the pointing moments ({pct(u['coverage'])} against {pct(o['coverage'])}) "
            "without speaking over the lecturer."
        )
    else:
        values["coverage_sentence"] = (
            f"The one-shot approach covered more pointing moments ({pct(o['coverage'])} against "
            f"{pct(u['coverage'])}), but {fit} of its descriptions fit a pause: a student would hear "
            f"{'them' if o['in_silence'] == 0 else 'the rest'} on top of the explanation. Unsaid describes less, and "
            "every description it speaks is heard."
        )
    if "heldout" in splits:
        h = metrics(splits["heldout"]["systems"])
        values["heldout_sentence"] = (
            f"On the held-out clips alone, Unsaid covered {pct(h['unsaid']['coverage'])} of the pointing moments "
            f"(one-shot {pct(h['oneshot']['coverage'])}) and spoke over the lecturer for "
            f"{FORMATS['talk_over'](h['unsaid']['talk_over'])} per minute (one-shot "
            f"{FORMATS['talk_over'](h['oneshot']['talk_over'])})."
        )
    return values


def sample_values(sample: dict) -> dict[str, str]:
    summary = sample["ledger"]["summary"]
    total = summary["total_usd"]
    if total <= 0:
        return {}
    vision = summary["by_model"].get(VISION, {}).get("cost_usd", 0.0)
    text, text_on_ultra = total - vision, summary["ultra_only_usd"] - vision
    ratio = round(text_on_ultra / text, 2) if text > 0 else 1.0
    phrase = f"{round((ratio - 1) * 100)}% more" if ratio < 2 else f"{ratio:.1f} times as much"
    split = sorted(summary["by_model"].items(), key=lambda kv: -kv[1]["cost_usd"])
    return {
        "ultra_only_phrase": phrase,
        "cost_split": ", ".join(f"{name} {pct(row['cost_usd'] / total)}" for name, row in split),
    }


def deployment_values(base: str) -> dict[str, str]:
    """What the text may say about hosting, as the deployed app reports it (claims follow what actually runs)."""

    def get(path: str) -> dict | None:
        try:
            with urllib.request.urlopen(base + path, timeout=20) as response:
                return json.load(response)
        except (OSError, ValueError):  # the static demo has no API
            return None

    health, backlog_info = get("/api/health"), get("/api/backlog") or {}
    host, backlog = (health or {}).get("host", ""), backlog_info.get("available", False)
    on_nebius = "Nebius" in host
    return {
        "backlog_line": "Long lectures run **overnight as a Nebius Serverless Job** with a dollar cap."
        if backlog
        else "Long lectures go to an **overnight batch job** (built for Nebius Serverless Jobs) with a dollar cap.",
        "hosting_tags": "nebius-ai-cloud, nebius-serverless, "
        if on_nebius
        else ("github-pages, " if health is None else "fly.io, "),
    }


def readme_block(report: dict, values: dict[str, str]) -> str:
    m = metrics(report["systems"])
    lines = [
        f"On {values['clips']} openly licensed lecture clips ({values['minutes']} minutes, {values['labels']} labelled "
        f"pointing moments), each described {values['runs']}, measured {values['eval_where']}, scored by the same "
        f"code for both systems (evaluated {report['generated_at']}):",
        "",
        "| | One-shot (Super VL, whole clip) | Unsaid |",
        "| --- | --- | --- |",
    ]
    for key, label in ROWS:
        lines.append(f"| {label} | {FORMATS[key](m['oneshot'][key])} | {FORMATS[key](m['unsaid'][key])} |")
    lines += [
        "",
        values["coverage_sentence"],
        "",
        "Unsupported claims are scored by the same Super VL verifier that Unsaid's own check step answers to, so that "
        "row favours Unsaid; invented numbers and names are counted by code.",
    ]
    if "heldout_sentence" in values:
        lines += ["", values["heldout_sentence"]]
    lines += [
        "",
        "Method, both splits and the failure list: the app's Evaluation page and `backend/eval/run_eval.py`.",
    ]
    return "\n".join(lines)


def fill(text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    missing: list[str] = []

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return values[key]
        missing.append(key)
        return match.group(0)

    return re.sub(r"\{\{([\w.]+)\}\}", sub, text), missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-url", default="")
    parser.add_argument("--repo-url", default="https://github.com/enesteve0/unsaid")
    parser.add_argument(
        "--allow-prototype", action="store_true", help="accept runs not made on Token Factory"
    )
    parser.add_argument(
        "--allow-partial", action="store_true", help="accept a report the evaluation is still writing"
    )
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    args = parser.parse_args()

    values: dict[str, str] = {"repo_url": args.repo_url}
    if args.demo_url:
        values["demo_url"] = args.demo_url.rstrip("/")
        values |= deployment_values(args.demo_url.rstrip("/"))
    problems: list[str] = []

    report = json.loads(args.report.read_text()) if args.report.exists() else {"available": False}
    if report.get("available"):
        if report.get("complete") is False and not args.allow_partial:
            problems.append(f"{args.report.name} is partial: the evaluation did not finish every clip")
        elif report.get("provider") not in EVAL_PROVIDERS and not args.allow_prototype:
            problems.append(f"{args.report.name} comes from an unknown provider ({report.get('provider')!r})")
        else:
            values |= report_values(report)
    else:
        problems.append(f"no evaluation report at {args.report}")

    sample = json.loads(args.sample.read_text())
    if sample.get("provider", "tokenfactory") != "tokenfactory" and not args.allow_prototype:
        problems.append(
            f"the home-page sample was not made on Token Factory (provider {sample.get('provider')!r})"
        )
    else:
        values |= sample_values(sample)

    devpost, missing = fill(TEMPLATE.read_text(), values)
    DEVPOST.write_text(
        "# Devpost submission text\n\n"
        "Generated by `scripts/fill_numbers.py` from `docs/DEVPOST.template.md`, the evaluation report and the home-page "
        "run; edit the template, not this file. Paste each section into the matching Devpost field.\n\n"
        + devpost[devpost.index("## Project overview") :]
    )

    readme = README.read_text()
    if START in readme and END in readme and "clips" in values:
        before, rest = readme.split(START, 1)
        after = rest.split(END, 1)[1]
        README.write_text(f"{before}{START}\n{readme_block(report, values)}\n{END}{after}")
    elif START not in readme:
        problems.append("README.md has no results markers")

    for p in problems:
        print("!", p)
    if missing:
        print("unfilled:", ", ".join(sorted(set(missing))))
    print(f"wrote {DEVPOST.relative_to(REPO)}" + (" and README.md" if "clips" in values else ""))
    return 1 if (missing or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
