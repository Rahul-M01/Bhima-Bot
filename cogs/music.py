import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp
from discord.ui import Button, View

class PauseButton(Button):
    def __init__(self, cog):
        super().__init__(label="▐▐", style=discord.ButtonStyle.grey)
        self.cog = cog
        self.paused = False  # Indicates the current state

    async def callback(self, interaction: discord.Interaction):
        # Toggle the state
        self.paused = not self.paused

        # Update the button label based on the state
        if self.paused:
            self.label = "▶"
            await self.cog.pause(interaction)
        else:
            self.label = "▐▐"
            await self.cog.resume(interaction)

        # Update the message with the new button label
        await interaction.message.edit(view=self.view)


class SkipButton(Button):
    def __init__(self, cog, label="▶▶▶"):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.skip(interaction)

class StopButton(Button):
    def __init__(self, cog, label="◼"):
        super().__init__(label=label, style=discord.ButtonStyle.red)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.stop(interaction)

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
    async def pause(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Paused the music.", ephemeral=True)
        else:
            await interaction.response.send_message("No music is currently playing.")

    @commands.command()
    async def resume(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Resumed the music.", ephemeral=True)
        else:
            await interaction.response.send_message("Music is not paused.")


    @commands.command()
    async def skip(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()  # This should stop the current song
            # play_next will be called automatically after the song stops
            await interaction.response.send_message("Skipping to the next song.")
        else:
            await interaction.response.send_message("No music is playing to skip.")

    @commands.command()
    async def stop(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            self.current_song = None
            self.song_queue.clear()
            await interaction.response.send_message("Stopped the music and cleared the queue.", ephemeral=True)




    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

    @commands.command()
    async def queue(self, ctx):
        if len(self.song_queue) == 0:
            return await ctx.send("The queue is empty.")

        queue_info = "\n".join([f"{idx + 1}: {song['title']}" for idx, song in enumerate(self.song_queue)])
        view = View()
        view.add_item(PauseButton(self))
        view.add_item(SkipButton(self))
        view.add_item(StopButton(self))
        await ctx.send(f"Current Queue:\n{queue_info}", view=view)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
