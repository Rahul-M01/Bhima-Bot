import asyncio
import re
import discord
from discord.ext import commands
from discord import utils
import os
import requests
import json

class Members(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def get_quote():
        response = requests.get("https://zenquotes.io/api/random")
        json_data = json.loads(response.text)
        quote = json_data[0]["q"] + "\n~" + json_data[0]["a"]
        return quote
    
    @commands.command(name='quote')
    async def quote(self, ctx):
        quote = Members.get_quote()
        await ctx.send("```{0}```".format(quote))

    @commands.command(name='hello')
    async def hello(self, ctx):
        await ctx.send('Hello!')

    @commands.command(name='reminder')
    async def reminder(self, ctx, time: str, reminder):
        await ctx.send('Reminder set!')
        await asyncio.sleep(int(time))
        await ctx.author.send(reminder)
        
    @commands.command(name='help')
    async def help(self, ctx):
        embed=discord.Embed(title="*Server Commands*", description=f"""
        **Music Commands**
        
        - **!play [song name]**: Plays a song from youtube.
        - **!pause**: Pauses the current song.
        - **!resume**: Resumes the current song.
        - **!stop**: Stops the current song.
        - **!skip**: Skips the current song.
        - **!queue**: Shows the current queue.
        - **!clear**: Clears the current queue.
        - **!lower**: Lowers the volume.
        - **!higher**: Raises the volume.
        
        **Member Commands**
        
        - **!hello** - Says hello!
        - **!quote** - Gives a random quote!
        - **!reminder** - Sets a reminder!
        - **!help** - Shows this message!
        - **!messages <member>** - Shows the number of messages a member has sent!
        - **!all-messages** - Shows the number of messages every member has sent!

        **Admin Commands**

        - **!kick <member>** - Kicks a member!
        - **!ban <member>** - Bans a member!
        - **!unban <member>** - Unbans a member!
        - **!mute <member>** - Mutes a member!
        - **!clear <x>** - Clears x number of messages!

        """, color=0x00ff00)
        await ctx.send(embed=embed)

    

def setup(bot):
    bot.add_cog(Members(bot))