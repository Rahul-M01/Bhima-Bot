from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from advisor.fundamentals import quality_score
from advisor.market import fmt_price
from advisor.signals import SELL_SIGNALS


@dataclass(frozen=True)
class Recommendation:
    ticker: str
    action: str
    score: int
    confidence: float
    drivers: tuple[str, ...]

    @property
    def gauge(self) -> str:
        pos = int(round((self.score + 100) / 200 * 10))
        bar = ["\u2501"] * 10
        bar[min(max(pos, 0), 9)] = "\u25C6"
        return "[" + "".join(bar) + "]"

    def line(self) -> str:
        return f"**{self.action}** \u2022 {self.confidence:.0f}% confidence \u2022 {self.gauge} ({self.score:+d})"


WEIGHTS = {"trend": 0.35, "momentum": 0.30, "stretch": 0.15, "volume": 0.20}
WEIGHTS_WITH_QUALITY = {
    "trend": 0.28,
    "momentum": 0.24,
    "stretch": 0.08,
    "volume": 0.12,
    "quality": 0.28,
}


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _safe(v) -> float:
    try:
        f = float(v)
        return f if f == f else 0.0
    except Exception:
        return 0.0


def build(ind, ticker: str, win_rates: dict | None = None, regime: str = "bull",
          active_signals=(), fundamentals: dict | None = None) -> Recommendation:
    c = _safe(ind["Close"].iloc[-1])
    sma20 = _safe(ind["SMA20"].iloc[-1]) or c
    sma50 = _safe(ind["SMA50"].iloc[-1]) or c
    sma200 = _safe(ind["SMA200"].iloc[-1]) or c
    sma200_prev = _safe(ind["SMA200"].iloc[-21]) or sma200
    rsi_v = _safe(ind["RSI"].iloc[-1])
    macd_hist = _safe(ind["MACD"].iloc[-1] - ind["MACD_SIG"].iloc[-1])
    macd_hist_prev = _safe(ind["MACD"].iloc[-4] - ind["MACD_SIG"].iloc[-4]) if len(ind) > 4 else 0.0
    roc63 = (c / _safe(ind["Close"].iloc[-64]) - 1.0) if _safe(ind["Close"].iloc[-64]) else 0.0
    vol5 = float(ind["Volume"].tail(5).mean())
    vol60 = float(ind["Volume"].tail(60).mean())

    drivers: list[str] = []
    trend_parts = [
        (_clamp((c / sma50 - 1) * 10), None),
        (_clamp((sma50 / sma200 - 1) * 15), None),
        (_clamp((sma200 / sma200_prev - 1) * 40), None),
    ]
    trend = sum(p[0] for p in trend_parts) / 3
    if trend > 0.3:
        drivers.append("Uptrend: price above rising moving averages")
    elif trend < -0.3:
        drivers.append("Downtrend: price below falling moving averages")

    momentum = (
        0.45 * _clamp(macd_hist / max(sma20 * 0.012, 1e-9))
        + 0.35 * _clamp(roc63 * 4)
        + 0.20 * (1 if rsi_v >= 55 else (-1 if rsi_v <= 40 else 0)) * _clamp(abs(rsi_v - 47.5) / 12.5)
    )
    rsi_state = ""
    if rsi_v >= 75:
        rsi_state = f"Overbought (RSI {rsi_v:.0f})"
    elif rsi_v <= 30:
        rsi_state = f"Oversold (RSI {rsi_v:.0f})"
    if rsi_state:
        drivers.append(rsi_state)

    deviation = c / sma20 - 1
    if abs(deviation) <= 0.03:
        stretch = 0.0
    else:
        stretch = _clamp(-_clamp((deviation - 0.03 * (1 if deviation > 0 else -1))) / 0.05)
    if stretch < -0.5:
        drivers.append(f"Stretched {abs(deviation) * 100:.0f}% above the 20-day average")
    elif stretch > 0.5:
        drivers.append(f"Pulled back {abs(deviation) * 100:.0f}% below the 20-day average")

    vr = vol5 / vol60 if vol60 else 1.0
    volume_score = _clamp((vr - 1.0) / 0.6)
    if volume_score > 0.5:
        drivers.append("Accumulation: volume running above normal")

    if fundamentals:
        q_score, q_drivers = quality_score(fundamentals)
        drivers.extend(q_drivers)
        weights = WEIGHTS_WITH_QUALITY
        raw = {
            "trend": trend,
            "momentum": momentum,
            "stretch": stretch,
            "volume": volume_score,
            "quality": q_score,
        }
    else:
        weights = WEIGHTS
        raw = {
            "trend": trend,
            "momentum": momentum,
            "stretch": stretch,
            "volume": volume_score,
        }

    total = sum(weights[k] * raw[k] for k in weights)

    if regime == "bear":
        total -= 0.18
        drivers.append("Broad market regime is bearish")

    score = int(round(_clamp(total, -1.8, 1.8) / 1.8 * 100))

    agreeing = sum(
        abs(weights[k] * raw[k]) for k in weights if raw[k] * total >= 0
    )
    all_mag = sum(abs(weights[k] * raw[k]) for k in weights) or 1e-9
    agreement = agreeing / all_mag

    confidence = 55 + agreement * 22

    boost = 0.0
    n_weight = 0
    wr_sum = 0.0
    for s in active_signals:
        name = getattr(s, "name", "")
        if name in SELL_SIGNALS or not name:
            continue
        st = (win_rates or {}).get(name, {})
        n = st.get("trades") or 0
        wr = st.get("win_rate")
        if wr and n >= 30:
            wr_sum += wr * n
            n_weight += n
    if n_weight:
        blended = wr_sum / n_weight
        shrunk = 50 + (blended - 50) * (n_weight / (n_weight + 150)) ** 0.5
        boost = (shrunk - 50) * 0.35
    confidence += boost

    if score >= 40:
        action = "STRONG BUY"
    elif score >= 15:
        action = "BUY"
    elif score > -15:
        action = "HOLD"
    elif score > -40:
        action = "SELL"
    else:
        action = "STRONG SELL"

    confidence = float(np.clip(confidence, 52, 88))
    if action == "HOLD":
        drivers.insert(0, "Signals balanced between buyers and sellers")
    if not drivers:
        drivers.append("No dominant technical theme")
    return Recommendation(
        ticker=ticker,
        action=action,
        score=score,
        confidence=float(confidence),
        drivers=tuple(drivers[:4]),
    )


def price_line(ticker: str, value: float) -> str:
    return fmt_price(ticker, value)
