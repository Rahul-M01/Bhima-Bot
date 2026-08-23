import discord
from discord.ext import commands, tasks
from discord import Embed
import yfinance as yf
from datetime import datetime, timezone, time
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

CHANNEL_FILE = Path(__file__).resolve().parents[1] / 'logs' / 'metals_config.json'
SURGE_THRESHOLD = 1.5   # % change within one check interval to trigger alert
CHECK_INTERVAL  = 15    # minutes between surge checks

METALS = {
    'Gold':   ('GC=F', '🟡', 'oz'),
    'Silver': ('SI=F', '⚪', 'oz'),
}

MORNING = time(9,  0, tzinfo=timezone.utc)
EVENING = time(17, 0, tzinfo=timezone.utc)


def load_config():
    if not CHANNEL_FILE.exists():
        return {}
    with open(CHANNEL_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CHANNEL_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def fetch_prices():
    """Returns {name: {price, prev_close, change, pct}} or raises."""
    results = {}
    for name, (sym, emoji, unit) in METALS.items():
        t    = yf.Ticker(sym)
        info = t.fast_info
        price = round(info.last_price, 2)
        prev  = round(info.previous_close, 2)
        change = round(price - prev, 2)
        pct    = round((change / prev) * 100, 2) if prev else 0.0
        results[name] = {
            'price':  price,
            'prev':   prev,
            'change': change,
            'pct':    pct,
            'emoji':  emoji,
            'unit':   unit,
        }
    return results


def build_embed(prices, title):
    embed = Embed(title=title, color=0xf0c040, timestamp=datetime.now(timezone.utc))
    for name, d in prices.items():
        arrow = '🔺' if d['change'] >= 0 else '🔻'
        embed.add_field(
            name=f"{d['emoji']} {name}",
            value=f"**${d['price']:,.2f}** / {d['unit']}\n{arrow} ${d['change']:+,.2f} ({d['pct']:+.2f}%)",
            inline=True
        )
    embed.set_footer(text="Prices via Yahoo Finance (futures)")
    return embed


class Metals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_prices = {}   # {name: price} for surge detection
        self.daily_report.start()
        self.surge_check.start()

    def cog_unload(self):
        self.daily_report.cancel()
        self.surge_check.cancel()

    async def get_channels(self):
        cfg = load_config()
        channels = []
        for guild_id, channel_id in cfg.items():
            ch = self.bot.get_channel(int(channel_id))
            if ch:
                channels.append(ch)
        return channels

    @tasks.loop(time=[MORNING, EVENING])
    async def daily_report(self):
        channels = await self.get_channels()
        if not channels:
            return
        try:
            prices = fetch_prices()
        except Exception as e:
            print(f"[metals] failed to fetch prices: {e}")
            return

        hour = datetime.now(timezone.utc).hour
        title = "Good morning — Metals Report ☀️" if hour < 13 else "Evening Metals Report 🌙"
        embed = build_embed(prices, title)

        for ch in channels:
            await ch.send(embed=embed)

    @daily_report.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=CHECK_INTERVAL)
    async def surge_check(self):
        channels = await self.get_channels()
        if not channels:
            return
        try:
            prices = fetch_prices()
        except Exception:
            return

        alerts = []
        for name, d in prices.items():
            last = self.last_prices.get(name)
            if last is None:
                self.last_prices[name] = d['price']
                continue
            move = ((d['price'] - last) / last) * 100
            if abs(move) >= SURGE_THRESHOLD:
                direction = "surged 🔺" if move > 0 else "crashed 🔻"
                alerts.append((name, d, move, direction))
            self.last_prices[name] = d['price']

        if not alerts:
            return

        embed = Embed(
            title="⚠️ Metals Alert",
            color=discord.Color.red() if any(m < 0 for _, _, m, _ in alerts) else discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        for name, d, move, direction in alerts:
            embed.add_field(
                name=f"{d['emoji']} {name} {direction}",
                value=f"Now **${d['price']:,.2f}** ({move:+.2f}% in the last {CHECK_INTERVAL} min)",
                inline=False
            )
        for ch in channels:
            await ch.send(embed=embed)

    @surge_check.before_loop
    async def before_surge(self):
        await self.bot.wait_until_ready()

    @commands.command(name='metals', help='Show current gold and silver prices.')
    async def metals(self, ctx):
        async with ctx.typing():
            try:
                prices = fetch_prices()
            except Exception:
                log.exception("Couldn't fetch metal prices")
                await ctx.send("Couldn't fetch prices right now. Please try again in a moment.")
                return
        await ctx.send(embed=build_embed(prices, "Gold & Silver"))

    @commands.command(name='setmetals', help='Set the channel for metals reports. Usage: !setmetals #channel')
    @commands.has_permissions(manage_guild=True)
    async def set_metals(self, ctx, channel: discord.TextChannel):
        cfg = load_config()
        cfg[str(ctx.guild.id)] = channel.id
        save_config(cfg)
        await ctx.send(
            f"Metals reports will be sent to {channel.mention}.\n"
            f"Daily at **09:00 UTC** (morning) and **17:00 UTC** (evening).\n"
            f"Surge alerts fire when price moves ≥ **{SURGE_THRESHOLD}%** within {CHECK_INTERVAL} minutes."
        )

    @commands.command(name='unsetmetals', help='Stop metals reports in this server.')
    @commands.has_permissions(manage_guild=True)
    async def unset_metals(self, ctx):
        cfg = load_config()
        if str(ctx.guild.id) in cfg:
            del cfg[str(ctx.guild.id)]
            save_config(cfg)
            await ctx.send("Metals reports disabled.")
        else:
            await ctx.send("No metals channel was set.")

    @set_metals.error
    async def set_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Couldn't find that channel. Try mentioning it: `!setmetals #channel`")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Manage Server permission to do that.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Metals(bot))
