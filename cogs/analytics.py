import discord
from discord.ext import commands, tasks
import json
import re
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[1] / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ANALYTICS_FILE = LOGS_DIR / 'analytics.json'

FLUSH_INTERVAL = 5      # minutes between disk writes
MAX_WORDS = 500         # distinct words kept per channel (bounded file growth)
WORD_PATTERN = re.compile(r"[a-z0-9']{3,}")


def extract_words(text):
    return WORD_PATTERN.findall(text.lower())


class Analytics(commands.Cog):
    """Incrementally caches message stats and answers !analytics queries."""

    def __init__(self, bot):
        self.bot = bot
        self.data = self._load()
        self._dirty = False
        self.flush_loop.start()

    def cog_unload(self):
        self.flush_loop.cancel()
        self._flush_now()

    def _load(self):
        if not ANALYTICS_FILE.exists():
            return {}
        try:
            with open(ANALYTICS_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _guild_data(self, guild_id):
        entry = self.data.setdefault(str(guild_id), {'channels': {}, 'users': {}, 'total': 0})
        entry.setdefault('channels', {})
        entry.setdefault('users', {})
        entry.setdefault('total', 0)
        return entry

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or not message.content:
            return
        guild = self._guild_data(message.guild.id)

        channel = guild['channels'].setdefault(str(message.channel.id), {
            'name': message.channel.name, 'messages': 0, 'words': {},
        })
        channel['messages'] += 1
        for word in extract_words(message.content):
            channel['words'][word] = channel['words'].get(word, 0) + 1

        guild['users'][str(message.author.id)] = guild['users'].get(str(message.author.id), 0) + 1
        guild['total'] += 1
        self._dirty = True

    @tasks.loop(minutes=FLUSH_INTERVAL)
    async def flush_loop(self):
        if self._dirty:
            self._flush_now()

    @flush_loop.before_loop
    async def before_flush(self):
        await self.bot.wait_until_ready()

    def _flush_now(self):
        try:
            with open(ANALYTICS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            self._dirty = False
        except OSError:
            pass

    @commands.group(name='analytics', invoke_without_command=True,
                    help='Server message analytics. Subcommands: words, talkers, channels.')
    @commands.has_permissions(administrator=True)
    async def analytics_group(self, ctx):
        await ctx.send("Usage: `!analytics words [#channel]`, `!analytics talkers`, "
                       "`!analytics channels`.")

    @analytics_group.command(name='words',
                             help='Most-used words in a channel (defaults to this one). '
                                  'Usage: !analytics words [#channel]')
    async def words(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        info = self._guild_data(ctx.guild.id)['channels'].get(str(channel.id))
        if not info or not info.get('words'):
            await ctx.send(f"No word data cached for {channel.mention} yet — it builds "
                           f"incrementally as people chat.")
            return
        top = sorted(info['words'].items(), key=lambda kv: kv[1], reverse=True)[:10]
        lines = [f"`{i}.` **{word}** — {count:,}" for i, (word, count) in enumerate(top, 1)]
        embed = discord.Embed(
            title=f"Most-Used Words in #{channel.name}",
            description='\n'.join(lines),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"{info['messages']:,} messages tracked since last reset")
        await ctx.send(embed=embed)

    @analytics_group.command(name='talkers', help='Members with the most tracked messages.')
    async def talkers(self, ctx):
        guild = self._guild_data(ctx.guild.id)
        if not guild['users']:
            await ctx.send('No message data cached yet.')
            return
        ranked = sorted(guild['users'].items(), key=lambda kv: kv[1], reverse=True)[:10]
        lines = []
        for i, (user_id, count) in enumerate(ranked, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f'User {user_id}'
            lines.append(f"`{i}.` **{name}** — {count:,} messages")
        embed = discord.Embed(title="🗣️ Top Talkers", description='\n'.join(lines),
                              color=discord.Color.green())
        embed.set_footer(text=f"{guild['total']:,} messages tracked server-wide")
        await ctx.send(embed=embed)

    @analytics_group.command(name='channels', help='Total tracked messages per channel.')
    async def channels(self, ctx):
        channels = self._guild_data(ctx.guild.id)['channels']
        if not channels:
            await ctx.send('No message data cached yet.')
            return
        ranked = sorted(channels.items(), key=lambda kv: kv[1].get('messages', 0), reverse=True)[:15]
        lines = []
        for i, (_, info) in enumerate(ranked, 1):
            name = info.get('name', 'unknown')
            lines.append(f"`{i}.` **#{name}** — {info.get('messages', 0):,} messages")
        embed = discord.Embed(title="📊 Messages per Channel", description='\n'.join(lines),
                              color=discord.Color.orange())
        await ctx.send(embed=embed)

    @commands.command(name='resetanalytics', hidden=True,
                      help='Clear cached analytics for this server (admin).')
    @commands.has_permissions(administrator=True)
    async def reset_analytics(self, ctx):
        self.data.pop(str(ctx.guild.id), None)
        self._flush_now()
        await ctx.send('Analytics cache cleared for this server.')

    @analytics_group.error
    @words.error
    @talkers.error
    @channels.error
    @reset_analytics.error
    async def analytics_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('You need administrator permission to use analytics commands.')
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Couldn't find that channel. Try mentioning it: `!analytics words #general`")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send('Something went wrong collecting analytics. Please try again.')
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Analytics(bot))
