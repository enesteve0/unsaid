"""Nebius Serverless Job entry point: describe a backlog of lectures overnight, or run the evaluation.

    uv run --no-sync python -m batch.run_batch --mode backlog --manifest backlog.json --out /out --budget-usd 2
    uv run --no-sync python -m batch.run_batch --mode eval --out /out

Jobs have no automatic retry, so the backlog is resumable: a lecture whose result.json already exists in the output
directory is skipped. A dollar cap stops the run before it overspends. The digest (`digest.json`) is what the web
app shows on its Backlog panel: how many lectures are ready, how many need a person, what it cost.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from unsaid.asr import SpeechRecognizer
from unsaid.config import get_settings
from unsaid.pipeline import RunOptions, run_pipeline
from unsaid.tf_client import AuthFailure, CreditExhausted, TokenFactory


def _fetch(source: str, target: Path) -> Path:
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "Unsaid/0.1 (backlog job)"})
        with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        return target
    return Path(source)


async def backlog(manifest: Path, out: Path, budget_usd: float) -> dict:
    settings = get_settings()
    tf = TokenFactory(settings)
    asr = SpeechRecognizer(Path("models"))
    items = json.loads(manifest.read_text())
    spent, rows = 0.0, []
    started = time.time()
    for item in items:
        workdir = out / item["id"]
        done = workdir / "result.json"
        if done.exists():
            result = json.loads(done.read_text())
            rows.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": "ready",
                    "skipped": True,
                    **_counts(result),
                }
            )
            continue
        if spent >= budget_usd:
            rows.append(
                {"id": item["id"], "title": item["title"], "status": "deferred", "reason": "budget reached"}
            )
            continue
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            video = _fetch(item["source"], workdir / "source.mp4")
            result = await run_pipeline(
                video,
                workdir,
                settings=settings,
                tf=tf,
                asr=asr,
                options=RunOptions(title=item["title"], source_url=item.get("page"), session_id="backlog"),
            )
            cost = result["ledger"]["summary"]["total_usd"]
            spent += cost
            rows.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": "ready",
                    "cost_usd": cost,
                    **_counts(result),
                }
            )
        except (CreditExhausted, AuthFailure) as exc:
            rows.append(
                {"id": item["id"], "title": item["title"], "status": "failed", "reason": type(exc).__name__}
            )
            break
        except Exception as exc:
            rows.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
    digest = {
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
        "spent_usd": round(spent, 6),
        "budget_usd": budget_usd,
        "lectures": rows,
        "ready": sum(1 for r in rows if r["status"] == "ready"),
        "need_review": sum(1 for r in rows if r.get("review", 0) > 0),
    }
    (out / "digest.json").write_text(json.dumps(digest, indent=1))
    return digest


def _counts(result: dict) -> dict:
    tiers = result["metrics"]["tiers"]
    return {
        "cues": result["metrics"]["cues"],
        "auto": tiers["auto"],
        "review": tiers["review"],
        "never": tiers["never"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="run_batch")
    parser.add_argument("--mode", choices=["backlog", "eval"], required=True)
    parser.add_argument("--manifest", default="batch/backlog.json")
    parser.add_argument("--out", default="/out")
    parser.add_argument("--budget-usd", type=float, default=2.0)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "backlog":
        digest = asyncio.run(backlog(Path(args.manifest), out, args.budget_usd))
        print(json.dumps({k: v for k, v in digest.items() if k != "lectures"}))
    else:
        from eval.run_eval import main as run_eval

        run_eval(["--out", str(out)])


if __name__ == "__main__":
    main()
