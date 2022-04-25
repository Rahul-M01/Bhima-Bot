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
    async def quote(ctx):
        quote = Members.get_quote()
        await ctx.send("```{0}```".format(quote))

    @commands.command(name='hello')
    async def hello(ctx):
        await ctx.send('Hello!')

def setup(bot):
    bot.add_cog(Members(bot))