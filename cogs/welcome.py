#==================================
#          Doesnt Work
#==================================

import discord
from discord.ext import commands

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = discord.utils.get(member.guild.channels, name='general')  # Replace 'general' with your channel
        if channel:
            await channel.send(f"Welcome to the server, {member.mention}! We're glad to have you here!")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
