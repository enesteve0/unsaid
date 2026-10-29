"""Deploy (or update) the Unsaid demo as a free Hugging Face Docker Space (2 vCPU, 16 GB, no persistent disk).

    cd backend && uv run --with huggingface_hub python ../infra/hf/deploy.py --mode recorded
    cd backend && uv run --with huggingface_hub python ../infra/hf/deploy.py --mode judges --live-until 2026-11-27

Reads HF_TOKEN, NEBIUS_API_KEY, TAVILY_API_KEY and JUDGE_CODE from ../.env and prints nothing secret.
Modes: recorded (examples only, no model calls), judges (live runs only with the access code), live (everyone).
Without a persistent disk, the spend caps restart with the container, so judges mode keeps the caps tight.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

REPO = Path(__file__).resolve().parents[2]
SKIP = shutil.ignore_patterns(
    ".venv", "data", "models", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "dist",
    "test-results", "playwright-report", ".DS_Store", "tests", "e2e",
)  # fmt: skip
CARD = """---
title: Unsaid
emoji: 🔊
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 8080
pinned: false
license: mit
short_description: Audio description for what a lecture shows but never says
---

# Unsaid

Audio description for everything a lecture shows but never says: four NVIDIA Nemotron models on Nebius Token
Factory, NVIDIA Parakeet speech recognition, and timing and grounding rules enforced in code.

Source, method and evaluation: https://github.com/enesteve0/unsaid
"""


def env() -> dict[str, str]:
    values = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["recorded", "judges", "live"], required=True)
    parser.add_argument("--live-until", default="", help="last day of live runs (UTC, YYYY-MM-DD)")
    parser.add_argument("--space", default="unsaid")
    args = parser.parse_args()

    secrets = env()
    api = HfApi(token=secrets["HF_TOKEN"])
    user = api.whoami()["name"]
    repo_id = f"{user}/{args.space}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for name in ("Dockerfile", ".dockerignore", "LICENSE", "NOTICE"):
            shutil.copy(REPO / name, stage / name)
        for folder in ("backend", "web", "samples"):
            shutil.copytree(REPO / folder, stage / folder, ignore=SKIP)
        (stage / "README.md").write_text(CARD)
        api.upload_folder(
            repo_id=repo_id,
            repo_type="space",
            folder_path=stage,
            commit_message="Deploy Unsaid from github.com/enesteve0/unsaid",
            delete_patterns=["*"],
        )

    for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "JUDGE_CODE"):
        if secrets.get(key):
            api.add_space_secret(repo_id, key, secrets[key])
    variables = {
        "PROVIDER": "tokenfactory",
        "HOST": "Hugging Face Spaces",
        "DEMO_MODE": "recorded" if args.mode == "recorded" else "live",
        "PUBLIC_LIVE": "true" if args.mode == "live" else "false",
        "LIVE_UNTIL": args.live_until,
        # Caps per container start (no persistent disk): small, and the public lane has none when judges-only.
        "JUDGE_DAILY_USD": "0.5",
        "PUBLIC_DAILY_USD": "0.5" if args.mode == "live" else "0",
        "MONTHLY_CEILING_USD": "2",
    }
    for key, value in variables.items():
        api.add_space_variable(repo_id, key, value)

    subdomain = repo_id.lower().replace("/", "-").replace("_", "-")
    print(f"Space: https://huggingface.co/spaces/{repo_id}")
    print(
        f"App:   https://{subdomain}.hf.space  (mode {args.mode}{', live until ' + args.live_until if args.live_until else ''})"
    )


if __name__ == "__main__":
    main()
