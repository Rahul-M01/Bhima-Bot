from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from advisor.market import is_london, normalise_currency

log = logging.getLogger("advisor.data")

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(ticker: str, period: str = "2y") -> Path:
    safe = ticker.replace("/", "_").replace("^", "IDX_")
    return CACHE_DIR / f"{safe}.{period}.parquet"


def _load_cache(ticker: str, max_age_seconds: int, period: str) -> pd.DataFrame | None:
    path = _cache_path(ticker, period)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > max_age_seconds:
        return None
    try:
        df = pd.read_parquet(path)
        return df if not df.empty else None
    except Exception:
        return None


def _save_cache(ticker: str, df: pd.DataFrame, period: str) -> None:
    try:
        df.to_parquet(_cache_path(ticker, period))
    except Exception as exc:
        log.debug("cache write failed for %s: %s", ticker, exc)


def normalise_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(0):
            df = df[ticker]
        else:
            return pd.DataFrame()
    df = df.rename(columns=str.title)
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    if len(keep) < 5 or df.empty:
        return pd.DataFrame()
    df = df[keep].dropna(subset=["Close"])
    df = df[~df.index.duplicated(keep="last")]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.astype(float)
    if is_london(ticker):
        prices = normalise_currency(df[["Open", "High", "Low", "Close"]], ticker)
        df[["Open", "High", "Low", "Close"]] = prices
    return df


def _download_chunk(chunk: list[str], period: str, attempts: int = 3) -> pd.DataFrame | None:
    delay = 2.0
    for attempt in range(attempts):
        try:
            raw = yf.download(
                tickers=chunk,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
            if raw is not None and not raw.empty:
                return raw
        except Exception as exc:
            log.warning("download attempt %d failed for %s: %s", attempt + 1, chunk[:3], exc)
        if attempt < attempts - 1:
            time.sleep(delay)
            delay *= 2.5
    return None


def fetch_batch(
    tickers: list[str],
    period: str = "2y",
    max_age_seconds: int = 900,
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for t in tickers:
        cached = _load_cache(t, max_age_seconds, period)
        if cached is not None:
            result[t] = cached
        else:
            missing.append(t)

    for i in range(0, len(missing), 100):
        chunk = missing[i : i + 100]
        raw = _download_chunk(chunk, period)
        if raw is not None:
            for t in chunk:
                try:
                    df = normalise_frame(raw, t)
                except Exception as exc:
                    log.debug("normalise failed for %s: %s", t, exc)
                    continue
                if len(df) >= 60:
                    _save_cache(t, df, period)
                    result[t] = df
        if i + 100 < len(missing):
            time.sleep(1.0)

    return result


def prune_cache(valid_tickers: list[str]) -> list[str]:
    valid = {_cache_path(t).name.rsplit(".parquet", 1)[0] for t in valid_tickers}
    removed = []
    for f in CACHE_DIR.glob("*.parquet"):
        key = f.name.rsplit(".parquet", 1)[0].rsplit(".", 1)[0]
        if key not in valid:
            removed.append(f.stem)
            f.unlink(missing_ok=True)
    return removed
