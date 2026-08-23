from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from advisor.indicators import compute_all
from advisor.market import min_dollar_volume


@dataclass(frozen=True)
class Signal:
    ticker: str
    name: str
    horizon: str
    entry: float
    stop: float
    target: float
    strength: float
    rationale: str

    @property
    def rr(self) -> float:
        risk = self.entry - self.stop
        reward = self.target - self.entry
        return round(reward / risk, 2) if risk > 0 else 0.0


SELL_SIGNALS = {"DEATH_CROSS", "BREAKDOWN_200", "RSI_FADE"}


def _val(df: pd.DataFrame, col: str, idx: int) -> float:
    v = df[col].iloc[idx]
    return float(v) if v == v else float("nan")


def _crossed_up(a: pd.Series, b: pd.Series, idx: int) -> bool:
    if idx < 2:
        return False
    d = a.iloc[idx - 2 : idx + 1] - b.iloc[idx - 2 : idx + 1]
    if len(d) < 3 or d.isna().any():
        return False
    return bool(d.iloc[-2] <= 0 and d.iloc[-1] > 0)


def _vol_ratio(ind: pd.DataFrame, idx: int) -> float:
    avg = _val(ind, "VOL_SMA20", idx)
    vol = float(ind["Volume"].iloc[idx])
    return vol / avg if avg and avg == avg else float("nan")


def _swing_at(ind: pd.DataFrame, idx: int, ticker: str) -> list[Signal]:
    out: list[Signal] = []
    close = _val(ind, "Close", idx)
    atr_v = _val(ind, "ATR", idx)
    if not (close == close) or not (atr_v == atr_v) or close <= 0:
        return out

    vr = _vol_ratio(ind, idx)
    hi20 = _val(ind, "HI20", idx)
    rsi_now = _val(ind, "RSI", idx)
    rsi_prev = _val(ind, "RSI", idx - 1)
    sma50 = _val(ind, "SMA50", idx)
    sma200 = _val(ind, "SMA200", idx)

    if close > hi20 and vr >= 1.5 and close > sma50:
        out.append(Signal(ticker, "BREAKOUT_20D", "SWING", close,
                          round(close - 2 * atr_v, 4), round(close + 3 * atr_v, 4),
                          min(vr / 3.0, 1.0), f"Closed above 20-day high on {vr:.1f}x volume"))

    if rsi_prev < 30 <= rsi_now and close > sma200:
        out.append(Signal(ticker, "RSI_RECOVERY", "SWING", close,
                          round(close - 2 * atr_v, 4), round(close + 2.5 * atr_v, 4),
                          min(max((rsi_now - 30) / 15, 0.1), 1.0),
                          f"RSI recovered from oversold ({rsi_prev:.0f} to {rsi_now:.0f}) above the 200-day trend"))

    if _crossed_up(ind["MACD"], ind["MACD_SIG"], idx) and close > sma50 > sma200:
        out.append(Signal(ticker, "MACD_CROSS_UP", "SWING", close,
                          round(close - 2 * atr_v, 4), round(close + 2.5 * atr_v, 4),
                          0.6, "MACD bullish crossover within an established uptrend"))

    low_today = _val(ind, "Low", idx)
    bounced = float(ind["Close"].iloc[idx]) > float(ind["Open"].iloc[idx])
    if sma50 > sma200 and 40 <= rsi_now <= 60 and abs(low_today - sma50) / sma50 < 0.02 and bounced:
        out.append(Signal(ticker, "PULLBACK_SUPPORT", "SWING", close,
                          round(sma50 * 0.98, 4), round(close + 3 * atr_v, 4),
                          0.55, "Bounced off rising 50-day support during a pullback in an uptrend"))
    return out


def _long_at(df: pd.DataFrame, ind: pd.DataFrame, idx: int, ticker: str) -> list[Signal]:
    out: list[Signal] = []
    close = _val(ind, "Close", idx)
    atr_v = _val(ind, "ATR", idx)
    if not (close == close) or not (atr_v == atr_v) or close <= 0:
        return out

    sma50_now = _val(ind, "SMA50", idx)
    sma200_now = _val(ind, "SMA200", idx)

    if idx >= 5:
        d = (ind["SMA50"] - ind["SMA200"]).iloc[idx - 5 : idx + 1].dropna()
        if len(d) == 6 and bool((d.iloc[:-1] <= 0).all()) and d.iloc[-1] > 0:
            out.append(Signal(ticker, "GOLDEN_CROSS", "LONG", close,
                              round(close - 3.5 * atr_v, 4), round(close + 7 * atr_v, 4),
                              0.7, "50-day moving average crossed above the 200-day"))

    window = ind["Close"].iloc[max(0, idx - 64) : idx + 1]
    sma200_win = ind["SMA200"].iloc[max(0, idx - 64) : idx + 1]
    if window.notna().mean() > 0.95 and sma200_win.notna().all():
        above = float((window > sma200_win).mean()) > 0.9
        rising = sma200_win.iloc[-1] > sma200_win.iloc[0]
        near_50 = abs(close - sma50_now) / sma50_now < 0.03
        rsi_now = _val(ind, "RSI", idx)
        if above and rising and near_50 and 35 <= rsi_now <= 60:
            out.append(Signal(ticker, "TREND_CONTINUATION", "LONG", close,
                              round(sma200_now * 0.97, 4), round(close + 7 * atr_v, 4),
                              0.65, "Long-term uptrend holding; price pulled back to the 50-day average"))

    hi55 = _val(ind, "HI55", idx)
    year_high = float(df["Close"].iloc[max(0, idx - 251) : idx + 1].max())
    vr = _vol_ratio(ind, idx)
    if close > hi55 and close >= year_high * 0.995 and vr >= 1.2:
        out.append(Signal(ticker, "NEW_52W_HIGH", "LONG", close,
                          round(max(close - 3.5 * atr_v, year_high * 0.92), 4),
                          round(close + 8 * atr_v, 4),
                          min(vr / 2.5, 1.0), f"New 52-week high on {vr:.1f}x volume (momentum)"))
    return out


