import discord
from discord.ext import commands
from googletrans import Translator, LANGUAGES

class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(name="translate", help="Translates text to English. Usage: !translate [text]")
    async def translate(self, ctx, *, text: str):
        try:
            translated = self.translator.translate(text, dest='en')
            embed = discord.Embed(
                title="Translation",
                description=f"Original: {text}\nTranslated: {translated.text}",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(Translation(bot))
