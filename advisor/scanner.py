from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from advisor import data as data_mod
from advisor import risk as risk_mod
from advisor.risk import RiskProfile
from advisor.signals import Signal, evaluate

log = logging.getLogger("advisor.scanner")

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
INDICES = {"^GSPC": "S&P 500", "^FTSE": "FTSE 100"}


@dataclass(frozen=True)
class Alert:
    signal: Signal
    risk: RiskProfile
    regime: str = "bull"


def lse_open() -> bool:
    now_ldn = datetime.now(LONDON)
    if now_ldn.weekday() >= 5:
        return False
    return now_ldn.replace(hour=8, minute=0, second=0) <= now_ldn <= now_ldn.replace(hour=16, minute=35, second=0)


def nyse_open() -> bool:
    now_ny = datetime.now(NEW_YORK)
    if now_ny.weekday() >= 5:
        return False
    return now_ny.replace(hour=9, minute=30, second=0) <= now_ny <= now_ny.replace(hour=16, minute=5, second=0)


def market_open_now() -> bool:
    return lse_open() or nyse_open()


def load_universe(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        log.error("universe file not found: %s", p)
        return []
    tickers = []
    for line in p.read_text(encoding="utf-8").splitlines():
        t = line.strip().upper()
        if t and not t.startswith("#") and t not in tickers:
            tickers.append(t)
    return tickers


def _drop_partial_bar(df: pd.DataFrame, ticker: str = "") -> pd.DataFrame:
    own_market_open = lse_open() if ticker.upper().endswith(".L") else nyse_open()
    tz = LONDON if ticker.upper().endswith(".L") else NEW_YORK
    today = pd.Timestamp(datetime.now(tz).date())
    if len(df) and df.index[-1] >= today and own_market_open:
        return df.iloc[:-1]
    return df


def get_regime(max_age_seconds: int = 21600) -> tuple[str, str]:
    frames = data_mod.fetch_batch(list(INDICES), period="1y", max_age_seconds=max_age_seconds)
    spx = frames.get("^GSPC")
    if spx is None or len(spx) < 210:
        return "bull", ""
    close = float(spx["Close"].iloc[-1])
    sma200_now = float(spx["Close"].tail(200).mean())
    sma200_prev = float(spx["Close"].tail(220).head(200).mean())
    rising = sma200_now > sma200_prev
    bull = close > sma200_now and rising
    detail = f"S&P 500 {'above' if close > sma200_now else 'below'} 200-day"
    return ("bull" if bull else "bear"), detail


def run_scan(universe_file: str | Path = "universe.txt", max_age_seconds: int = 900,
             respect_market_hours: bool = True) -> tuple[list[Alert], dict]:
    tickers = load_universe(universe_file)
    if not tickers:
        return [], {"scanned": 0, "errors": ["empty universe"], "signals": 0}

    history = data_mod.fetch_batch(tickers, period="2y", max_age_seconds=max_age_seconds)
    removed = data_mod.prune_cache(tickers + list(INDICES))
    if removed:
        log.info("pruned %d stale cache files", len(removed))

    regime, regime_detail = get_regime()
    alerts: list[Alert] = []
    errors: list[str] = []

    for ticker, raw_df in history.items():
        try:
            df = _drop_partial_bar(raw_df, ticker) if respect_market_hours else raw_df
            sigs, stats = evaluate(df, ticker)
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            continue
        if not sigs:
            continue
        rp = risk_mod.assess(
            stats.get("ann_vol", float("nan")),
            stats.get("max_dd_1y", float("nan")),
            stats.get("atr", float("nan")),
            stats.get("close", 1.0),
            dollar_volume=stats.get("dollar_volume", float("nan")),
            ticker=ticker,
        )
        for s in sigs:
            alerts.append(Alert(signal=s, risk=rp, regime=regime))

    alerts.sort(key=lambda a: (a.signal.horizon, -a.signal.strength))
    summary = {
        "scanned": len(history),
        "universe": len(tickers),
        "errors": errors,
        "signals": len(alerts),
        "regime": regime,
        "regime_detail": regime_detail,
        "missing": sorted(set(tickers) - set(history)),
    }
    return alerts, summary
