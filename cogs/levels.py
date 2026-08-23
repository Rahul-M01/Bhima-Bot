import discord
from discord.ext import commands, tasks
import json
import math
import random
import time
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[1] / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LEVELS_FILE = LOGS_DIR / 'levels.json'

XP_MIN, XP_MAX = 15, 25     # xp awarded per eligible message
XP_COOLDOWN = 60            # seconds between awards per user
CONGRATS_COOLDOWN = 30      # min seconds between level-up messages per channel
FLUSH_INTERVAL = 5          # minutes between disk writes


def level_for_xp(xp):
    """Level curve: reaching level L costs L^2 * 100 xp."""
    return int(math.sqrt(max(0, xp) // 100))


def load_levels():
    if not LEVELS_FILE.exists():
        return {}
    try:
        with open(LEVELS_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_levels()
        self.cooldowns = {}          # (guild_id, user_id) -> last award time
        self.last_congrats = {}      # channel_id -> last congrats time
        self._dirty = False
        self.flush_loop.start()

    def cog_unload(self):
        self.flush_loop.cancel()
        self._flush_now()

    def _flush_now(self):
        try:
            with open(LEVELS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            self._dirty = False
        except OSError:
            pass

    @tasks.loop(minutes=FLUSH_INTERVAL)
    async def flush_loop(self):
        if self._dirty:
            self._flush_now()

    @flush_loop.before_loop
    async def before_flush(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return

        key = (message.guild.id, message.author.id)
        now = time.time()
        last = self.cooldowns.get(key, 0)
        if now - last < XP_COOLDOWN:
            return
        self.cooldowns[key] = now

        guild = self.data.setdefault(str(message.guild.id), {})
        record = guild.setdefault(str(message.author.id), {'xp': 0})
        old_level = level_for_xp(record['xp'])
        record['xp'] += random.randint(XP_MIN, XP_MAX)
        new_level = level_for_xp(record['xp'])
        self._dirty = True

        if new_level > old_level:
            await self.congratulate(message.channel, message.author, new_level)

    async def congratulate(self, channel, member, level):
        now = time.time()
        if now - self.last_congrats.get(channel.id, 0) < CONGRATS_COOLDOWN:
            return
        self.last_congrats[channel.id] = now
        await channel.send(f"🎉 {member.mention} just reached level **{level}**!")

    @commands.command(name='rank', help='Show your (or another member\'s) chat level. '
                                        'Usage: !rank [@user]')
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        record = self.data.get(str(ctx.guild.id), {}).get(str(member.id), {})
        xp = record.get('xp', 0)
        embed = discord.Embed(
            title=f"Chat Level — {member.display_name}",
            description=(
                f"**Level:** {level_for_xp(xp)}\n"
                f"**Total XP:** {xp:,}\n"
                f"Next level at **{(level_for_xp(xp) + 1) ** 2 * 100:,}** xp."
            ),
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @commands.group(name='leaderboard', invoke_without_command=True,
                    help='Server leaderboards. Usage: !leaderboard levels')
    async def leaderboard_group(self, ctx):
        await ctx.send('Usage: `!leaderboard levels`.')

    @leaderboard_group.command(name='levels', help='Top members by chat level.')
    async def leaderboard_levels(self, ctx):
        guild = self.data.get(str(ctx.guild.id), {})
        if not guild:
            await ctx.send('No levels recorded yet — start chatting!')
            return
        ranked = sorted(guild.items(), key=lambda kv: kv[1].get('xp', 0), reverse=True)[:10]
        lines = []
        for i, (user_id, record) in enumerate(ranked, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f'User {user_id}'
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"`{i}.`")
            lines.append(
                f"{medal} **{name}** — level {level_for_xp(record.get('xp', 0))} "
                f"({record.get('xp', 0):,} xp)"
            )
        embed = discord.Embed(title="🏅 Level Leaderboard", description='\n'.join(lines),
                              color=discord.Color.purple())
        await ctx.send(embed=embed)

    @rank.error
    @leaderboard_group.error
    @leaderboard_levels.error
    async def levels_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument. Make sure you're mentioning a valid user.")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send('Something went wrong with the leveling system. Please try again.')
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Levels(bot))
