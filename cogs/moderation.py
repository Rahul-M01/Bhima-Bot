import discord
from discord.ext import commands
from datetime import timedelta
import json
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[1] / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

WARNINGS_FILE = LOGS_DIR / 'warnings.json'

def load_warnings():
    if not WARNINGS_FILE.exists():
        return {}
    with open(WARNINGS_FILE, 'r') as f:
        return json.load(f)

def save_warnings(data):
    with open(WARNINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='kick', help='Kick a member. Usage: !kick @user [reason]')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = 'No reason provided'):
        if member == ctx.author:
            await ctx.send("You can't kick yourself.")
            return
        if member.top_role >= ctx.author.top_role:
            await ctx.send("You can't kick someone with an equal or higher role.")
            return

        try:
            await member.send(f"You were kicked from **{ctx.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass

        await member.kick(reason=reason)
        embed = discord.Embed(
            title="Member Kicked",
            description=f"{member.mention} has been kicked.\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='ban', help='Ban a member. Usage: !ban @user [reason]')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = 'No reason provided'):
        if member == ctx.author:
            await ctx.send("You can't ban yourself.")
            return
        if member.top_role >= ctx.author.top_role:
            await ctx.send("You can't ban someone with an equal or higher role.")
            return

        try:
            await member.send(f"You were banned from **{ctx.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            pass

        await member.ban(reason=reason)
        embed = discord.Embed(
            title="Member Banned",
            description=f"{member.mention} has been banned.\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='unban', help='Unban a user. Usage: !unban username#0000')
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, username: str):
        banned = [entry async for entry in ctx.guild.bans()]
        for entry in banned:
            if str(entry.user) == username:
                await ctx.guild.unban(entry.user)
                embed = discord.Embed(
                    title="Member Unbanned",
                    description=f"**{entry.user}** has been unbanned.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
                return

        await ctx.send(f"No banned user found matching `{username}`.")

    @commands.command(name='mute', help='Timeout a member. Usage: !mute @user <minutes> [reason]')
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, minutes: int, *, reason: str = 'No reason provided'):
        if member == ctx.author:
            await ctx.send("You can't mute yourself.")
            return
        if member.top_role > ctx.author.top_role:
            await ctx.send("You can't mute someone with an equal or higher role.")
            return
        if minutes <= 0 or minutes > 40320:  # Discord max timeout is 28 days
            await ctx.send("Duration must be between 1 and 40320 minutes (28 days).")
            return

        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)

        embed = discord.Embed(
            title="Member Muted",
            description=f"{member.mention} has been timed out for **{minutes} minute(s)**.\n**Reason:** {reason}",
            color=discord.Color.dark_orange()
        )
        embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='unmute', help='Remove a timeout from a member. Usage: !unmute @user')
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        if not member.is_timed_out():
            await ctx.send(f"{member.mention} is not currently muted.")
            return

        await member.timeout(None)
        embed = discord.Embed(
            title="Member Unmuted",
            description=f"{member.mention}'s timeout has been removed.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='warn', help='Warn a member. Usage: !warn @user <reason>')
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if member.bot:
            await ctx.send("You can't warn a bot.")
            return

        data = load_warnings()
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in data:
            data[guild_id] = {}
        if user_id not in data[guild_id]:
            data[guild_id][user_id] = []

        data[guild_id][user_id].append({
            'reason': reason,
            'by': str(ctx.author),
            'by_id': ctx.author.id
        })
        save_warnings(data)

        count = len(data[guild_id][user_id])

        try:
            await member.send(f"You received a warning in **{ctx.guild.name}**.\n**Reason:** {reason}\nYou now have **{count}** warning(s).")
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="Member Warned",
            description=f"{member.mention} has been warned.\n**Reason:** {reason}\n**Total warnings:** {count}",
            color=discord.Color.yellow()
        )
        embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='warnings', help='View warnings for a member. Usage: !warnings @user')
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        data = load_warnings()
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        warns = data.get(guild_id, {}).get(user_id, [])
        if not warns:
            await ctx.send(f"{member.mention} has no warnings.")
            return

        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            color=discord.Color.yellow()
        )
        for i, w in enumerate(warns, 1):
            embed.add_field(name=f"Warning {i}", value=f"**Reason:** {w['reason']}\n**By:** {w['by']}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='clearwarnings', help='Clear all warnings for a member. Usage: !clearwarnings @user')
    @commands.has_permissions(administrator=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        data = load_warnings()
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if data.get(guild_id, {}).get(user_id):
            data[guild_id][user_id] = []
            save_warnings(data)
            await ctx.send(f"Cleared all warnings for {member.mention}.")
        else:
            await ctx.send(f"{member.mention} has no warnings to clear.")

    @commands.command(name='purge', help='Delete messages in bulk. Usage: !purge <amount> [@user]')
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        if amount <= 0 or amount > 100:
            await ctx.send("Please provide an amount between 1 and 100.")
            return

        await ctx.message.delete()

        if member:
            def check(m):
                return m.author == member
            deleted = await ctx.channel.purge(limit=amount * 5, check=check, bulk=True)
            deleted = deleted[:amount]
        else:
            deleted = await ctx.channel.purge(limit=amount, bulk=True)

        embed = discord.Embed(
            description=f"Deleted **{len(deleted)}** message(s){f' from {member.mention}' if member else ''}.",
            color=discord.Color.blurple()
        )
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=5)

    @commands.command(name='slowmode', help='Set channel slowmode. Usage: !slowmode <seconds> (0 to disable)')
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        if seconds < 0 or seconds > 21600:
            await ctx.send("Slowmode must be between 0 and 21600 seconds (6 hours).")
            return

        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("Slowmode disabled.")
        else:
            await ctx.send(f"Slowmode set to **{seconds}** second(s).")

    @kick.error
    @ban.error
    @mute.error
    @unmute.error
    @warn.error
    @warnings.error
    @clearwarnings.error
    @purge.error
    @slowmode.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument. Use `!help {ctx.command.name}` for usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument. Make sure you're mentioning a valid user.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have permission to do that.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Moderation(bot))
