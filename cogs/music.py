import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = []
        self.current_song = None

    async def play_next(self, ctx):
        if len(self.song_queue) > 0:
            self.current_song = self.song_queue.pop(0)
            await self.play_song(ctx, self.current_song)
        else:
            self.current_song = None

    async def play_song(self, ctx, song):
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['url']))
        ctx.voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))

    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("You are not connected to a voice channel.")
        channel = ctx.author.voice.channel
        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, url: str):
        if not ctx.voice_client:
            await ctx.invoke(self.join)

        ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            song = {'url': info['url'], 'title': info['title']}

        if ctx.voice_client.is_playing() or self.current_song is not None:
            self.song_queue.append(song)
            return await ctx.send(f"Added to queue: {song['title']}")

        self.current_song = song
        await self.play_song(ctx, song)

    #=======================================
    #                Pauses               #
    #=======================================
    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()

    #=======================================
    #                Resumes               #
    #=======================================
    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()

    #=======================================
    #              Adjusts Volume          #
    #=======================================
    @commands.command()
    async def volume(self, ctx, *, volume: int):
        if ctx.voice_client and ctx.voice_client.source:
            # Ensure volume is between 1 and 100
            volume = max(0, min(volume, 100))
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"Volume set to {volume}%")
        else:
            await ctx.send("Not connected to a voice channel.")
    
    @commands.command()
    async def skip(self, ctx):
        """Skips the current song and plays the next one in the queue."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await self.play_next(ctx)
        else:
            await ctx.send("No song is currently playing.")

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            self.current_song = None
            self.song_queue.clear()

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

    @commands.command()
    async def queue(self, ctx):
        if len(self.song_queue) == 0:
            return await ctx.send("The queue is empty.")
        queue_info = "\n".join([f"{idx + 1}: {song['title']}" for idx, song in enumerate(self.song_queue)])
        await ctx.send(f"Current Queue:\n{queue_info}")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
