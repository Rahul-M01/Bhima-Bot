import asyncio
import re
import discord
from discord.ext import commands
from discord import utils
import os
import requests
import json
import requests
from decouple import config

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

class Leveling(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 961966319752851497:
            return

        if message.content.startswith('!'):
            return

        with open('leveling.json', 'r') as f:
            users = json.load(f)

        await self.update_data(users, message.author)
        await self.add_experience(users, message.author, 5)
        if(await self.level_up(users, message.author) == 1):
            await message.channel.send(f"{message.author.mention} has leveled up to level {users[str(message.author.id)]['level']}")
        with open('leveling.json', 'w') as f:
            json.dump(users, f)
    
    async def level_up(self, users, message):
    
        experience = users[str(message.id)]['experience']
        lvl_end = int(experience % 1000)

        if lvl_end == 0:
            users[str(message.id)]['level'] += 1
            self.add_experience(users, message.id, 5)
            return 1

    async def add_experience(self, users, message, exp):
        users[str(message.id)]['experience'] += exp

    async def update_data(self, users, message):
        if not str(message.id) in users:
            users[str(message.id)] = {}
            users[str(message.id)]['experience'] = 0
            users[str(message.id)]['level'] = 1

    @commands.command(name='level')
    async def level(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author
        with open('leveling.json', 'r') as f:
            users = json.load(f)
        level = users[str(member.id)]['level']
        experience = users[str(member.id)]['experience']
        progress = int((experience / 100) % 10)
        bar = await self.progress_bar(progress)
        embed = discord.Embed(title=f"{member.name}'s level", description=f"{bar} {progress}/10", color=0xd89522)
        embed.add_field(name="Level", value=level)
        embed.add_field(name="Experience", value=experience)
        await ctx.send(embed=embed)


    async def progress_bar(self, progress):
        bar = ""
        for i in range(0, progress):
            bar += "▓"
        for i in range(progress, 10):
            bar += "░"
        return bar


    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        with open('leveling.json', 'r') as f:
            users = json.load(f)
        leader_board = {}
        for user in users:
            name = int(user)
            level = users[user]['level']
            experience = users[user]['experience']
            leader_board[name] = [level, experience]
        leader_board = sorted(leader_board.items(), key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="Leaderboard", description="The top 10 levels in the server", color=0x00ff00)
        index = 1
        for x in leader_board:
            if index > 10:
                break
            else:
                username = ctx.guild.get_member(int(x[0]))
                embed.add_field(name=f"{index}. {username}", value=f"Level: {x[1][0]}\nExperience: {x[1][1]}", inline=False)
                index += 1
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Leveling(bot))