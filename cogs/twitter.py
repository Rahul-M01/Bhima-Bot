import discord
from discord.ext import commands
import re

class TweetEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='embed')
    async def embed_tweet(self, ctx, *, message: str):
        # Regular expression to match and replace the Twitter URL
        if(re.search(r'twitter\.com', message) is None and re.search(r'x\.com', message) is None):
            await ctx.send("This is not a tweet!")
            return
        else:
            if(re.search(r'twitter\.com', message)):
                modified_message = re.sub(r'twitter\.com', 'vxtwitter.com', message)
            elif(re.search(r'x\.com', message)):
                modified_message = re.sub(r'x\.com', 'vxtwitter.com', message)
            await ctx.message.delete()
            # Send the modified message
            await ctx.send(modified_message)

async def setup(bot):
    await bot.add_cog(TweetEmbed(bot))
