import discord
from discord.ext import commands
import asyncio
import re
import time

EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
DEFAULT_DURATION = 60
MIN_DURATION = 10
MAX_DURATION = 3600
EDIT_MIN_INTERVAL = 5   # min seconds between in-place embed updates

DURATION_PATTERN = re.compile(r'^(\d+)([smh]?)$')


def parse_duration(token):
    """Parse a trailing duration like 45, 30s, 5m or 1h into seconds."""
    match = DURATION_PATTERN.match(token)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multiplier = {'': 1, 's': 1, 'm': 60, 'h': 3600}[unit]
    return value * multiplier


def build_tallies(options, votes):
    counts = [0] * len(options)
    for index in votes.values():
        if 0 <= index < len(options):
            counts[index] += 1
    return counts


class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}   # message_id -> poll state dict

    def build_embed(self, poll):
        counts = build_tallies(poll['options'], poll['votes'])
        lines = []
        for i, option in enumerate(poll['options']):
            bar = '█' * min(counts[i], 12)
            lines.append(f"{EMOJIS[i]} **{option}** — {counts[i]} vote(s) {bar}")
        remaining = max(0, int(poll['ends_at'] - time.time()))
        embed = discord.Embed(title=f"📊 {poll['question']}", description='\n'.join(lines),
                              color=discord.Color.blue())
        embed.set_footer(text=f"Click a number to vote • closes in {remaining}s")
        return embed

    async def refresh_embed(self, poll, force=False):
        """Update the poll embed in place, throttled to one edit every few seconds."""
        if poll.get('closed'):
            return
        now = time.time()
        elapsed = now - poll['last_edit']
        if force or elapsed >= EDIT_MIN_INTERVAL:
            poll['last_edit'] = now
            try:
                await poll['message'].edit(embed=self.build_embed(poll))
            except discord.HTTPException:
                pass
            return
        if poll.get('edit_task') and not poll['edit_task'].done():
            return
        poll['edit_task'] = asyncio.create_task(
            self._delayed_refresh(poll, EDIT_MIN_INTERVAL - elapsed)
        )

    async def _delayed_refresh(self, poll, delay):
        await asyncio.sleep(delay)
        await self.refresh_embed(poll, force=True)

    async def auto_close(self, poll):
        await asyncio.sleep(poll['duration'])
        await self.close_poll(poll)

    async def close_poll(self, poll):
        if poll.get('closed'):
            return
        poll['closed'] = True
        if poll.get('edit_task'):
            poll['edit_task'].cancel()

        self.polls.pop(poll['message'].id, None)
        counts = build_tallies(poll['options'], poll['votes'])
        total = sum(counts)
        if total == 0:
            description = "Nobody voted. 🍃"
        else:
            top = max(counts)
            winners = [EMOJIS[i] + ' **' + poll['options'][i] + '**'
                       for i, c in enumerate(counts) if c == top]
            description = ', '.join(winners) + f" with **{top}** vote(s) ({total} cast)."
        embed = discord.Embed(title=f"📊 Poll Closed: {poll['question']}",
                              description=description, color=discord.Color.gold())
        try:
            await poll['channel'].send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.command(name="poll", help='Create a live-tally poll. Usage: !poll "Question" '
                                        '"Option 1" "Option 2" [duration e.g. 60s or 5m]')
    async def create_poll(self, ctx, question: str, *options: str):
        duration = DEFAULT_DURATION
        options = list(options)
        if options:
            parsed = parse_duration(options[-1])
            if parsed is not None:
                duration = parsed
                options.pop()

        if len(options) > 10:
            await ctx.send("You can provide a maximum of 10 options.")
            return
        if len(options) < 2:
            await ctx.send("Please provide at least 2 options.")
            return
        if duration < MIN_DURATION:
            duration = MIN_DURATION
        elif duration > MAX_DURATION:
            duration = MAX_DURATION

        poll = {
            'question': question,
            'options': options,
            'votes': {},
            'channel': ctx.channel,
            'duration': duration,
            'ends_at': time.time() + duration,
            'last_edit': 0,
            'closed': False,
            'edit_task': None,
        }

        embed = self.build_embed(poll)
        embed.set_footer(text=f"Click a number to vote • closes in {duration}s")
        poll_message = await ctx.send(embed=embed)
        poll['message'] = poll_message
        self.polls[poll_message.id] = poll

        for i in range(len(options)):
            try:
                await poll_message.add_reaction(EMOJIS[i])
            except discord.HTTPException:
                break

        asyncio.create_task(self.auto_close(poll))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self._handle_reaction(payload, adding=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self._handle_reaction(payload, adding=False)

    async def _handle_reaction(self, payload, adding):
        poll = self.polls.get(payload.message_id)
        if not poll or payload.user_id == self.bot.user.id:
            return
        if payload.emoji.name not in EMOJIS[:len(poll['options'])]:
            return
        index = EMOJIS.index(payload.emoji.name)
        if adding:
            poll['votes'][str(payload.user_id)] = index
        else:
            current = poll['votes'].get(str(payload.user_id))
            if current == index:
                del poll['votes'][str(payload.user_id)]
        await self.refresh_embed(poll)

    @create_poll.error
    async def poll_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Usage: `!poll "Question" "Option 1" "Option 2" [duration]`')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('Wrap the question and each option in quotes.')
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Poll(bot))
