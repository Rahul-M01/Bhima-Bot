import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import Embed
import asyncio
import yt_dlp

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


class Track:
    def __init__(self, data, requester):
        self.url = data['url']
        self.title = data.get('title', 'Unknown')
        self.webpage = data.get('webpage_url', '')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail', '')
        self.requester = requester

    @classmethod
    async def from_query(cls, query, requester):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if 'entries' in data:
            data = data['entries'][0]
        return cls(data, requester)

    def fmt_duration(self):
        if not self.duration:
            return '?:??'
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f'{h}:{m:02}:{s:02}' if h else f'{m}:{s:02}'

    def make_source(self):
        return discord.FFmpegPCMAudio(self.url, **FFMPEG_OPTS)


class GuildPlayer:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop_track = False
        self.loop_queue = False
        self.volume = 0.5

    def pop_next(self):
        if self.loop_track and self.current:
            return self.current
        if self.loop_queue and self.current:
            self.queue.append(self.current)
        return self.queue.pop(0) if self.queue else None


class PlayerView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.grey, custom_id="music_pause")
    async def pause_resume(self, interaction, button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("Not in a voice channel.", ephemeral=True)
        if vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
        elif vc.is_paused():
            vc.resume()
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple, custom_id="music_skip")
    async def skip(self, interaction, button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.red, custom_id="music_stop")
    async def stop(self, interaction, button):
        vc = interaction.guild.voice_client
        if vc:
            player = self.cog.get_player(interaction.guild.id)
            player.queue.clear()
            player.loop_track = False
            player.loop_queue = False
            vc.stop()
            await vc.disconnect()
            self.cog.cleanup(interaction.guild.id)
            await interaction.response.send_message("Stopped.", ephemeral=True)
        else:
            await interaction.response.send_message("Not connected.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer()
        return self.players[guild_id]

    def cleanup(self, guild_id):
        self.players.pop(guild_id, None)

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel first.")
            return None
        vc = ctx.voice_client
        if vc and vc.channel == ctx.author.voice.channel:
            return vc
        if vc:
            await vc.move_to(ctx.author.voice.channel)
            return vc
        return await ctx.author.voice.channel.connect()

    def np_embed(self, track):
        embed = Embed(
            title="Now Playing",
            description=f"[{track.title}]({track.webpage})",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Duration",     value=track.fmt_duration(),         inline=True)
        embed.add_field(name="Requested by", value=track.requester.display_name, inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        return embed

    def play_next(self, ctx):
        player = self.get_player(ctx.guild.id)
        track = player.pop_next()

        if track is None:
            player.current = None
            asyncio.run_coroutine_threadsafe(ctx.send("Queue finished."), self.bot.loop)
            asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), self.bot.loop)
            self.cleanup(ctx.guild.id)
            return

        player.current = track
        source = discord.PCMVolumeTransformer(track.make_source(), volume=player.volume)
        ctx.voice_client.play(source, after=lambda e: self.play_next(ctx))
        asyncio.run_coroutine_threadsafe(
            ctx.send(embed=self.np_embed(track), view=PlayerView(self)),
            self.bot.loop
        )

    @commands.command(name='play', aliases=['p'], help='Play a song. Usage: !play <url or search terms>')
    async def play(self, ctx, *, query: str):
        vc = await self.ensure_voice(ctx)
        if not vc:
            return

        async with ctx.typing():
            try:
                track = await Track.from_query(query, ctx.author)
            except Exception as e:
                await ctx.send(f"Couldn't load that track: {e}")
                return

        player = self.get_player(ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            player.queue.append(track)
            embed = Embed(title="Added to Queue", description=f"[{track.title}]({track.webpage})", color=discord.Color.green())
            embed.add_field(name="Position", value=str(len(player.queue)), inline=True)
            embed.add_field(name="Duration", value=track.fmt_duration(),   inline=True)
            await ctx.send(embed=embed)
        else:
            player.current = track
            source = discord.PCMVolumeTransformer(track.make_source(), volume=player.volume)
            vc.play(source, after=lambda e: self.play_next(ctx))
            await ctx.send(embed=self.np_embed(track), view=PlayerView(self))

    @commands.command(name='pause', help='Pause playback.')
    async def pause(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("Paused.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name='resume', help='Resume playback.')
    async def resume(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("Resumed.")
        else:
            await ctx.send("Not paused.")

    @commands.command(name='skip', aliases=['s'], help='Skip the current track.')
    async def skip(self, ctx):
        vc = ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.send("Skipped.")
        else:
            await ctx.send("Nothing to skip.")

    @commands.command(name='stop', help='Stop playback and disconnect.')
    async def stop(self, ctx):
        vc = ctx.voice_client
        if vc:
            player = self.get_player(ctx.guild.id)
            player.queue.clear()
            player.loop_track = False
            player.loop_queue = False
            vc.stop()
            await vc.disconnect()
            self.cleanup(ctx.guild.id)
            await ctx.send("Stopped.")
        else:
            await ctx.send("Not connected.")

    @commands.command(name='queue', aliases=['q'], help='Show the queue.')
    async def queue(self, ctx):
        player = self.get_player(ctx.guild.id)
        vc = ctx.voice_client

        if not (vc and (vc.is_playing() or vc.is_paused())) and not player.current:
            await ctx.send("Nothing is playing.")
            return

        embed = Embed(title="Queue", color=discord.Color.blurple())
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"[{player.current.title}]({player.current.webpage}) `{player.current.fmt_duration()}`",
                inline=False
            )

        if player.queue:
            lines = [
                f"`{i+1}.` [{t.title}]({t.webpage}) `{t.fmt_duration()}` — {t.requester.display_name}"
                for i, t in enumerate(player.queue[:10])
            ]
            if len(player.queue) > 10:
                lines.append(f"*...and {len(player.queue) - 10} more*")
            embed.add_field(name="Up Next", value='\n'.join(lines), inline=False)
        else:
            embed.add_field(name="Up Next", value="Queue is empty.", inline=False)

        flags = []
        if player.loop_track: flags.append("🔂 Track loop")
        if player.loop_queue: flags.append("🔁 Queue loop")
        if flags:
            embed.set_footer(text=' | '.join(flags))

        await ctx.send(embed=embed)

    @commands.command(name='nowplaying', aliases=['np'], help='Show the current track.')
    async def nowplaying(self, ctx):
        player = self.get_player(ctx.guild.id)
        if player.current:
            await ctx.send(embed=self.np_embed(player.current))
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name='volume', aliases=['vol'], help='Set volume 0-100. Usage: !volume 75')
    async def volume(self, ctx, vol: int):
        if not 0 <= vol <= 100:
            await ctx.send("Volume must be between 0 and 100.")
            return
        player = self.get_player(ctx.guild.id)
        player.volume = vol / 100
        vc = ctx.voice_client
        if vc and vc.source:
            vc.source.volume = player.volume
        await ctx.send(f"Volume set to **{vol}%**.")

    @commands.command(name='loop', help='Toggle loop. Usage: !loop track | !loop queue | !loop off')
    async def loop(self, ctx, mode: str = 'track'):
        player = self.get_player(ctx.guild.id)
        mode = mode.lower()
        if mode == 'track':
            player.loop_track = not player.loop_track
            player.loop_queue = False
            await ctx.send(f"🔂 Track loop **{'on' if player.loop_track else 'off'}**.")
        elif mode in ('queue', 'q'):
            player.loop_queue = not player.loop_queue
            player.loop_track = False
            await ctx.send(f"🔁 Queue loop **{'on' if player.loop_queue else 'off'}**.")
        elif mode == 'off':
            player.loop_track = False
            player.loop_queue = False
            await ctx.send("Loop disabled.")
        else:
            await ctx.send("Usage: `!loop track` | `!loop queue` | `!loop off`")

    @commands.command(name='remove', help='Remove a track by position. Usage: !remove 2')
    async def remove(self, ctx, pos: int):
        player = self.get_player(ctx.guild.id)
        if not player.queue:
            await ctx.send("The queue is empty.")
            return
        if not 1 <= pos <= len(player.queue):
            await ctx.send(f"Position must be between 1 and {len(player.queue)}.")
            return
        removed = player.queue.pop(pos - 1)
        await ctx.send(f"Removed **{removed.title}**.")

    @commands.command(name='clearqueue', help='Clear the queue without stopping the current track.')
    async def clearqueue(self, ctx):
        self.get_player(ctx.guild.id).queue.clear()
        await ctx.send("Queue cleared.")

    @commands.command(name='join', help='Join your voice channel.')
    async def join(self, ctx):
        vc = await self.ensure_voice(ctx)
        if vc:
            await ctx.send(f"Joined **{vc.channel.name}**.")

    @commands.command(name='leave', help='Leave the voice channel.')
    async def leave(self, ctx):
        vc = ctx.voice_client
        if vc:
            await vc.disconnect()
            self.cleanup(ctx.guild.id)
            await ctx.send("Disconnected.")
        else:
            await ctx.send("Not in a voice channel.")

    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!play <url or search terms>`")
        else:
            raise error

    @volume.error
    async def volume_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Please provide a number between 0 and 100.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Music(bot))
