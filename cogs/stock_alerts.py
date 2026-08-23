from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
import yfinance as yf
from discord import Embed
from discord.ext import commands, tasks

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from advisor import data as advisor_data  # noqa: E402
from advisor.fundamentals import (  # noqa: E402
    earnings_risk,
    fmt_fundamentals,
    get_fundamentals,
)
from advisor.market import fmt_price  # noqa: E402
from advisor.recommend import build as build_recommendation  # noqa: E402
from advisor.risk import assess  # noqa: E402
from advisor.scanner import get_regime, market_open_now, run_scan  # noqa: E402
from advisor.signals import SELL_SIGNALS, analyze_frame  # noqa: E402

log = logging.getLogger(__name__)

CONFIG_FILE = ROOT_DIR / "logs" / "stock_alerts_config.json"
STATE_FILE = ROOT_DIR / "logs" / "stock_alerts_state.json"
PORTFOLIO_FILE = ROOT_DIR / "logs" / "portfolios.json"
STATS_FILE = ROOT_DIR / "backtest" / "stats.json"
UNIVERSE_FILE = ROOT_DIR / "universe.txt"

DEFAULT_CHANNEL_ID = int(os.getenv("STOCK_ALERT_CHANNEL_ID", "1487671397525491813"))
SCAN_INTERVAL = int(os.getenv("STOCK_SCAN_INTERVAL_MINUTES", "20"))
ALERT_COOLDOWN_HOURS = 72
MAX_ALERTS_PER_CYCLE = 15

RISK_COLOURS = {1: 0x2ECC71, 2: 0x27AE60, 3: 0xF1C40F, 4: 0xE67E22, 5: 0xE74C3C}
ACTION_COLOURS = {
    "STRONG BUY": 0x145A32,
    "BUY": 0x2ECC71,
    "HOLD": 0xF1C40F,
    "SELL": 0xE67E22,
    "STRONG SELL": 0xC0392B,
}


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_win_rates() -> dict:
    return load_json(STATS_FILE, {})


def passes_quality(signal_name: str) -> bool:
    st = load_win_rates().get(signal_name) or {}
    n = st.get("trades") or 0
    wr = st.get("win_rate")
    if wr is None or n < 30:
        return True
    threshold = 55.0 if signal_name in SELL_SIGNALS else 45.0
    return wr >= threshold


def fmt_pct(v) -> str:
    if v is None or v != v:
        return "n/a"
    return f"{v * 100:.1f}%"


def _prune_state(state: dict) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERT_COOLDOWN_HOURS * 2)
    out = {}
    for k, iso in state.items():
        try:
            if datetime.fromisoformat(iso) >= cutoff:
                out[k] = iso
        except Exception:
            pass
    return out


def build_alert_embed(signal, risk_profile, regime: str = "bull", earn_note: str = "") -> Embed:
    s = signal
    r = risk_profile
    is_sell = s.name in SELL_SIGNALS
    stop_pct = (s.stop / s.entry - 1) * 100 if s.entry else 0
    tgt_pct = (s.target / s.entry - 1) * 100 if s.entry else 0
    arrow = "\U0001F53B SELL" if is_sell else ("\U0001F7E1" if r.score >= 4 else r.emoji)
    emb = Embed(
        title=f"{arrow} {s.horizon} \u2022 {s.name} \u2014 {s.ticker}",
        description=s.rationale,
        colour=RISK_COLOURS[r.score],
    )
    emb.add_field(name="Entry", value=fmt_price(s.ticker, s.entry), inline=True)
    emb.add_field(name="Stop level", value=f"{fmt_price(s.ticker, s.stop)} ({stop_pct:+.1f}%)", inline=True)
    emb.add_field(name="Target", value=f"{fmt_price(s.ticker, s.target)} ({tgt_pct:+.1f}%)", inline=True)
    danger_score = min(r.score + (1 if earn_note and not is_sell else 0), 5)
    danger_label = f"**{danger_score}/5 \u2013 {risk_profile.LABELS[danger_score][0]}**"
    if earn_note and not is_sell:
        danger_label += "\n+1 event risk (earnings)"
    emb.add_field(name="Danger level", value=danger_label, inline=True)
    emb.add_field(name="Market regime", value="\U0001F4C8 Bullish" if regime == "bull" else "\U0001F4CA Bearish \u2013 extra caution", inline=True)
    if not is_sell:
        emb.add_field(name="Suggested max position", value=f"\u2264 {r.max_position_pct:.0f}% of portfolio", inline=True)
    if earn_note:
        emb.add_field(name="Event risk", value=earn_note, inline=False)

    stats = load_win_rates().get(s.name)
    bits = []
    if stats and (stats.get("trades") or 0) >= 30 and stats.get("win_rate") is not None:
        bits.append(f"Historical: {stats['win_rate']}% win rate over {stats['trades']} backtested trades (net of fees)")
    bits.append("Not financial advice \u2022 markets are never certain")
    emb.set_footer(text=" \u2022 ".join(bits))
    return emb


