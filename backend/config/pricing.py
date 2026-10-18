"""Pricing configuration — single source for cost estimates in the usage ledger.

All prices are USD per million tokens. Values here were verified against
https://platform.claude.com/docs/en/about-claude/pricing (2026-10). Ollama
inference is free (0/0). Override any of these via the environment
(`ARIA_PRICE_INPUT_MTOK`, `ANTHROPIC_PRICE_INPUT_MTOK`, …) or edit this file —
never scatter prices through the codebase.

Models missing from MODEL_PRICES fall back to the provider defaults in
config/settings.py, and every cost figure in the ledger is flagged
`cost_is_estimate: True` — they are estimates from configuration, not bills.
"""

# Verified current Claude API IDs (docs 2026-10): base input / output $/MTok.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-fable-5-1": (10.0, 50.0),
}


def price_for(provider: str, model: str) -> tuple[float, float]:
    """(input, output) USD per MTok for a provider+model, from config only."""
    if provider == "anthropic":
        if model in MODEL_PRICES:
            return MODEL_PRICES[model]
        try:
            from config.settings import settings

            return (
                settings.anthropic_price_input_mtok,
                settings.anthropic_price_output_mtok,
            )
        except Exception:
            return (0.10, 0.50)
    # Local inference (Ollama) — free unless overridden by env
    try:
        from config.settings import settings

        return (settings.aria_price_input_mtok, settings.aria_price_output_mtok)
    except Exception:
        return (0.0, 0.0)