def _sell_at(df: pd.DataFrame, ind: pd.DataFrame, idx: int, ticker: str) -> list[Signal]:
    out: list[Signal] = []
    close = _val(ind, "Close", idx)
    atr_v = _val(ind, "ATR", idx)
    if not (close == close) or not (atr_v == atr_v) or close <= 0:
        return out

    sma50_now = _val(ind, "SMA50", idx)
    sma200_now = _val(ind, "SMA200", idx)
    rsi_prev = _val(ind, "RSI", idx - 1)
    rsi_now = _val(ind, "RSI", idx)

    if rsi_prev > 70 >= rsi_now:
        out.append(Signal(ticker, "RSI_FADE", "SWING", close,
                          round(close + 2 * atr_v, 4), round(close - 3 * atr_v, 4),
                          min((rsi_prev - 70) / 15 + 0.3, 1.0),
                          f"Momentum fading from overbought (RSI {rsi_prev:.0f} to {rsi_now:.0f})"))

    prev_close = float(ind["Close"].iloc[idx - 1])
    if prev_close >= sma200_now and close < sma200_now:
        vr = _vol_ratio(ind, idx)
        out.append(Signal(ticker, "BREAKDOWN_200", "SWING", close,
                          round(close + 1.5 * atr_v, 4), round(close - 3 * atr_v, 4),
                          min(max(vr / 2.5, 0.4), 1.0),
                          f"Broke below the 200-day average{f' on {vr:.1f}x volume' if vr == vr else ''}"))

    if idx >= 5:
        d = (ind["SMA50"] - ind["SMA200"]).iloc[idx - 5 : idx + 1].dropna()
        if len(d) == 6 and bool((d.iloc[:-1] >= 0).all()) and d.iloc[-1] < 0:
            out.append(Signal(ticker, "DEATH_CROSS", "LONG", close,
                              round(close + 3.5 * atr_v, 4), round(close - 7 * atr_v, 4),
                              0.7, "50-day moving average crossed below the 200-day"))
    return out


def evaluate_at(df: pd.DataFrame, ind: pd.DataFrame, idx: int, ticker: str) -> list[Signal]:
    return _swing_at(ind, idx, ticker) + _long_at(df, ind, idx, ticker) + _sell_at(df, ind, idx, ticker)


def prepare(df: pd.DataFrame, ticker: str = "") -> pd.DataFrame | None:
    if len(df) < 210:
        return None
    dv = float(((df["Close"] * df["Volume"]).tail(20)).mean())
    if dv < min_dollar_volume(ticker or " "):
        return None
    return compute_all(df)


def evaluate(df: pd.DataFrame, ticker: str, ind: pd.DataFrame | None = None) -> tuple[list[Signal], dict]:
    if ind is None:
        ind = prepare(df, ticker)
    if ind is None:
        return [], {}
    idx = len(ind) - 1
    sigs = evaluate_at(df, ind, idx, ticker)

    returns = ind["Close"].pct_change()
    ann_vol = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) > 10 else float("nan")
    prices = ind["Close"].tail(252)
    dd = float((prices / prices.cummax() - 1).min()) if len(prices) > 20 else float("nan")

    stats = {
        "ann_vol": ann_vol,
        "max_dd_1y": dd,
        "atr": _val(ind, "ATR", idx),
        "close": _val(ind, "Close", idx),
        "rsi": _val(ind, "RSI", idx),
        "dollar_volume": float(((ind["Close"] * ind["Volume"]).tail(20)).mean()),
    }
    return sigs, stats


def analyze_frame(df: pd.DataFrame, ticker: str):
    ind = prepare(df, ticker)
    if ind is None:
        return [], {}, None
    sigs, stats = evaluate(df, ticker, ind=ind)
    return sigs, stats, ind
