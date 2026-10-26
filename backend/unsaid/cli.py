"""Command line: `uv run python -m unsaid.cli describe VIDEO --out DIR [--title T] [--source-url URL]`."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .asr import SpeechRecognizer
from .config import get_settings
from .pipeline import RunOptions, run_pipeline
from .tf_client import TokenFactory


def _print_event(event: dict) -> None:
    if event["type"] == "stage" and event["status"] == "start":
        print(f"→ {event['label']}: {event['detail']}", flush=True)
    elif event["type"] == "stage":
        print(
            f"  done in {event['seconds']}s, {len(event['calls'])} model calls, total ${event['total_usd']:.4f}",
            flush=True,
        )


async def _describe(args: argparse.Namespace) -> None:
    settings = get_settings()
    if settings.provider != "tokenfactory":
        print("warning: provider is not Token Factory (local prototyping only)")
    tf = TokenFactory(settings)
    asr = SpeechRecognizer(Path(args.models))
    result = await run_pipeline(
        Path(args.video),
        Path(args.out),
        settings=settings,
        tf=tf,
        asr=asr,
        options=RunOptions(title=args.title, source_url=args.source_url),
        progress=_print_event,
    )
    print(
        json.dumps(
            {"metrics": result["metrics"], "cost": result["ledger"]["summary"], "timings": result["timings"]},
            indent=1,
        )
    )
    for cue in result["cues"]:
        print(f"[{cue['start']:7.2f}] {cue['tier']:6} {cue['id']}: {cue['text']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="unsaid")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("describe", help="describe one video")
    d.add_argument("video")
    d.add_argument("--out", required=True)
    d.add_argument("--title", default="Lecture")
    d.add_argument("--source-url", default=None)
    d.add_argument("--models", default="models")
    args = parser.parse_args()
    if args.command == "describe":
        asyncio.run(_describe(args))


if __name__ == "__main__":
    main()
