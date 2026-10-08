"""List prices for the LLMs this platform calls, in USD per 1M tokens.

The cost the Super Admin panel shows is tokens × these rates — what the usage
would cost on each provider's paid plan, even while the free tiers happen to
bill $0. Rates are public list prices at the time of writing; providers change
them, so re-check this table against their pricing pages before relying on a
number for a financial decision. The panel labels the figure "list price".
"""

from __future__ import annotations

from decimal import Decimal

# (input_per_1M, output_per_1M). First substring match on the model name wins.
_MODEL_RATES: list[tuple[str, tuple[str, str]]] = [
    ("gpt-oss-120b", ("0.15", "0.60")),
    ("gpt-oss-20b", ("0.10", "0.50")),
    ("mistral-small", ("0.20", "0.60")),
    ("mistral-medium", ("0.40", "2.00")),
    ("mistral-large", ("2.00", "6.00")),
    ("gpt-4o-mini", ("0.15", "0.60")),
    ("gpt-4o", ("2.50", "10.00")),
]

# Used when the model isn't in the table, so an unlisted model is costed at its
# provider's typical rate instead of silently counting as free.
_PROVIDER_DEFAULT = {
    "groq": ("0.15", "0.60"),
    "mistral": ("0.20", "0.60"),
    "openai": ("2.50", "10.00"),
}

_PER_MILLION = Decimal(1_000_000)


def estimate_cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    rates = next((r for needle, r in _MODEL_RATES if needle in (model or "").lower()), None)
    if rates is None:
        rates = _PROVIDER_DEFAULT.get(provider, ("0", "0"))
    cost = (Decimal(prompt_tokens) * Decimal(rates[0]) + Decimal(completion_tokens) * Decimal(rates[1])) / _PER_MILLION
    return cost.quantize(Decimal("0.000001"))
