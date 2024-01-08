import discord
from discord.ext import commands
import pyshorteners  # Install using pip install pyshorteners
import validators

class URLShortener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shortener = pyshorteners.Shortener()

    @commands.command(name='short', help='Shortens a given URL. Usage: !short [url]')
    async def shorten_url(self, ctx, url):
        # Check if the provided text is a valid URL
        if not validators.url(url):
            await ctx.send("Please provide a valid URL.")
            return

        try:
            # Shorten the URL
            shortened_url = self.shortener.tinyurl.short(url)

            # Include the user's name or mention in the response
            response_message = f"{ctx.author.mention}, your shortened URL: {shortened_url}"
            await ctx.send(response_message)

            # Attempt to delete the user's original message
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                await ctx.send("I don't have permission to delete messages.")
            except discord.HTTPException:
                await ctx.send("Failed to delete the message.")

        except Exception as e:
            await ctx.send("An error occurred while shortening the URL.")



async def setup(bot):
    await bot.add_cog(URLShortener(bot))
