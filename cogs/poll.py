import discord
from discord.ext import commands
import asyncio

class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="poll", help="Creates a poll with the specified question and options,\
                    example: !poll \"What is your favorite color?\" \"Red\" \"Blue\" \"Yellow\",\
                    the poll lasts for 60 seconds")
    async def create_poll(self, ctx, question, *options: str):
        if len(options) > 10:
            await ctx.send("You can provide a maximum of 10 options.")
            return

        if len(options) < 2:
            await ctx.send("Please provide at least 2 options.")
            return

        embed = discord.Embed(title=question, description="\n".join([f"{i+1}. {option}" for i, option in enumerate(options)]), color=discord.Color.blue())
        poll_message = await ctx.send(embed=embed)

        reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        for i in range(len(options)):
            await poll_message.add_reaction(reactions[i])

        # Wait for reactions
        await asyncio.sleep(60)  # Poll duration in seconds

        poll_message = await ctx.channel.fetch_message(poll_message.id)
        results = []
        for reaction in poll_message.reactions:
            results.append((reaction.emoji, reaction.count - 1))  # Subtract 1 to exclude the bot's own reaction

        results_str = "\n".join([f"{emoji}: {count} vote(s)" for emoji, count in results])
        await ctx.send(f"Poll results for '{question}':\n{results_str}")

async def setup(bot):
    await bot.add_cog(Poll(bot))
