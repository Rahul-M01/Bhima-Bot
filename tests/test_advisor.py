from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from advisor import risk
from advisor.fundamentals import earnings_risk, quality_score
from advisor.indicators import compute_all, rsi
from advisor.market import fmt_price, min_dollar_volume
from advisor.recommend import build as build_recommendation
from advisor.signals import evaluate


def make_df(closes, volume=1_000_000):
    closes = pd.Series(closes, dtype=float)
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    spread = closes * 0.005
    return pd.DataFrame(
        {
            "Open": (closes - spread * 0.3).values,
            "High": (closes + spread).values,
            "Low": (closes - spread).values,
            "Close": closes.values,
            "Volume": float(volume),
        },
        index=idx,
    )


def test_rsi_extremes():
    up = pd.Series(np.linspace(10, 60, 120))
    down = pd.Series(np.linspace(60, 10, 120))
    assert rsi(up).iloc[-1] > 70
    assert rsi(down).iloc[-1] < 30


def test_risk_mapping_extremes():
    calm = risk.assess(ann_vol=0.12, max_dd_1y=-0.08, atr_value=0.8, last_close=100.0)
    wild = risk.assess(ann_vol=0.95, max_dd_1y=-0.62, atr_value=7.0, last_close=100.0)
    assert calm.score == 1
    assert wild.score == 5
    assert calm.max_position_pct > wild.max_position_pct


def test_risk_liquidity_bump():
    base = risk.assess(0.20, -0.15, 1.5, 100.0)
    illiquid = risk.assess(0.20, -0.15, 1.5, 100.0, dollar_volume=1000.0, ticker="AAPL")
    assert illiquid.score == min(base.score + 1, 5)


def test_currency_helpers():
    assert fmt_price("VOD.L", 72.5).startswith("\u00A3")
    assert fmt_price("AAPL", 232.4).startswith("$")
    assert min_dollar_volume("HSBA.L") > min_dollar_volume("AAPL")


def test_evaluate_filters_illiquid():
    n = 260
    closes = 50 + np.cumsum(np.random.default_rng(7).normal(0, 0.4, n))
    df = make_df(closes, volume=500)
    sigs, stats = evaluate(df, "AAPL")
    assert sigs == [] and stats == {}


def test_recommendation_directions():
    up = make_df(50 * (1.0009 ** np.arange(420)))
    ind_up = compute_all(up)
    rec_up = build_recommendation(ind_up, "AAPL")
    assert rec_up.action in ("BUY", "STRONG BUY")
    assert rec_up.score > 0

    dn = make_df(300 * (0.9991 ** np.arange(420)))
    ind_dn = compute_all(dn)
    rec_dn = build_recommendation(ind_dn, "AAPL")
    assert rec_dn.action in ("SELL", "STRONG SELL")
    assert rec_dn.score < 0

    bear = build_recommendation(ind_up, "AAPL", regime="bear")
    assert bear.score <= rec_up.score


def test_recommendation_confidence_bounds():
    up = make_df(50 * (1.001 ** np.arange(420)) * (1 + np.sin(np.arange(420)) * 0.002))
    ind = compute_all(up)
    rec = build_recommendation(ind, "AAPL")
    assert 52 <= rec.confidence <= 88
    assert len(rec.drivers) >= 1


def test_evaluate_no_signals_on_short_history():
    df = make_df([50] * 100)
    sigs, _ = evaluate(df, "AAPL")
    assert sigs == []


def test_quality_score_directions():
    strong = {
        "revenueGrowth": 0.25,
        "profitMargins": 0.22,
        "debtToEquity": 40.0,
        "freeCashflow": 5_000_000_000,
    }
    weak = {
        "revenueGrowth": -0.12,
        "profitMargins": 0.01,
        "debtToEquity": 250.0,
        "freeCashflow": -1_000_000,
    }
    s_strong, d_strong = quality_score(strong)
    s_weak, _ = quality_score(weak)
    assert s_strong > 0.7 and len(d_strong) >= 2
    assert s_weak < -0.6
    assert quality_score(None)[0] == 0.0


def test_recommendation_fundamentals_blend():
    up = make_df(50 * (1.001 ** np.arange(420)))
    ind = compute_all(up)
    base = build_recommendation(ind, "AAPL").score
    good = build_recommendation(
        ind, "AAPL",
        fundamentals={"revenueGrowth": 0.3, "profitMargins": 0.25, "debtToEquity": 30.0},
    ).score
    bad = build_recommendation(
        ind, "AAPL",
        fundamentals={"revenueGrowth": -0.15, "profitMargins": 0.01, "debtToEquity": 260.0},
    ).score
    assert good > base
    assert bad < base


def test_earnings_risk_windows():
    from datetime import datetime, timezone

    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    soon = datetime(2026, 8, 26, tzinfo=timezone.utc)
    far = datetime(2026, 10, 30, tzinfo=timezone.utc)
    hit, note = earnings_risk("AAPL", today=now, known_date=soon)
    assert hit and "3 days" in note
    miss, _ = earnings_risk("AAPL", today=now, known_date=far)
    assert not miss
    none_hit, _ = earnings_risk("AAPL", today=now, known_date=None)
    assert not none_hit
