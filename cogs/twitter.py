import discord
from discord.ext import commands
import re

class TweetEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='embed')
    async def embed_tweet(self, ctx, *, message: str):
        if 'twitter.com' or 'x.com' in message and 'status' in message:
            url = re.search("(?P<url>https?://[^\s]+)", message).group("url")

            embed = discord.Embed()
            embed.add_field(name="Tweet Link", value=url, inline=False)

            await ctx.send(embed=embed)

            await ctx.message.delete()
        else:
            await ctx.send("Please provide a valid Twitter link.")

def setup(bot):
    bot.add_cog(TweetEmbed(bot))
