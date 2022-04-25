from calendar import c
import re
import discord
from discord.ext import commands
from discord import utils
import os
from discord import Embed

class Stats(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='messages')
    async def message_stats(self, ctx, member: discord.Member = None):
        messages = 0
        async with ctx.typing():
            async for message in ctx.channel.history(limit=None):
                if message.author == member or member is None:
                    messages += 1
        embed = Embed(title="Message Stats", description=f"{member.mention} has sent {messages} messages in this channel.", color=0x00ff00)
        await ctx.send(embed=embed)

    @commands.command(name='all-messages')
    async def all_message_stats(self, ctx):
        #Create embed of message count by every member in the server
        embed = Embed(title="Message Stats", description="Messages sent by every member in the server.", color=0x00ff00)
        for member in ctx.guild.members:
            messages = 0
            async with ctx.typing():
                async for message in ctx.channel.history(limit=None):
                    if message.author == member:
                        messages += 1
            embed.add_field(name=member.name, value=messages, inline=False)
        await ctx.send(embed=embed)
    

def setup(bot):
    bot.add_cog(Stats(bot))
