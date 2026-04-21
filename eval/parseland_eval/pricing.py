"""Per-model pricing for Anthropic + OpenAI. Rates in USD per million tokens.

Rates verified 2026-04 against vendor pricing pages. Cache multipliers:
- Anthropic: cache writes cost 1.25x input; cache reads cost 0.1x input.
- OpenAI (Structured Outputs models): standard input/output billing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_write_multiplier: float = 1.25
    cache_read_multiplier: float = 0.10


# Anthropic — standard (non-1M-context) pricing, which also covers 1M context
# on Sonnet 4.6 and Opus 4.7 per the April-2026 GA announcement.
ANTHROPIC: Mapping[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(input_per_mtok=3.00, output_per_mtok=15.00),
    "claude-opus-4-7": ModelPricing(input_per_mtok=15.00, output_per_mtok=75.00),
    "claude-haiku-4-5-20251001": ModelPricing(input_per_mtok=1.00, output_per_mtok=5.00),
}

# OpenAI — Structured Outputs supported models.
OPENAI: Mapping[str, ModelPricing] = {
    "gpt-4o-2024-08-06": ModelPricing(input_per_mtok=2.50, output_per_mtok=10.00),
    "gpt-4o-mini": ModelPricing(input_per_mtok=0.15, output_per_mtok=0.60),
    "gpt-4.1": ModelPricing(input_per_mtok=2.00, output_per_mtok=8.00),
    "gpt-4.1-mini": ModelPricing(input_per_mtok=0.40, output_per_mtok=1.60),
}


def _lookup(model: str) -> ModelPricing:
    if model in ANTHROPIC:
        return ANTHROPIC[model]
    if model in OPENAI:
        return OPENAI[model]
    raise KeyError(f"no pricing entry for model {model!r}")


def compute_anthropic_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    """Return USD cost for one Anthropic call given its `response.usage`."""
    p = _lookup(model)
    regular_input = max(0, input_tokens - cache_creation_input_tokens - cache_read_input_tokens)
    cost = (
        regular_input * p.input_per_mtok
        + cache_creation_input_tokens * p.input_per_mtok * p.cache_write_multiplier
        + cache_read_input_tokens * p.input_per_mtok * p.cache_read_multiplier
        + output_tokens * p.output_per_mtok
    ) / 1_000_000
    return round(cost, 6)


def compute_openai_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = _lookup(model)
    cost = (input_tokens * p.input_per_mtok + output_tokens * p.output_per_mtok) / 1_000_000
    return round(cost, 6)
