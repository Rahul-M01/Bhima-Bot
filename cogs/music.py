import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp
from discord.ui import Button, View
import asyncio

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

        embed = discord.Embed(title="🎶 Now playing:", description=song['title'], color=discord.Color.green())
        await ctx.send(embed=embed)

    
    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("You are not connected to a voice channel.")
        channel = ctx.author.voice.channel
        await channel.connect()

    #=======================================
    #              Plays Music             #
    #=======================================
    # Helper function to handle search and selection
    async def search_and_select(self, ctx, query):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch5'  # Search for top 5 results
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = info['entries']

        if not results:
            await ctx.send("No results found.")
            return None

        embed = discord.Embed(title="Search Results", description="", color=discord.Color.blue())
        for i, track in enumerate(results, start=1):
            embed.add_field(name=f"{i}. {track['title']}", value=track['webpage_url'], inline=False)
        
        message = await ctx.send(embed=embed)

        # Check for user response
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            response = await self.bot.wait_for('message', check=check, timeout=30.0)  # 30 seconds timeout
            content = int(response.content)
            if 1 <= content <= len(results):
                return results[content - 1]
            else:
                await ctx.send("Invalid choice.")
                return None
        except asyncio.TimeoutError:
            await message.delete()
            await ctx.send("Response timed out. Please try again.")
            return None

    # Play command adjusted for URL or query
    @commands.command()
    async def play(self, ctx, *, input: str):
        # Join the voice channel if not already connected
        if not ctx.voice_client:
            await ctx.invoke(self.join)

        # Check if input is a direct link or a query
        song = None
        if input.startswith(("http://", "https://")):
            ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(input, download=False)
                song = {'url': info['url'], 'title': info['title'], 'artist': info.get('uploader', 'Unknown artist')}        
        else:
            song = await self.search_and_select(ctx, input)
            if song:
                song = {'url': song['url'], 'title': song['title'], 'artist': song.get('uploader', 'Unknown artist')}
            if not song:
                return  # Exit if no song was selected

        # Now play or add the song to the queue
        if ctx.voice_client.is_playing() or self.current_song is not None:
            self.song_queue.append(song)
            await ctx.send(f"Added to queue: {song['title']}")
        else:
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
    
    #=======================================
    #              Pauses Music            #
    #=======================================
    @commands.command()
    async def pause(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Paused the music.", ephemeral=True)
        else:
            await interaction.response.send_message("No music is currently playing.")

    #=======================================
    #              Resumes Music           #
    #=======================================
    @commands.command()
    async def resume(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Resumed the music.", ephemeral=True)
        else:
            await interaction.response.send_message("Music is not paused.")


    #=======================================
    #              Skips Song              #
    #=======================================
    @commands.command()
    async def skip(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()  # This should stop the current song
            # play_next will be called automatically after the song stops
            await interaction.response.send_message("Skipping to the next song.")
        else:
            await interaction.response.send_message("No music is playing to skip.")

    #=======================================
    #              Stops Music             #
    #=======================================
    @commands.command()
    async def stop(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            self.current_song = None
            self.song_queue.clear()
            await interaction.response.send_message("Stopped the music and cleared the queue.", ephemeral=True)

    #=======================================
    #              Leaves Voice            #
    #=======================================
    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

    #=======================================
    #              Shows the Queue         #
    #=======================================
    @commands.command()
    async def queue(self, ctx):
        if len(self.song_queue) == 0:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.blue()))

        embed = discord.Embed(title="Music Queue", description="", color=discord.Color.blue())
        for idx, song in enumerate(self.song_queue):
            embed.add_field(name=f"{idx + 1}. {song['title']} by {song['artist']}", value="\u200b", inline=False)

        view = View()
        view.add_item(PauseButton(self))
        view.add_item(SkipButton(self))
        view.add_item(StopButton(self))
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
