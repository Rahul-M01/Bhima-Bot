from __future__ import annotations

"""Shared market helpers: London (GBp) vs US (USD) conventions."""

MIN_DOLLAR_VOLUME = 250_000
MIN_GBP_VOLUME = 80_000_000


def is_london(ticker: str) -> bool:
    return ticker.upper().endswith(".L")


def currency(ticker: str) -> str:
    return "GBP" if is_london(ticker) else "USD"


def fmt_price(ticker: str, value: float) -> str:
    if value != value:
        return "n/a"
    return f"\u00A3{value:,.2f}" if is_london(ticker) else f"${value:,.2f}"


def min_dollar_volume(ticker: str) -> float:
    return MIN_GBP_VOLUME if is_london(ticker) else MIN_DOLLAR_VOLUME


def normalise_currency(df, ticker: str):
    if is_london(ticker):
        return df / 100.0
    return df
