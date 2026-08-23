from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    out = out.replace([np.inf], 100.0)
    return out.fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def annualised_volatility(close: pd.Series, window: int = 60) -> float:
    returns = close.pct_change().dropna().tail(window)
    if len(returns) < 10:
        return float("nan")
    return float(returns.std() * np.sqrt(252))


def max_drawdown(close: pd.Series, window: int = 252) -> float:
    prices = close.tail(window)
    if len(prices) < 20:
        return float("nan")
    running_max = prices.cummax()
    dd = prices / running_max - 1
    return float(dd.min())


def volume_ratio(volume: pd.Series, window: int = 20) -> float:
    recent = volume.iloc[-1]
    avg = volume.tail(window).mean()
    if not avg or np.isnan(avg):
        return float("nan")
    return float(recent / avg)


def dollar_volume_avg(df: pd.DataFrame, window: int = 20) -> float:
    dv = (df["Close"] * df["Volume"]).tail(window)
    return float(dv.mean()) if len(dv) else 0.0


def pct_above_high(close: pd.Series, window: int = 252) -> float:
    ref = close.tail(window).max()
    if not ref or np.isnan(ref):
        return float("nan")
    return float(close.iloc[-1] / ref - 1)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["SMA20"] = sma(out["Close"], 20)
    out["SMA50"] = sma(out["Close"], 50)
    out["SMA200"] = sma(out["Close"], 200)
    out["RSI"] = rsi(out["Close"])
    macd_line, macd_sig, _ = macd(out["Close"])
    out["MACD"] = macd_line
    out["MACD_SIG"] = macd_sig
    out["ATR"] = atr(out["High"], out["Low"], out["Close"])
    out["VOL_SMA20"] = sma(out["Volume"].astype(float), 20)
    out["HI20"] = out["High"].rolling(20).max().shift(1)
    out["HI55"] = out["High"].rolling(55).max().shift(1)
    return out
