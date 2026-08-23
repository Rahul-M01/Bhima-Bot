import discord
from discord.ext import commands
import asyncio
import json
import urllib.parse
import urllib.request

IS_GD_ENDPOINT = 'https://is.gd/create.php'
REQUEST_TIMEOUT = 10


def shorten_url(url):
    """Call the is.gd API and return the short URL. Raises ValueError on API errors."""
    query = urllib.parse.urlencode({'format': 'json', 'url': url})
    request = urllib.request.Request(f"{IS_GD_ENDPOINT}?{query}", headers={
        'User-Agent': 'Mozilla/5.0 (compatible; BhimaBot/1.0)',
    })
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read().decode('utf-8'))
    if payload.get('shorturl'):
        return payload['shorturl']
    message = payload.get('errormessage') or 'unknown error'
    raise ValueError(message)


class Shortener(commands.Cog):
    @commands.command(name='shorten', help='Shorten a URL with is.gd. Usage: !shorten <url>')
    async def shorten(self, ctx, url: str):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            await ctx.send("That doesn't look like a valid URL. Include the `https://` part.")
            return

        async with ctx.typing():
            try:
                short = await asyncio.to_thread(shorten_url, url)
            except ValueError as e:
                await ctx.send(f"is.gd rejected that URL: `{e}`")
                return
            except Exception:
                await ctx.send("Couldn't reach is.gd right now. Please try again in a moment.")
                return
        await ctx.send(f"🔗 {short}")

    @shorten.error
    async def shorten_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!shorten <url>`")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Shortener(bot))
