"""ARIA Gateway — Cloud Boost proxy (Phase 0 of docs/BUSINESS.md).

Holds the single Anthropic API key server-side. Users authenticate with
gateway tokens (`gw_…`); every request is quota-checked and metered
here, before Anthropic sees anything.
"""
