import discord
from discord.ext import commands
from discord.ui import View
from discord import Embed
import asyncio
import logging
import yt_dlp

log = logging.getLogger(__name__)

YTDL_BASE = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL({**YTDL_BASE, 'noplaylist': True})
ytdl_search = yt_dlp.YoutubeDL({**YTDL_BASE, 'noplaylist': True})
ytdl_playlist = yt_dlp.YoutubeDL({**YTDL_BASE, 'extract_flat': 'in_playlist'})


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

    @classmethod
    async def from_url(cls, url, requester):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
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


class SearchSelect(discord.ui.Select):
    def __init__(self, results, cog, requester):
        self.results = results
        self.cog = cog
        self.requester = requester
        options = []
        for i, r in enumerate(results):
            dur = r.get('duration')
            if dur:
                m, s = divmod(int(dur), 60)
                desc = f"{m}:{s:02}"
            else:
                desc = "Unknown length"
            label = (r.get('title') or 'Unknown')[:100]
            options.append(discord.SelectOption(label=label, value=str(i), description=desc))
        super().__init__(placeholder="Pick a track...", options=options)

    async def callback(self, interaction):
        idx = int(self.values[0])
        picked = self.results[idx]
        ctx = self.cog._search_contexts.pop(interaction.message.id, None)
        if not ctx:
            return await interaction.response.send_message("This search expired.", ephemeral=True)

        await interaction.response.defer()
        await interaction.message.delete()

        try:
            track = await Track.from_url(picked['url'], self.requester)
        except Exception:
            log.exception("Couldn't load selected search track %s", picked.get('webpage_url', ''))
            await ctx.send("Couldn't load that track. Please try another one.")
            return

        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            vc = await self.cog.ensure_voice(ctx)
            if not vc:
                return

        player = self.cog.get_player(ctx.guild.id)
        if vc.is_playing() or vc.is_paused():
            player.queue.append(track)
            embed = Embed(title="Added to Queue", description=f"[{track.title}]({track.webpage})", color=discord.Color.green())
            embed.add_field(name="Position", value=str(len(player.queue)), inline=True)
            embed.add_field(name="Duration", value=track.fmt_duration(), inline=True)
            await ctx.send(embed=embed)
        else:
            player.current = track
            source = discord.PCMVolumeTransformer(track.make_source(), volume=player.volume)
            vc.play(source, after=lambda e: self.cog.play_next(ctx))
            await ctx.send(embed=self.cog.np_embed(track), view=PlayerView(self.cog))


class SearchView(View):
    def __init__(self, results, cog, requester):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(results, cog, requester))
        self.message = None

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="Search timed out.", view=None, embed=None)
            except Exception:
                pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._search_contexts = {}
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
        channel = ctx.author.voice.channel
        vc = ctx.voice_client
        if vc and vc.is_connected() and vc.channel == channel:
            return vc
        if vc:
            await vc.disconnect(force=True)
        return await channel.connect(self_deaf=True)

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

        if getattr(track, '_needs_resolve', False):
            asyncio.run_coroutine_threadsafe(self._play_resolved(ctx, track), self.bot.loop)
        else:
            player.current = track
            source = discord.PCMVolumeTransformer(track.make_source(), volume=player.volume)
            ctx.voice_client.play(source, after=lambda e: self.play_next(ctx))
            asyncio.run_coroutine_threadsafe(
                ctx.send(embed=self.np_embed(track), view=PlayerView(self)),
                self.bot.loop
            )

    async def _play_resolved(self, ctx, track):
        try:
            resolved = await Track.from_url(track.url, track.requester)
        except Exception:
            # skip tracks that fail to resolve
            self.play_next(ctx)
            return

        player = self.get_player(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return

        player.current = resolved
        source = discord.PCMVolumeTransformer(resolved.make_source(), volume=player.volume)
        vc.play(source, after=lambda e: self.play_next(ctx))
        await ctx.send(embed=self.np_embed(resolved), view=PlayerView(self))

    def _is_playlist_url(self, query):
        return 'list=' in query and ('youtube.com' in query or 'youtu.be' in query)

    @commands.command(name='play', aliases=['p'], help='Play a song or playlist. Usage: !play <url or search terms>')
    async def play(self, ctx, *, query: str):
        vc = await self.ensure_voice(ctx)
        if not vc:
            return

        if self._is_playlist_url(query):
            await self._play_playlist(ctx, query)
            return

        async with ctx.typing():
            try:
                track = await Track.from_query(query, ctx.author)
            except Exception:
                log.exception("Couldn't load track for query")
                await ctx.send("Couldn't load that track. Please try another one.")
                return

        player = self.get_player(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            await ctx.send("Voice connection dropped, try again.")
            return

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

    async def _play_playlist(self, ctx, url):
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, lambda: ytdl_playlist.extract_info(url, download=False))
            except Exception:
                log.exception("Couldn't load playlist")
                await ctx.send("Couldn't load that playlist. Please check the link and try again.")
                return

        entries = data.get('entries') or []
        if not entries:
            await ctx.send("That playlist is empty or couldn't be loaded.")
            return

        playlist_title = data.get('title', 'Unknown playlist')
        player = self.get_player(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            await ctx.send("Voice connection dropped, try again.")
            return

        # load the first track fully so we can play it right away
        first_entry = entries[0]
        try:
            first_track = await Track.from_url(first_entry['url'], ctx.author)
        except Exception:
            await ctx.send("Couldn't load the first track from that playlist.")
            return

        if not vc.is_playing() and not vc.is_paused():
            player.current = first_track
            source = discord.PCMVolumeTransformer(first_track.make_source(), volume=player.volume)
            vc.play(source, after=lambda e: self.play_next(ctx))
            await ctx.send(embed=self.np_embed(first_track), view=PlayerView(self))
            remaining = entries[1:]
        else:
            player.queue.append(first_track)
            remaining = entries[1:]

        # queue the rest as stubs, they get resolved when play_next picks them up
        for entry in remaining:
            stub = Track({
                'url': entry['url'],
                'title': entry.get('title', 'Unknown'),
                'webpage_url': entry.get('url', ''),
                'duration': entry.get('duration', 0),
                'thumbnail': entry.get('thumbnails', [{}])[0].get('url', '') if entry.get('thumbnails') else '',
            }, ctx.author)
            stub._needs_resolve = True
            player.queue.append(stub)

        await ctx.send(f"Queued **{len(remaining)}** tracks from **{playlist_title}**.")

    @commands.command(name='search', help='Search YouTube and pick a track. Usage: !search <query>')
    async def search(self, ctx, *, query: str):
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, lambda: ytdl_search.extract_info(f"ytsearch5:{query}", download=False))
            except Exception:
                log.exception("YouTube search failed")
                await ctx.send("Search failed. Please try again in a moment.")
                return

        results = [e for e in (data.get('entries') or []) if e]
        if not results:
            await ctx.send(f"No results for **{query}**.")
            return

        lines = []
        for i, r in enumerate(results, 1):
            dur = r.get('duration')
            if dur:
                m, s = divmod(int(dur), 60)
                ts = f"`{m}:{s:02}`"
            else:
                ts = "`?:??`"
            lines.append(f"`{i}.` **{r.get('title', 'Unknown')}** — {ts}")

        embed = Embed(title=f"Results for \"{query}\"", description="\n".join(lines), color=discord.Color.blurple())
        view = SearchView(results, self, ctx.author)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        self._search_contexts[msg.id] = ctx

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
