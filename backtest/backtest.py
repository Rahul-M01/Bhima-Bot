from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from advisor import data as data_mod
from advisor.scanner import load_universe
from advisor.signals import SELL_SIGNALS, prepare, evaluate_at

MAX_HOLD = {"SWING": 15, "LONG": 120}
COOLDOWN = {"SWING": 10, "LONG": 40}
DEFAULT_FEE_BPS = 15.0
DEAD_FILE = Path(__file__).resolve().parent / "universe_dead.txt"
HAIRCUT_WIN_PP = 1.5
HAIRCUT_AVG_PCT = 0.20
SIGNAL_HORIZON = {
    "BREAKOUT_20D": "SWING",
    "RSI_RECOVERY": "SWING",
    "MACD_CROSS_UP": "SWING",
    "PULLBACK_SUPPORT": "SWING",
    "RSI_FADE": "SWING",
    "BREAKDOWN_200": "LONG",
    "GOLDEN_CROSS": "LONG",
    "TREND_CONTINUATION": "LONG",
    "NEW_52W_HIGH": "LONG",
    "DEATH_CROSS": "LONG",
}


def simulate(df: pd.DataFrame, entry_idx: int, entry: float, stop: float, target: float, horizon: str):
    max_hold = MAX_HOLD[horizon]
    end = min(len(df), entry_idx + max_hold)
    for i in range(entry_idx, end):
        o, h, l = df["Open"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
        if l <= stop and h >= target:
            return float(o if o <= stop else stop), i - entry_idx + 1, "stop"
        if l <= stop:
            return float(min(o, stop)), i - entry_idx + 1, "stop"
        if h >= target:
            return float(max(o, target) if o >= target else target), i - entry_idx + 1, "target"
    return float(df["Close"].iloc[end - 1]), end - entry_idx, "timeout"


def benchmark_avg(history: dict[str, pd.DataFrame], hold: int) -> float | None:
    rets = []
    for df in history.values():
        closes = df["Close"]
        for start in range(210, len(closes) - hold - 1, 5):
            base = float(closes.iloc[start])
            fwd = float(closes.iloc[start + hold])
            rets.append(fwd / base - 1)
    return round(float(np.mean(rets)) * 100, 2) if rets else None


def load_dead_candidates() -> list[str]:
    if not DEAD_FILE.exists():
        return []
    out = []
    for line in DEAD_FILE.read_text(encoding="utf-8").splitlines():
        t = line.strip().upper()
        if t and not t.startswith("#"):
            out.append(t)
    return out


def run(universe_file: str, period: str = "5y", fee_bps: float = DEFAULT_FEE_BPS,
        include_dead: bool = True) -> dict:
    tickers = load_universe(universe_file)
    dead_candidates = load_dead_candidates() if include_dead else []
    fetchable_dead = []

    history = data_mod.fetch_batch(tickers, period=period, max_age_seconds=10**9)
    if dead_candidates:
        dead_frames = data_mod.fetch_batch(dead_candidates, period=period, max_age_seconds=10**9)
        for t, df in dead_frames.items():
            if len(df) >= 210 and df.index[-1] < pd.Timestamp.now() - pd.Timedelta(days=45):
                history[t] = df
                fetchable_dead.append(t)

    fee_pct = fee_bps / 10_000 * 2
    trades: dict[str, list[dict]] = defaultdict(list)
    for ticker, df in history.items():
        ind = prepare(df, ticker)
        if ind is None:
            continue
        last_fire: dict[str, int] = {}
        for idx in range(210, len(ind) - 2):
            for sig in evaluate_at(df, ind, idx, ticker):
                prev = last_fire.get(sig.name, -10**9)
                if idx - prev < COOLDOWN[sig.horizon]:
                    continue
                last_fire[sig.name] = idx
                exit_price, days, outcome = simulate(df, idx + 1, sig.entry, sig.stop, sig.target, sig.horizon)
                gross = exit_price / sig.entry - 1
                net = gross - fee_pct
                if sig.name in SELL_SIGNALS:
                    net = -net + fee_pct * 2
                    if outcome == "target":
                        outcome = "exit_validated"
                    elif outcome == "stop":
                        outcome = "signal_failed"
                trades[sig.name].append(
                    {
                        "ticker": ticker,
                        "date": str(ind.index[idx].date()),
                        "year": ind.index[idx].year,
                        "ret_pct": round(net * 100, 3),
                        "days": days,
                        "outcome": outcome,
                    }
                )

    benchmarks = {
        "SWING": benchmark_avg(history, MAX_HOLD["SWING"]),
        "LONG": benchmark_avg(history, MAX_HOLD["LONG"]),
    }

    stats: dict[str, dict] = {}
    for name, rows in sorted(trades.items()):
        rets = np.array([r["ret_pct"] for r in rows])
        wins = rets > 0
        horizon = SIGNAL_HORIZON[name]
        yearly = {}
        for y in sorted({r["year"] for r in rows}):
            yr = np.array([r["ret_pct"] for r in rows if r["year"] == y])
            yearly[str(y)] = {
                "trades": int(len(yr)),
                "win_rate": round(float((yr > 0).mean()) * 100, 1),
                "avg_ret_pct": round(float(yr.mean()), 2),
            }
        raw_win = round(float(wins.mean()) * 100, 1) if len(rets) else None
        raw_avg = round(float(rets.mean()), 2) if len(rets) else None
        stats[name] = {
            "horizon": horizon,
            "fees_bps_round_trip": fee_bps * 2,
            "benchmark_buyhold_pct": benchmarks[horizon],
            "trades": int(len(rets)),
            "win_rate": raw_win,
            "avg_ret_pct": raw_avg,
            "adj_win_rate": round(raw_win - HAIRCUT_WIN_PP, 1) if raw_win is not None else None,
            "adj_avg_ret_pct": round(raw_avg - HAIRCUT_AVG_PCT, 2) if raw_avg is not None else None,
            "median_ret_pct": round(float(np.median(rets)), 2) if len(rets) else None,
            "best_pct": round(float(rets.max()), 2) if len(rets) else None,
            "worst_pct": round(float(rets.min()), 2) if len(rets) else None,
            "avg_days_held": round(float(np.mean([r["days"] for r in rows])), 1) if rows else None,
            "target_hits_pct": (
                round(sum(r["outcome"] in ("target", "exit_validated") for r in rows) / len(rows) * 100, 1)
                if rows
                else None
            ),
            "yearly": yearly,
        }
        if name in SELL_SIGNALS:
            stats[name]["interpretation"] = "Exit advisory: win% = share of cases where downside played out"

    stats["_meta"] = {
        "universe_size": len(tickers),
        "delisted_included": sorted(fetchable_dead),
        "survivorship_note": (
            f"Adjusted columns subtract a conservative haircut (-{HAIRCUT_WIN_PP}pp win rate, "
            f"-{HAIRCUT_AVG_PCT}% avg) to compensate for survivorship bias that free data cannot remove."
        ),
    }

    out_path = Path(__file__).resolve().parent.parent / "backtest" / "stats.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def print_report(stats: dict) -> None:
    signals = {k: v for k, v in stats.items() if not k.startswith("_")}
    if not signals:
        print("No trades generated - check universe file or data.")
        return
    meta = stats.get("_meta", {})
    if meta.get("delisted_included"):
        print(f"Survivorship set: included {len(meta['delisted_included'])} delisted tickers ({', '.join(meta['delisted_included'])})")
    header = f"{'Signal':<20}{'Horizon':<9}{'Trades':>7}{'Win%':>8}{'Adj%':>8}{'Avg%':>7}{'Adj%':>7}{'Med%':>8}{'Worst%':>9}{'B&H%':>7}"
    print(header)
    print("-" * len(header))
    for name, s in signals.items():
        print(
            f"{name:<20}{s['horizon']:<9}{s['trades']:>7}{s['win_rate']:>8}"
            f"{s['adj_win_rate']:>8}{s['avg_ret_pct']:>7}{s['adj_avg_ret_pct']:>7}"
            f"{s['median_ret_pct']:>8}{s['worst_pct']:>9}{s['benchmark_buyhold_pct']:>7}"
        )
    print()
    print(f"Adj columns = conservative survivorship haircut (win -{HAIRCUT_WIN_PP}pp, avg -{HAIRCUT_AVG_PCT}%).")
    print("Yearly win-rate stability:")
    for name, s in signals.items():
        years = " ".join(f"{y}:{v['win_rate']}%" for y, v in s["yearly"].items())
        print(f"  {name:<20} {years}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="universe.txt")
    parser.add_argument("--period", default="5y")
    parser.add_argument("--fee-bps", type=float, default=DEFAULT_FEE_BPS)
    parser.add_argument("--no-dead", action="store_true")
    args = parser.parse_args()
    results = run(args.universe, args.period, args.fee_bps, include_dead=not args.no_dead)
    print_report(results)
