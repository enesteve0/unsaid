"""Runtime configuration.

Every value can be overridden with an environment variable (see `.env.example`). Model roles map to ordered
fallback chains: the first model is preferred, later ones are used when an earlier one is unavailable.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Role(StrEnum):
    VISION = "vision"  # Nemotron 3.5 Super VL: the only model that can see slides and video
    REASON = "reason"  # Nemotron 3 Ultra: whole-lecture judgement in one 1M-token context
    FAST = "fast"  # Nemotron 3.5 Lightning: many small, latency-sensitive rewrites
    CLASSIFY = "classify"  # Nemotron 3 Nano: high-volume structured classification


TOKEN_FACTORY_URL = "https://api.tokenfactory.nebius.com/v1/"
NVIDIA_BUILD_URL = "https://integrate.api.nvidia.com/v1"

TOKEN_FACTORY_MODELS: dict[Role, list[str]] = {
    Role.VISION: ["nvidia/Nemotron-3.5-Super-VL"],
    Role.REASON: [
        "nvidia/Nemotron-3-Ultra-550b-a55b",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/Nemotron-3.5-Super-VL",
    ],
    Role.FAST: ["nvidia/Nemotron-3_5-Lightning", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"],
    Role.CLASSIFY: ["nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "nvidia/Nemotron-3_5-Lightning"],
}

# build.nvidia.com is for local prompt prototyping only. It does NOT satisfy the hackathon platform rule,
# so the API server refuses to start with this provider unless explicitly allowed.
NVIDIA_BUILD_MODELS: dict[Role, list[str]] = {
    Role.VISION: ["nvidia/nemotron-3.5-super-vl-120b-a12b"],
    Role.REASON: ["nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3-super-120b-a12b"],
    Role.FAST: ["nvidia/nemotron-3.5-lightning-30b-a3b"],
    Role.CLASSIFY: ["nvidia/nemotron-3.5-lightning-30b-a3b"],  # Nano is not enabled on every build account
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    provider: Literal["tokenfactory", "nvidia_build"] = "tokenfactory"
    allow_non_tokenfactory: bool = False

    nebius_api_key: str = ""
    nebius_api_key_backup: str = ""
    nvidia_api_key: str = ""
    tavily_api_key: str = ""
    tf_base_url: str = TOKEN_FACTORY_URL

    # Optional comma-separated overrides of the model chains, e.g. MODEL_REASON="nvidia/a,nvidia/b".
    model_vision: str = ""
    model_reason: str = ""
    model_fast: str = ""
    model_classify: str = ""

    data_dir: Path = Path("data")
    samples_dir: Path = Path("../samples")
    web_dist: Path | None = None  # the built web app; defaults to web/dist in the repository
    # Where this server runs, shown in the footer ("Nebius AI Cloud", "Fly.io"); empty when unknown (local).
    host: str = ""
    # The Serverless Job writes digest.json here (a mounted bucket in production).
    backlog_dir: Path = Path("data/backlog")
    eval_report: Path = Path("eval/report.json")
    demo_mode: Literal["live", "recorded"] = "live"

    # Audio-description timing: plan at 2.5 words/s (150 wpm); describers avoid the 170-180 wpm of normal speech.
    words_per_second: float = 2.5
    speech_lead_seconds: float = 0.3  # synthesis start-up before the first word is heard
    min_gap_seconds: float = 1.2
    speech_guard_seconds: float = 0.15

    # Ultra's reasoning depth for the lesson plan. "medium" sets the chat template's medium_effort flag: on six clips
    # it planned with 58% fewer tokens at the same coverage as "full" (prototype on the NVIDIA API catalog).
    reason_effort: Literal["full", "medium"] = "medium"

    # Access and spend controls (see README "Operations").
    judge_code: str = ""
    public_daily_usd: float = 0.50
    judge_daily_usd: float = 1.50
    monthly_ceiling_usd: float = 30.0
    max_upload_seconds: float = 180.0
    max_upload_mb: int = 200
    # Public runs may use all slots but one, which stays free for judges.
    max_concurrent_runs: int = 3
    # Held against the daily caps for every queued or running run until its real cost is known.
    run_reserve_usd: float = 0.15
    run_timeout_seconds: float = 1800.0
    # Media of live runs (uploads, audio, frames) is deleted after this long; results and text tracks stay.
    keep_media_hours: float = 24.0

    @property
    def api_key(self) -> str:
        return self.nebius_api_key if self.provider == "tokenfactory" else self.nvidia_api_key

    @property
    def base_url(self) -> str:
        return self.tf_base_url if self.provider == "tokenfactory" else NVIDIA_BUILD_URL

    def chain(self, role: Role) -> list[str]:
        override = getattr(self, f"model_{role.value}")
        if override:
            return [m.strip() for m in override.split(",") if m.strip()]
        table = TOKEN_FACTORY_MODELS if self.provider == "tokenfactory" else NVIDIA_BUILD_MODELS
        return list(table[role])


@lru_cache
def get_settings() -> Settings:
    return Settings()
