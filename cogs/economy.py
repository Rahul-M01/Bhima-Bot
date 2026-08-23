import discord
from discord.ext import commands

import economy

STARTING_BALANCE = economy.STARTING_BALANCE
DAILY_BONUS = economy.DAILY_BONUS


def fmt_amount(amount: int) -> str:
    return f"**{amount:,}** chip{'s' if amount != 1 else ''}"


class Economy(commands.Cog):
    """Persistent per-guild chip balances shared with poker and blackjack."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='balance', aliases=['chips', 'bal'],
                      help='Show your (or another member\'s) chip balance. Usage: !balance [@user]')
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        if member.bot:
            await ctx.send("Bots don't hold chips.")
            return
        amount = economy.get_balance(ctx.guild.id, member.id)
        embed = discord.Embed(
            description=f"{member.mention} holds {fmt_amount(amount)}.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.command(name='daily', help=f'Claim your daily bonus of {DAILY_BONUS} chips.')
    async def daily(self, ctx):
        claimed, retry_in = economy.claim_daily(ctx.guild.id, ctx.author.id)
        if claimed:
            balance = economy.get_balance(ctx.guild.id, ctx.author.id)
            await ctx.send(embed=discord.Embed(
                title="Daily Bonus",
                description=f"{ctx.author.mention} claimed {fmt_amount(claimed)}! "
                            f"Balance: {fmt_amount(balance)}.",
                color=discord.Color.green()
            ))
            return
        hours, minutes = retry_in // 3600, (retry_in % 3600) // 60
        await ctx.send(f"{ctx.author.mention}, you already claimed today. Come back in "
                       f"**{hours}h {minutes:02d}m**.")

    @commands.command(name='grant', help='Give (or remove with a negative amount) chips. '
                                         'Usage: !grant @user <amount>')
    @commands.has_permissions(administrator=True)
    async def grant(self, ctx, member: discord.Member, amount: int):
        if member.bot:
            await ctx.send("Bots don't hold chips.")
            return
        if amount == 0:
            await ctx.send("Amount must be non-zero.")
            return
        balance = economy.add_chips(ctx.guild.id, member.id, amount)
        verb = "granted" if amount > 0 else "removed"
        await ctx.send(embed=discord.Embed(
            title="Chips Adjusted",
            description=f"{verb.title()} {fmt_amount(abs(amount))} for {member.mention}. "
                        f"New balance: {fmt_amount(balance)}.",
            color=discord.Color.green() if amount > 0 else discord.Color.red()
        ))

    @commands.command(name='topchips', aliases=['richest'],
                      help='Show the top chip holders in this server.')
    async def topchips(self, ctx):
        holders = economy.top_holders(ctx.guild.id)
        holders = [(uid, amount) for uid, amount in holders if amount != 0]
        if not holders:
            await ctx.send("No chip balances recorded yet. Claim some with `!daily`!")
            return
        lines = []
        for i, (user_id, amount) in enumerate(holders, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"`{i}.`")
            lines.append(f"{medal} {name} — {fmt_amount(amount)}")
        embed = discord.Embed(title="🏆 Top Chip Holders", description="\n".join(lines),
                              color=discord.Color.gold())
        await ctx.send(embed=embed)

    @balance.error
    @daily.error
    @grant.error
    @topchips.error
    async def economy_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need administrator permission to do that.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument. Use `!help {ctx.command.name}` for usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument. Make sure you're mentioning a valid user and "
                           "using a whole number amount.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Economy(bot))