class StockAlerts(commands.Cog):
    """Market scanner: signals, danger ratings, Revolut-style verdicts, portfolio tracking."""

    def __init__(self, bot):
        self.bot = bot
        self.last_summary: dict = {}
        self.last_signal_count = "-"
        self.alerts_sent_today = 0
        self.day_key = ""
        cfg = load_json(CONFIG_FILE, {})
        if cfg.get("enabled"):
            channel_id = cfg.get("channel_id", DEFAULT_CHANNEL_ID)
            log.info("Resuming stock alerts to channel %s", channel_id)
            self._start_loop(channel_id)

    def cog_unload(self):
        if self.scan_loop.is_running():
            self.scan_loop.cancel()

    def _start_loop(self, channel_id: int):
        if self.scan_loop.is_running():
            self.scan_loop.cancel()
        self.scan_loop.current_channel = channel_id
        self.scan_loop.start(channel_id)

    @tasks.loop(minutes=SCAN_INTERVAL)
    async def scan_loop(self, channel_id: int):
        try:
            if not market_open_now():
                log.info("Markets closed - skipping stock scan")
                return
            log.info("Stock scan starting")
            alerts, summary = await asyncio.to_thread(
                run_scan, str(UNIVERSE_FILE), max_age_seconds=900
            )
            self.last_summary = summary
            self.last_signal_count = len(alerts)
            posted = await self.post_alerts(channel_id, alerts)
            log.info(
                "Stock scan done: %s/%s tickers, %d signals (%s regime), %d posted",
                summary.get("scanned"),
                summary.get("universe"),
                len(alerts),
                summary.get("regime"),
                posted,
            )
        except Exception:
            log.exception("Stock scan loop error")

    async def post_alerts(self, channel_id: int, alerts) -> int:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                log.error("Alert channel %s not found", channel_id)
                return 0

        state = _prune_state(load_json(STATE_FILE, {}))
        now = datetime.now(timezone.utc)
        cutoff = timedelta(hours=ALERT_COOLDOWN_HOURS)
        posted = 0
        for alert in sorted(alerts, key=lambda a: -a.signal.strength)[:MAX_ALERTS_PER_CYCLE]:
            key = f"{alert.signal.ticker}:{alert.signal.name}"
            if not passes_quality(alert.signal.name):
                continue
            earn_note = ""
            if alert.signal.name not in SELL_SIGNALS:
                try:
                    _, earn_note = await asyncio.wait_for(
                        asyncio.to_thread(earnings_risk, alert.signal.ticker), timeout=15
                    )
                except Exception:
                    earn_note = ""
            last_iso = state.get(key)
            if last_iso:
                try:
                    if now - datetime.fromisoformat(last_iso) < cutoff:
                        continue
                except Exception:
                    pass
            try:
                await channel.send(embed=build_alert_embed(alert.signal, alert.risk, alert.regime, earn_note))
                state[key] = now.isoformat()
                save_json(STATE_FILE, state)
                posted += 1
                self._count_alert()
                await asyncio.sleep(1.5)
            except Exception:
                log.exception("Failed to send stock alert %s", key)
        return posted

    def _count_alert(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.day_key:
            self.day_key = today
            self.alerts_sent_today = 0
        self.alerts_sent_today += 1

    @scan_loop.before_loop
    async def before_scan(self):
        await self.bot.wait_until_ready()

    @commands.group(name="alerts", invoke_without_command=True, help="Stock scanner controls.")
    async def alerts_group(self, ctx):
        await ctx.send(
            "Usage:\n"
            "`!alerts start [#channel]` \u2013 begin scanning & posting signals\n"
            "`!alerts stop` \u2013 stop the scanner only (bot stays up)\n"
            "`!alerts scan` \u2013 force one scan right now\n"
            "`!alerts status` \u2013 scanner status\n"
            "`!alerts add/remove TICKER` / `!alerts list` \u2013 manage universe\n"
            "`!alerts health` \u2013 dead/problem tickers\n"
            "`!analyze TICKER` \u2013 full analysis + buy/hold/sell verdict\n"
            "`!portfolio show/add/remove/clear` \u2013 track your holdings"
        )

    @alerts_group.command(name="start")
    @commands.has_permissions(manage_guild=True)
    async def alerts_start(self, ctx, channel: discord.TextChannel = None):
        target_id = channel.id if channel else DEFAULT_CHANNEL_ID
        target = self.bot.get_channel(target_id) or ctx.channel
        already = self.scan_loop.is_running() and getattr(self.scan_loop, "current_channel", None) == target_id
        if not already:
            self._start_loop(target_id)
        save_json(CONFIG_FILE, {"enabled": True, "channel_id": target_id})
        state_word = "already running" if already else "**started**"
        await ctx.send(
            f"\U0001F4C8 Stock alerts {state_word} \u2192 {target.mention}\n"
            f"Scanning every **{SCAN_INTERVAL} min** during LSE/NYSE hours.\n"
            f"`!alerts stop` pauses just this feature."
        )

    @alerts_start.error
    async def start_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Manage Server permission to control the scanner.")
        else:
            raise error

    @alerts_group.command(name="stop")
    @commands.has_permissions(manage_guild=True)
    async def alerts_stop(self, ctx):
        if not self.scan_loop.is_running():
            await ctx.send("Scanner isn't running.")
            return
        self.scan_loop.cancel()
        save_json(CONFIG_FILE, {"enabled": False})
        await ctx.send("\U0001F6D1 Stock alerts **stopped**. Everything else keeps running.")

    @alerts_stop.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Manage Server permission to control the scanner.")
        else:
            raise error

    @alerts_group.command(name="scan")
    @commands.has_permissions(manage_guild=True)
    async def alerts_scan(self, ctx):
        await ctx.typing()
        cfg = load_json(CONFIG_FILE, {})
        channel_id = cfg.get("channel_id", DEFAULT_CHANNEL_ID)
        alerts, summary = await asyncio.to_thread(
            run_scan, str(UNIVERSE_FILE), max_age_seconds=3600, respect_market_hours=False
        )
        self.last_summary = summary
        self.last_signal_count = len(alerts)
        posted = await self.post_alerts(channel_id, alerts)
        buys = [a for a in alerts if a.signal.name not in SELL_SIGNALS]
        sells = [a for a in alerts if a.signal.name in SELL_SIGNALS]
        top = "\n".join(
            f"\u2022 {'\U0001F53B' if a.signal.name in SELL_SIGNALS else '\U0001F7E1'} {a.signal.name} \u2014 **{a.signal.ticker}** (danger {a.risk.score}/5)"
            for a in (buys[:6] + sells[:4])
        ) or "No signals."
        await ctx.send(
            f"\U0001F50D Scan complete: {summary['scanned']} tickers \u2022 regime **{summary.get('regime', '?')}**\n"
            f"{len(buys)} buy-side / {len(sells)} sell-side signals \u2022 {posted} new posted to <#{channel_id}>.\n{top}"[:2000]
        )

    @alerts_group.command(name="status")
    async def alerts_status(self, ctx):
        running = self.scan_loop.is_running()
        cfg = load_json(CONFIG_FILE, {})
        channel_id = cfg.get("channel_id", DEFAULT_CHANNEL_ID)
        ch = self.bot.get_channel(channel_id)
        summary = self.last_summary or {}
        emb = Embed(title="\U0001F4E1 Stock Scanner Status", colour=0x3498DB)
        emb.add_field(name="State", value="\u25B6\uFE0F Running" if running else "\u23F8\uFE0F Stopped", inline=True)
        emb.add_field(name="Channel", value=ch.mention if ch else f"`{channel_id}`", inline=True)
        emb.add_field(name="Interval", value=f"{SCAN_INTERVAL} min", inline=True)
        emb.add_field(name="Markets now", value="\U0001F7E2 Open" if market_open_now() else "\U000026AB Closed", inline=True)
        emb.add_field(name="Regime", value=summary.get("regime", "?").title() if summary else "-", inline=True)
        emb.add_field(name="Universe", value=f"{summary.get('scanned', '?')}/{summary.get('universe', '?')} scanned", inline=True)
        emb.add_field(name="Signals last scan", value=str(self.last_signal_count), inline=True)
        emb.add_field(name="Alerts sent today", value=str(self.alerts_sent_today), inline=True)
        missing = summary.get("missing") or []
        errors = summary.get("errors") or []
        issues = ", ".join((missing + errors)[:6]) or "None"
        emb.add_field(name="Problem tickers", value=issues[:1000], inline=False)
        emb.set_footer(text="Confidence is backtest-calibrated, never certainty.")
        await ctx.send(embed=emb)

    @alerts_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def universe_add(self, ctx, ticker: str = None):
        if not ticker:
            await ctx.send("Usage: `!alerts add VOD.L`")
            return
        t = ticker.strip().upper()
        lines = [l.strip() for l in UNIVERSE_FILE.read_text(encoding="utf-8").splitlines()]
        if t in lines:
            await ctx.send(f"`{t}` is already in the universe ({len(lines)} entries).")
            return
        UNIVERSE_FILE.write_text("\n".join(lines + [t]) + "\n", encoding="utf-8")
        await ctx.send(f"\u2705 Added `{t}`. Universe size: **{len([l for l in lines if l and not l.startswith('#')]) + 1}**. It'll be picked up on the next scan.")

    @alerts_group.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def universe_remove(self, ctx, ticker: str = None):
        if not ticker:
            await ctx.send("Usage: `!alerts remove VOD.L`")
            return
        t = ticker.strip().upper()
        lines = [l for l in UNIVERSE_FILE.read_text(encoding="utf-8").splitlines() if l.strip() != t]
        UNIVERSE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        advisor_data.prune_cache([l for l in lines if l.strip() and not l.startswith("#")])
        await ctx.send(f"\U0001F5D1\uFE0F Removed `{t}` from the universe.")

    @alerts_group.command(name="list")
    async def universe_list(self, ctx):
        tickers = [l.strip() for l in UNIVERSE_FILE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        ldn = [t for t in tickers if t.endswith(".L")]
        us = [t for t in tickers if not t.endswith(".L")]
        await ctx.send(
            f"Universe: **{len(tickers)}** stocks \u2014 London: {len(ldn)}, US: {len(us)}.\n"
            f"Edit `universe.txt` or use `!alerts add/remove TICKER`."
        )

    @alerts_group.command(name="health")
    @commands.has_permissions(manage_guild=True)
    async def alerts_health(self, ctx):
        await ctx.typing()
        _, summary = await asyncio.to_thread(run_scan, str(UNIVERSE_FILE), max_age_seconds=0, respect_market_hours=False)
        self.last_summary = summary
        dead = summary.get("missing") or []
        errs = summary.get("errors") or []
        msg = f"Scanned **{summary['scanned']}/{summary['universe']}**.\n"
        msg += f"Dead/delisted ({len(dead)}): {', '.join(dead[:15]) or 'none'}\n" if dead or True else ""
        msg += f"Errors: {', '.join(errs[:10]) or 'none'}"
        await ctx.send(msg)

    @commands.command(name="analyze", help="Full analysis with BUY/HOLD/SELL verdict. Usage: !analyze VOD.L")
    async def analyze(self, ctx, ticker: str = None):
        if not ticker:
            await ctx.send("Give me a ticker in Yahoo format, e.g. `!analyze VOD.L` or `!analyze AAPL`.")
            return
        t = ticker.strip().upper()
        async with ctx.typing():
            try:
                raw = await asyncio.to_thread(
                    yf.download, tickers=t, period="2y", interval="1d",
                    auto_adjust=True, progress=False,
                )
                df = advisor_data.normalise_frame(raw, t)
            except Exception as exc:
                await ctx.send(f"Data fetch failed for `{t}`: {exc}")
                return
            if df.empty or len(df) < 210:
                await ctx.send(f"`{t}` has too little history. London stocks need the `.L` suffix, e.g. `VOD.L`.")
                return
            sigs, stats, ind = analyze_frame(df, t)
            rp = assess(
                stats.get("ann_vol", float("nan")),
                stats.get("max_dd_1y", float("nan")),
                stats.get("atr", float("nan")),
                stats.get("close", 1.0),
                dollar_volume=stats.get("dollar_volume", float("nan")),
                ticker=t,
            )
            regime, regime_detail = await asyncio.to_thread(get_regime)
            fund = None
            try:
                fund = await asyncio.wait_for(asyncio.to_thread(get_fundamentals, t), timeout=20)
            except Exception:
                fund = None
            try:
                _, earn_note = await asyncio.wait_for(asyncio.to_thread(earnings_risk, t), timeout=15)
            except Exception:
                earn_note = ""
            rec = build_recommendation(
                ind, t, win_rates=load_win_rates(), regime=regime,
                active_signals=sigs, fundamentals=fund,
            )
            close = stats.get("close", float("nan"))

        emb = Embed(
            title=f"{rec.action} \u2022 {t}",
            description=rec.line(),
            colour=ACTION_COLOURS[rec.action],
        )
        emb.add_field(name="Price", value=fmt_price(t, close), inline=True)
        emb.add_field(name="Danger", value=f"{rp.score}/5 {rp.label}", inline=True)
        emb.add_field(name="RSI(14)", value=f"{stats.get('rsi', float('nan')):.0f}", inline=True)
        emb.add_field(name="Ann. volatility", value=fmt_pct(rp.ann_vol), inline=True)
        emb.add_field(name="Max drawdown (1y)", value=fmt_pct(rp.max_dd_1y), inline=True)
        emb.add_field(name="Suggested max position", value=f"\u2264 {rp.max_position_pct:.0f}%", inline=True)
        emb.add_field(name="Fundamentals", value=fmt_fundamentals(t, fund), inline=False)
        if earn_note:
            emb.add_field(name="Event risk", value=earn_note, inline=False)
        drivers = "\n".join(f"\u2022 {d}" for d in rec.drivers)
        emb.add_field(name="Why", value=(drivers or "-")[:1024], inline=False)
        if sigs:
            lines = [
                f"\u2022 **{s.name}** ({s.horizon}) entry {fmt_price(t, s.entry)}, stop {fmt_price(t, s.stop)}, target {fmt_price(t, s.target)}"
                for s in sigs
            ]
            emb.add_field(name="Active signals", value="\n".join(lines)[:1024], inline=False)
        else:
            emb.add_field(name="Active signals", value="None firing right now.", inline=False)
        emb.set_footer(text=f"{regime_detail or ''} \u2022 Confidence = backtest-calibrated probability, not certainty")
        await ctx.send(embed=emb)

    @commands.group(name="portfolio", invoke_without_command=True, help="Track your holdings.")
    async def portfolio_group(self, ctx):
        await self.portfolio_show(ctx)

    @portfolio_group.command(name="add")
    async def portfolio_add(self, ctx, ticker: str = None, qty: float = None, cost: float = None):
        if not ticker or qty is None:
            await ctx.send("Usage: `!portfolio add VOD.L 100 0.72`\n(cost optional \u2013 current price used if omitted)")
            return
        t = ticker.strip().upper()
        async with ctx.typing():
            if cost is None:
                raw = await asyncio.to_thread(
                    yf.download, tickers=t, period="5d", interval="1d", auto_adjust=True, progress=False
                )
                df = advisor_data.normalise_frame(raw, t)
                if df.empty:
                    await ctx.send(f"Couldn't find `{t}`. London stocks need `.L`, e.g. `VOD.L`.")
                    return
                cost = float(df["Close"].iloc[-1])
            data = load_json(PORTFOLIO_FILE, {})
            book = data.setdefault(str(ctx.author.id), {})
            prev = book.get(t, {"qty": 0.0, "cost": 0.0})
            total_qty = prev["qty"] + qty
            avg_cost = (prev["qty"] * prev["cost"] + qty * cost) / total_qty if total_qty else 0.0
            book[t] = {"qty": round(total_qty, 6), "cost": round(avg_cost, 6)}
            data[str(ctx.author.id)] = book
            save_json(PORTFOLIO_FILE, data)
        await ctx.send(f"\u2705 Logged **{qty:g} {t}** @ {fmt_price(t, cost)}. Use `!portfolio show` anytime.")

    @portfolio_group.command(name="remove")
    async def portfolio_remove(self, ctx, ticker: str = None):
        if not ticker:
            await ctx.send("Usage: `!portfolio remove VOD.L`")
            return
        data = load_json(PORTFOLIO_FILE, {})
        book = data.get(str(ctx.author.id), {})
        t = ticker.strip().upper()
        if t in book:
            del book[t]
            save_json(PORTFOLIO_FILE, data)
            await ctx.send(f"Removed `{t}`.")
        else:
            await ctx.send(f"`{t}` isn't in your portfolio.")

    @portfolio_group.command(name="clear")
    async def portfolio_clear(self, ctx):
        data = load_json(PORTFOLIO_FILE, {})
        data.pop(str(ctx.author.id), None)
        save_json(PORTFOLIO_FILE, data)
        await ctx.send("Portfolio cleared.")

    @portfolio_group.command(name="show")
    async def portfolio_show(self, ctx):
        data = load_json(PORTFOLIO_FILE, {})
        book = data.get(str(ctx.author.id)) or {}
        if not book:
            await ctx.send("Your portfolio is empty. Add holdings with `!portfolio add VOD.L 100 0.72`.")
            return
        async with ctx.typing():
            tickers = list(book)
            frames = await asyncio.to_thread(advisor_data.fetch_batch, tickers, "2y", 900)
            regime, _ = await asyncio.to_thread(get_regime)
            win_rates = load_win_rates()
            lines = []
            for t, pos in book.items():
                df = frames.get(t)
                if df is None:
                    lines.append(f"`{t}` \u2013 no data (delisted?)")
                    continue
                price = float(df["Close"].iloc[-1])
                pl_pct = (price / pos["cost"] - 1) * 100 if pos["cost"] else 0.0
                _, _, ind = analyze_frame(df, t)
                action, conf = "\u2013", ""
                fund = None
                earn_flag, _ = False, ""
                if ind is not None:
                    try:
                        fund = await asyncio.wait_for(asyncio.to_thread(get_fundamentals, t), timeout=20)
                    except Exception:
                        fund = None
                    rec = build_recommendation(
                        ind, t, win_rates=win_rates, regime=regime, fundamentals=fund
                    )
                    action, conf = rec.action, f" ({rec.confidence:.0f}%)"
                    try:
                        earn_flag, earn_note = await asyncio.wait_for(
                            asyncio.to_thread(earnings_risk, t), timeout=15
                        )
                    except Exception:
                        earn_flag = False
                warn = " \u26A0\uFE0F below 200-day trend" if ind is not None and price < float(ind["SMA200"].iloc[-1]) else ""
                if earn_flag:
                    warn += " \U0001F4C5 earnings imminent"
                emoji = "\U0001F7E2" if action in ("STRONG BUY", "BUY") else ("\U0001F7E1" if action == "HOLD" else "\U0001F534")
                lines.append(
                    f"{emoji} **{t}** \u2013 {pos['qty']:g} @ {fmt_price(t, pos['cost'])} \u2192 {fmt_price(t, price)} "
                    f"({pl_pct:+.1f}%) \u2022 {action}{conf}{warn}"
                )
        emb = Embed(title=f"\U0001F4BC {ctx.author.display_name}'s portfolio", description="\n".join(lines)[:4000], colour=0x3498DB)
        emb.set_footer(text=f"Regime: {regime} \u2022 Not financial advice")
        await ctx.send(embed=emb)


async def setup(bot):
    await bot.add_cog(StockAlerts(bot))
