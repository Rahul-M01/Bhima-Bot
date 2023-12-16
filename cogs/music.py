import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx):
        """Joins the author's voice channel."""
        if ctx.author.voice is None:
            return await ctx.send("You are not connected to a voice channel.")
        channel = ctx.author.voice.channel
        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, url: str):
        """Plays a song from a given YouTube URL."""
        if not ctx.voice_client:
            await ctx.invoke(self.join)

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            URL = info['url']
            source = FFmpegPCMAudio(URL, **{'options': '-vn'})
            ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)

    @commands.command()
    async def stop(self, ctx):
        """Stops playing the song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    @commands.command()
    async def leave(self, ctx):
        """Leaves the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
