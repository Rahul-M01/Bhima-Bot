import asyncio
import logging
import sys
import types

# googletrans depends on httpx, which still imports the stdlib "cgi" module
# that was removed in Python 3.13. Provide a minimal parse_header shim.
try:
    import cgi  # noqa: F401
except ModuleNotFoundError:
    def _parse_header(line):
        parts = [p.strip() for p in line.split(';') if p.strip()]
        if not parts:
            return '', {}
        key = parts[0].lower()
        params = {}
        for part in parts[1:]:
            name, sep, value = part.partition('=')
            params[name.strip().lower()] = value.strip().strip('"') if sep else ''
        return key, params

    _cgi = types.ModuleType('cgi')
    _cgi.parse_header = _parse_header
    sys.modules['cgi'] = _cgi

import discord
from discord.ext import commands
from googletrans import Translator, LANGUAGES

log = logging.getLogger(__name__)

class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(name="translate", help="Translates text to English. Usage: !translate [text]")
    async def translate(self, ctx, *, text: str):
        try:
            translated = await asyncio.to_thread(self.translator.translate, text, dest='en')
            embed = discord.Embed(
                title="Translation",
                description=f"Original: {text}\nTranslated: {translated.text}",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        except Exception:
            log.exception("Translation failed")
            await ctx.send("Sorry, translation failed right now. Please try again later.")

async def setup(bot):
    await bot.add_cog(Translation(bot))
