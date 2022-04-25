import re
from discord import Embed
import discord
import lavalink
from discord.ext import commands
from discord import utils

url_rx = re.compile(r'https?://(?:www\.)?.+')

class songs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.music = lavalink.Client(self.bot.user.id)
        self.bot.music.add_node('localhost', 2333, 'youshallnotpass', 'na', 'music-node')
        self.bot.add_listener(self.bot.music.voice_update_handler, 'on_socket_response')
        self.bot.music.add_event_hook(self.track_hook)
    
    @commands.command(name='join')
    async def join(self, ctx):
        member = utils.find(lambda m: m.id == ctx.author.id, ctx.guild.members)
        if member is not None and member.voice is not None:
            vc = member.voice.channel
            player = self.bot.music.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
            if not player.is_connected:
                player.store('channel', ctx.channel.id)
                await self.connect_to(ctx.guild.id, str(vc.id))

    @commands.command(name='play')
    async def play(self, ctx, *, query):
        try:
            player = self.bot.music.player_manager.get(ctx.guild.id)
            query = f'ytsearch:{query}'
            results = await player.node.get_tracks(query)
            tracks = results['tracks'][:10]
            counter = 0
            query_result = ''
            for track in tracks:
                counter += 1
                query_result += f'{counter}. {track["info"]["title"]} by {track["info"]["uri"]} \n'
            embed = Embed()
            embed.description = query_result

            await ctx.channel.send(embed=embed)

            def check(m):
                return m.author.id == ctx.author.id
            
            response = await self.bot.wait_for('message', check=check)
            track = tracks[int(response.content) - 1]
            player.add(requester=ctx.author.id, track=track)
            await ctx.send(f'Added {track["info"]["title"]} to the queue.')
            if not player.is_playing:
                await player.play()
        except Exception as error:
            await ctx.channel.send("Error: {}".format(error))

    @commands.command(name='pause')
    async def pause(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        if player.is_playing:
            await player.set_pause(True)
            await ctx.send('Music paused.')
        else:
            await ctx.send('Music is not playing.')
    
    @commands.command(name='resume')
    async def resume(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        await player.set_pause(False)
        await ctx.send('Music resumed.')
    
    @commands.command(name='stop')
    async def stop(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        await player.queue.clear()
        await player.stop()
        await ctx.send('Music stopped.')
    
    @commands.command(name='skip')
    async def skip(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        if player.is_playing:
            await player.skip()
            await ctx.send('Music skipped.')
        else:
            await ctx.send('Music is not playing.')
    
    @commands.command(name='queue')
    async def queue(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        try:
            queue_list = ''
            for track in player.queue:
                queue_list += f'{track["title"]} by {track["uri"]} \n'
            embed = Embed()
            embed.description = queue_list
            await ctx.send(embed=embed)
        except Exception as error:
            await ctx.send("Error: {}".format(error))

    @commands.command(name='lower')
    async def lower(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        if player.is_playing:
            await player.set_volume(player.volume - 50)
            await ctx.send('Volume lowered.')
        else:
            await ctx.send('Music is not playing.')
    
    @commands.command(name='higher')
    async def higher(self, ctx):
        player = self.bot.music.player_manager.get(ctx.guild.id)
        if player.is_playing:
            await player.set_volume(player.volume + 50)
            await ctx.send('Volume higher.')
        else:
            await ctx.send('Music is not playing.')
    
    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            guild_id = int(event.player.guild_id)
            await self.connect_to(guild_id, None)
    
    async def connect_to(self, guild_id: int, channel_id: str):
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)
    

    


def setup(bot):
    bot.add_cog(songs(bot))

