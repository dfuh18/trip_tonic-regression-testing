"""Cost estimation, mirrored from apps/api/src/lib/pricing.ts.

The same rates and the same PRICING_VERSION as the application's own usage
log, so a run's cost (Table 11) is computed the way the product's cost
dashboard computes it. Keep both in sync: when the TypeScript table changes,
this one changes with it and the version with both.
"""

from __future__ import annotations

PRICING_VERSION = "2026-07"

#: USD per million tokens (input, output). Longest-prefix match on the model id.
LLM_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash": (1.5, 9.0),
    "gemini-2.5-flash-lite": (0.1, 0.4),
    "gemini-2.5-flash": (0.3, 2.5),
    "gemini-2.0-flash": (0.1, 0.4),
}
DEFAULT_RATE = LLM_PRICING["gemini-3.5-flash"]


def llm_cost_usd(model: str | None, tokens_input: int, tokens_output: int) -> float:
    rate = DEFAULT_RATE
    best = 0
    for prefix, candidate in LLM_PRICING.items():
        if model and model.startswith(prefix) and len(prefix) > best:
            rate, best = candidate, len(prefix)
    return round((tokens_input * rate[0] + tokens_output * rate[1]) / 1_000_000, 6)
