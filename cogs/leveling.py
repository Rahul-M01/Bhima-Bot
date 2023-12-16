import discord
from discord.ext import commands

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_messages = {}  # Store message count
        self.user_levels = {}    # Store user levels

    def calculate_level(self, message_count):
        # Implementing a simple incremental leveling formula
        level = 0
        messages_needed = 10
        while message_count >= messages_needed:
            level += 1
            message_count -= messages_needed
            messages_needed += 5  # Increase messages needed for next level
        return level

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.author.bot:
            return

        user_id = message.author.id
        self.user_messages[user_id] = self.user_messages.get(user_id, 0) + 1

        current_level = self.user_levels.get(user_id, 0)
        new_level = self.calculate_level(self.user_messages[user_id])

        if new_level > current_level:
            await message.channel.send(f"Congratulations {message.author.mention}, you've reached level {new_level}!")
            self.user_levels[user_id] = new_level
    
    #==================================
    #          Shows Level
    #==================================
    @commands.command()
    async def level(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        level = self.user_levels.get(user.id, 0)
        await ctx.send(f"{user.mention} is level {level}.")

async def setup(bot):
    await bot.add_cog(Leveling(bot))
