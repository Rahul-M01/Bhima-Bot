from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
FUND_CACHE = ROOT / "logs" / "fundamentals_cache.json"
EARN_CACHE = ROOT / "logs" / "earnings_cache.json"

FUND_TTL = 7 * 86400
EARN_TTL = 86400


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _fresh(entry: dict, ttl: float) -> bool:
    return isinstance(entry, dict) and (time.time() - entry.get("ts", 0)) < ttl


def get_fundamentals(ticker: str) -> dict | None:
    cache = _load(FUND_CACHE)
    entry = cache.get(ticker)
    if _fresh(entry, FUND_TTL):
        return entry["data"]
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        log.debug("fundamentals fetch failed %s: %s", ticker, exc)
        info = {}
    keys = (
        "trailingPE", "forwardPE", "priceToBook", "debtToEquity",
        "revenueGrowth", "earningsGrowth", "profitMargins",
        "dividendYield", "marketCap", "freeCashflow",
    )
    data = {k: info.get(k) for k in keys if info.get(k) is not None}
    if not data:
        if entry and isinstance(entry.get("data"), dict):
            return entry["data"]
        return None
    cache[ticker] = {"ts": time.time(), "data": data}
    _save(FUND_CACHE, cache)
    return data


def get_next_earnings(ticker: str):
    cache = _load(EARN_CACHE)
    entry = cache.get(ticker)
    if _fresh(entry, EARN_TTL):
        raw = entry.get("iso")
        return datetime.fromisoformat(raw) if raw else None
    nxt = None
    try:
        cal = yf.Ticker(ticker).calendar
        rows = []
        if isinstance(cal, dict):
            rows = cal.get("Earnings Date") or []
        elif cal is not None and hasattr(cal, "loc"):
            try:
                rows = cal.loc["Earnings Date"]
            except Exception:
                rows = []
        if isinstance(rows, (list, tuple)) and rows:
            first = rows[0]
            nxt = first if isinstance(first, datetime) else datetime.fromisoformat(str(first)[:10])
            if nxt.tzinfo is None:
                nxt = nxt.replace(tzinfo=timezone.utc)
    except Exception as exc:
        log.debug("earnings fetch failed %s: %s", ticker, exc)
    cache[ticker] = {"ts": time.time(), "iso": nxt.isoformat() if nxt else None}
    _save(EARN_CACHE, cache)
    return nxt


def earnings_risk(ticker: str, window_days: int = 6, today: datetime | None = None,
                  known_date: datetime | None = ...) -> tuple[bool, str]:
    now = today or datetime.now(timezone.utc)
    date = get_next_earnings(ticker) if known_date is ... else known_date
    if date is None:
        return False, ""
    days = (date - now).days
    if 0 <= days <= window_days:
        label = "today" if days == 0 else f"in {days} day{'s' if days > 1 else ''}"
        return True, f"\u26A0\uFE0F Earnings {label} ({date:%d %b}) \u2013 volatility likely"
    return False, ""


def quality_score(info: dict | None) -> tuple[float, list[str]]:
    if not info:
        return 0.0, []
    score = 0.0
    drivers: list[str] = []
    growth = info.get("revenueGrowth")
    if isinstance(growth, (int, float)):
        if growth > 0.20:
            score += 0.40
            drivers.append(f"Quality: revenue growing +{growth * 100:.0f}% y/y")
        elif growth > 0.08:
            score += 0.25
            drivers.append(f"Quality: solid revenue growth (+{growth * 100:.0f}% y/y)")
        elif growth < -0.05:
            score -= 0.30
            drivers.append(f"Quality: revenue shrinking ({growth * 100:.0f}% y/y)")

    margin = info.get("profitMargins")
    if isinstance(margin, (int, float)):
        if margin > 0.15:
            score += 0.30
            drivers.append(f"Quality: strong margins ({margin * 100:.0f}%)")
        elif margin < 0.03:
            score -= 0.20
            drivers.append(f"Quality: thin margins ({margin * 100:.0f}%)")

    de = info.get("debtToEquity")
    if isinstance(de, (int, float)):
        if de > 180:
            score -= 0.30
            drivers.append(f"Leverage high (D/E {de:.0f})")
        elif de < 60:
            score += 0.15
            drivers.append(f"Balance sheet conservative (D/E {de:.0f})")

    fcf = info.get("freeCashflow")
    if isinstance(fcf, (int, float)):
        if fcf > 0:
            score += 0.15
        else:
            score -= 0.15
            drivers.append("Cash burn: negative free cash flow")

    return max(-1.0, min(1.0, score)), drivers[:3]


def fmt_fundamentals(ticker: str, info: dict | None) -> str:
    if not info:
        return "n/a"
    parts = []
    pe = info.get("trailingPE")
    parts.append(f"P/E {pe:.1f}" if isinstance(pe, (int, float)) else "P/E -")
    g = info.get("revenueGrowth")
    parts.append(f"Rev {g * 100:+.0f}%" if isinstance(g, (int, float)) else "Rev -")
    de = info.get("debtToEquity")
    parts.append(f"D/E {de:.0f}" if isinstance(de, (int, float)) else "D/E -")
    dy = info.get("dividendYield")
    if isinstance(dy, (int, float)):
        pct = dy * 100 if abs(dy) <= 1 else dy
        parts.append(f"Div {pct:.1f}%")
    return " \u2022 ".join(parts)
