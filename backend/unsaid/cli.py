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


def _publish(args: argparse.Namespace) -> None:
    """Copy a finished run into samples/<id>/ (video, tracks, result) and register it in samples/manifest.json."""
    import shutil
    import subprocess

    run = Path(args.run)
    target = Path(args.samples) / args.id
    target.mkdir(parents=True, exist_ok=True)
    # 720p H.264 + AAC with fast start: plenty for the web player, small enough to keep in the repository.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            args.video,
            "-vf",
            "scale=-2:720",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(target / "video.mp4"),
        ],
        check=True,
    )
    for name in (
        "result.json",
        "descriptions.vtt",
        "captions.vtt",
        "captions.srt",
        "transcript.html",
        "markers.fcpxml",
    ):
        shutil.copyfile(run / name, target / name)
    poster_at = float(args.hero.split(",")[0]) + 1.0 if args.hero else 5.0
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{poster_at:.2f}",
            "-i",
            str(target / "video.mp4"),
            "-frames:v",
            "1",
            "-vf",
            "scale='min(1280,iw)':-2",
            "-q:v",
            "3",
            str(target / "poster.jpg"),
        ],
        check=True,
    )
    manifest_path = Path(args.samples) / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    result = json.loads((run / "result.json").read_text())
    entry = {
        "id": args.id,
        "title": result["title"],
        "credit": args.credit,
        "license": args.license,
        "license_url": args.license_url,
        "source_url": args.source_url,
        "duration": result["video"]["duration"],
        "run_seconds": round(result.get("timings", {}).get("total", 0)),
        "provider": result.get("provider", ""),
    }
    if args.hero:
        start, end = (float(x) for x in args.hero.split(","))
        entry["hero"] = {"start": start, "end": end}
    manifest = [m for m in manifest if m["id"] != args.id]
    manifest.insert(0 if args.first else len(manifest), entry)
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"published {args.id} -> {target}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="unsaid")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("describe", help="describe one video")
    d.add_argument("video")
    d.add_argument("--out", required=True)
    d.add_argument("--title", default="Lecture")
    d.add_argument("--source-url", default=None)
    d.add_argument("--models", default="models")
    p = sub.add_parser("publish-sample", help="publish a finished run as a sample")
    p.add_argument("--run", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--credit", required=True)
    p.add_argument("--license", required=True)
    p.add_argument("--license-url", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--hero", default="", help="start,end seconds of the home-page excerpt")
    p.add_argument("--first", action="store_true")
    p.add_argument("--samples", default="../samples")
    args = parser.parse_args()
    if args.command == "describe":
        asyncio.run(_describe(args))
    elif args.command == "publish-sample":
        _publish(args)


if __name__ == "__main__":
    main()
