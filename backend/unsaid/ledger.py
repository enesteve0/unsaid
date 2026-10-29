"""Per-call cost and latency ledger.

Every Token Factory call is recorded with its tokens, latency and dollar cost at catalog prices, plus the
counterfactual cost had the same text step run on Nemotron 3 Ultra. Vision steps have no Ultra counterfactual
because Ultra cannot see; they are reported at their real cost in both columns.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Price:
    input: float  # USD per 1M prompt tokens
    cached_input: float  # USD per 1M cached prompt tokens
    output: float  # USD per 1M completion tokens (reasoning tokens are billed as output)


# Token Factory public catalog, read 2026-10-26.
PRICES: dict[str, Price] = {
    "nvidia/Nemotron-3_5-Lightning": Price(0.06, 0.06, 0.24),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": Price(0.06, 0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": Price(0.30, 0.06, 0.90),
    "nvidia/Nemotron-3.5-Super-VL": Price(0.30, 0.06, 0.90),
    "nvidia/Nemotron-3-Ultra-550b-a55b": Price(1.00, 0.12, 3.00),
}
# The same models on NVIDIA's API catalog (build.nvidia.com), used for prototyping and the evaluation: priced and
# labelled as their Token Factory equivalents, so costs mean what they would cost on Token Factory.
CATALOG_EQUIVALENT: dict[str, str] = {
    "nvidia/nemotron-3.5-super-vl-120b-a12b": "nvidia/Nemotron-3.5-Super-VL",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "nvidia/nemotron-3.5-lightning-30b-a3b": "nvidia/Nemotron-3_5-Lightning",
    "nvidia/nemotron-nano-3-30b-a3b": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
}
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
VISION_MODELS = {"nvidia/Nemotron-3.5-Super-VL"}

MODEL_LABELS: dict[str, str] = {
    "nvidia/Nemotron-3_5-Lightning": "Nemotron 3.5 Lightning",
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": "Nemotron 3 Nano",
    "nvidia/nemotron-3-super-120b-a12b": "Nemotron 3 Super",
    "nvidia/Nemotron-3.5-Super-VL": "Nemotron 3.5 Super VL",
    "nvidia/Nemotron-3-Ultra-550b-a55b": "Nemotron 3 Ultra",
}


def token_factory_id(model: str) -> str:
    return CATALOG_EQUIVALENT.get(model, model)


def cost_usd(model: str, prompt_tokens: int, cached_tokens: int, completion_tokens: int) -> float:
    price = PRICES.get(token_factory_id(model))
    if price is None:
        return 0.0
    uncached = max(prompt_tokens - cached_tokens, 0)
    return (
        uncached * price.input + cached_tokens * price.cached_input + completion_tokens * price.output
    ) / 1e6


@dataclass
class LedgerEntry:
    stage: str
    role: str
    model: str
    thinking: bool
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: int = 0
    ok: bool = True
    error: str = ""
    request_id: str = ""
    at: float = field(default_factory=time.time)

    @property
    def cost(self) -> float:
        return cost_usd(self.model, self.prompt_tokens, self.cached_tokens, self.completion_tokens)

    @property
    def ultra_counterfactual(self) -> float:
        if token_factory_id(self.model) in VISION_MODELS:
            return self.cost
        return cost_usd(ULTRA, self.prompt_tokens, 0, self.completion_tokens)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cost_usd"] = round(self.cost, 6)
        data["ultra_counterfactual_usd"] = round(self.ultra_counterfactual, 6)
        data["model_label"] = MODEL_LABELS.get(token_factory_id(self.model), self.model)
        return data


@dataclass
class Ledger:
    entries: list[LedgerEntry] = field(default_factory=list)

    def add(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    @property
    def total_cost(self) -> float:
        return sum(e.cost for e in self.entries)

    @property
    def total_counterfactual(self) -> float:
        return sum(e.ultra_counterfactual for e in self.entries)

    def summary(self, video_minutes: float | None = None, accepted_cues: int | None = None) -> dict[str, Any]:
        by_model: dict[str, dict[str, float]] = {}
        for e in self.entries:
            row = by_model.setdefault(
                e.model,
                {"calls": 0, "prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
            )
            row["calls"] += 1
            row["prompt_tokens"] += e.prompt_tokens
            row["cached_tokens"] += e.cached_tokens
            row["completion_tokens"] += e.completion_tokens
            row["cost_usd"] += e.cost
        total = self.total_cost
        out: dict[str, Any] = {
            "calls": len(self.entries),
            "failed_calls": sum(1 for e in self.entries if not e.ok),
            "total_usd": round(total, 6),
            "ultra_only_usd": round(self.total_counterfactual, 6),
            "by_model": {
                MODEL_LABELS.get(token_factory_id(m), m): {
                    k: round(v, 6) if isinstance(v, float) else v for k, v in row.items()
                }
                for m, row in by_model.items()
            },
        }
        if video_minutes:
            out["usd_per_video_minute"] = round(total / video_minutes, 6)
        if accepted_cues:
            out["usd_per_accepted_cue"] = round(total / accepted_cues, 6)
        return out
