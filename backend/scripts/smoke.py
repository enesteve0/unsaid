"""Token Factory smoke test: proves each Nemotron model Unsaid uses is live and behaves as the pipeline expects.

    cd backend && uv run python scripts/smoke.py            # writes ../docs/EVIDENCE.md (no secrets)

Checks: catalog IDs and status, thinking off on every model, strict json_schema on Super VL, Super VL with a clip
and a still under a strict schema (the perception request's shape), Ultra reasoning, cached-token reporting on a
repeated prefix. Every call streams, as in production.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel

from unsaid import media
from unsaid.config import TOKEN_FACTORY_MODELS, Role, get_settings
from unsaid.ledger import Ledger
from unsaid.tf_client import TokenFactory

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "EVIDENCE.md"


class Product(BaseModel):
    answer: int


class Canary(BaseModel):
    greeting: str
    code: str


class Seen(BaseModel):
    summary: str


async def main() -> None:
    settings = get_settings()
    if settings.provider != "tokenfactory" or not settings.nebius_api_key:
        raise SystemExit("Set NEBIUS_API_KEY in ../.env (and PROVIDER=tokenfactory).")
    tf = TokenFactory(settings)
    ledger = Ledger()
    rows: list[str] = []

    def record(check: str, ok: bool, detail: str) -> None:
        rows.append(f"| {check} | {'pass' if ok else 'FAIL'} | {detail} |")
        print(f"{'PASS' if ok else 'FAIL'}  {check}: {detail}", flush=True)

    listed = {m["id"]: m for m in await tf.list_models()}
    for chain in TOKEN_FACTORY_MODELS.values():
        for model in chain:
            record(
                f"catalog: {model}",
                model in listed,
                f"status={listed.get(model, {}).get('status', 'missing')}",
            )

    for role in (Role.FAST, Role.CLASSIFY, Role.VISION, Role.REASON):
        t0 = time.perf_counter()
        r = await tf.chat(
            role,
            [{"role": "user", "content": "What is 17*23? Reply with only the number."}],
            stage="smoke",
            ledger=ledger,
            thinking=False,
            max_tokens=64,
        )
        record(
            f"thinking off, {role.value} ({r.model})",
            r.content.strip().startswith("391"),
            f"'{r.content.strip()[:20]}' in {time.perf_counter() - t0:.2f}s",
        )

    r = await tf.chat(
        Role.CLASSIFY,
        [{"role": "user", "content": "Compute 17*23."}],
        stage="smoke",
        ledger=ledger,
        schema=Product,
        max_tokens=200,
    )
    record("json_schema, classify", r.parsed is not None and r.parsed.answer == 391, r.content[:60])  # type: ignore[union-attr]

    r = await tf.chat(
        Role.VISION,
        [{"role": "user", "content": "Say hello."}],
        stage="smoke",
        ledger=ledger,
        schema=Canary,
        max_tokens=200,
    )
    record("strict json_schema, vision", r.parsed is not None, r.content[:80])

    clip = Path("data/smoke_clip.mp4")
    clip.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=6:size=960x540:rate=24",
            "-vf",
            "scale=480:-2,fps=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )
    still = await media.still(clip, 3.0, clip.with_suffix(".jpg"))
    t0 = time.perf_counter()
    # The perception request's shape: a clip plus a full-resolution still, strict json_schema, streamed.
    r = await tf.chat(
        Role.VISION,
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this video in one sentence; the still is a frame at 3 s.",
                    },
                    {"type": "video_url", "video_url": {"url": media.data_url(clip)}},
                    {"type": "image_url", "image_url": {"url": media.data_url(still)}},
                ],
            }
        ],
        stage="smoke",
        ledger=ledger,
        schema=Seen,
        max_tokens=300,
    )
    record(
        "video + still, strict json_schema, streamed, vision",
        r.parsed is not None,
        f"'{r.content[:70]}' in {time.perf_counter() - t0:.1f}s, "
        f"{ledger.entries[-1].prompt_tokens} prompt tokens",
    )

    t0 = time.perf_counter()
    r = await tf.chat(
        Role.REASON,
        [{"role": "user", "content": "In one sentence: why do audio descriptions go in pauses?"}],
        stage="smoke",
        ledger=ledger,
        thinking=True,
    )
    last = ledger.entries[-1]
    record(
        f"reasoning streamed ({r.model})",
        bool(r.content),
        f"{last.reasoning_tokens} reasoning / {last.completion_tokens} output tokens in {time.perf_counter() - t0:.1f}s",
    )

    # REASON_EFFORT=medium only helps if Token Factory honours the chat template's medium_effort flag. On the NVIDIA
    # API catalog it halved Ultra's output on this puzzle (medians 1,478 vs 2,794 tokens over four runs each).
    puzzle = (
        "Five silences last 1.2, 2.5, 3.1, 0.9 and 4.0 seconds. Four facts have importance 3, 2, 3 and 1 and lengths "
        "of 6, 9, 4 and 7 words; speech runs at 2.5 words per second. Assign facts to silences, at most one fact per "
        "silence, to maximise the total importance described. Reply with the total importance only."
    )
    spent: dict[bool, list[int]] = {False: [], True: []}
    for medium in (False, True, False, True):
        await tf.chat(
            Role.REASON,
            [{"role": "user", "content": puzzle}],
            stage="smoke",
            ledger=ledger,
            thinking=True,
            medium_effort=medium,
        )
        spent[medium].append(ledger.entries[-1].completion_tokens)
    full, medium = statistics.median(spent[False]), statistics.median(spent[True])
    record(
        "medium_effort honoured, reason",
        medium < 0.75 * full,
        f"median {medium:.0f} output tokens at medium effort vs {full:.0f} at full effort (2 runs each)",
    )

    prefix = "You are a careful assistant. " * 400
    for i in range(2):
        await tf.chat(
            Role.REASON,
            [{"role": "system", "content": prefix}, {"role": "user", "content": f"Say {i}."}],
            stage="smoke",
            ledger=ledger,
            thinking=False,
            max_tokens=16,
        )
    record(
        "prompt caching, reason",
        ledger.entries[-1].cached_tokens > 0,
        f"cached {ledger.entries[-1].cached_tokens} of {ledger.entries[-1].prompt_tokens} prompt tokens on the repeat",
    )

    summary = ledger.summary()
    EVIDENCE.write_text(
        "# Integration evidence\n\n"
        f"Token Factory smoke test run {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} against "
        f"`{settings.tf_base_url}` (keys never logged).\n\n"
        "| Check | Result | Detail |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n\n"
        f"Total: {summary['calls']} calls, ${summary['total_usd']:.4f}.\n\n"
        "Request ids (for support):\n\n"
        + "\n".join(f"- {e.stage} {e.model}: `{e.request_id}`" for e in ledger.entries)
        + "\n"
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
