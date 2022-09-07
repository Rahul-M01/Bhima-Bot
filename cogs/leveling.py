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

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        if message.content.startswith('!'):
            return

        with open('leveling.json', 'r') as f:
            users = json.load(f)

        await update_data(users, message.author)
        await add_experience(users, message.author, 5)
        await level_up(users, message.author, message)

        with open('leveling.json', 'w') as f:
            json.dump(users, f)
    
    async def update_data(users, user):
        if not user.id in users:
            users[user.id] = {}
            users[user.id]['experience'] = 0
            users[user.id]['level'] = 1
    
    async def add_experience(users, user, exp):
        users[user.id]['experience'] += exp
    
    async def level_up(users, user, message):
        experience = users[user.id]['experience']
        lvl_start = users[user.id]['level']
        lvl_end = int(experience ** (1/4))

        if lvl_start < lvl_end:
            await message.channel.send(f'{user.mention} has leveled up to level {lvl_end}')
            users[user.id]['level'] = lvl_end
    
    @commands.command(name='level')
    async def level(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author
        with open('leveling.json', 'r') as f:
            users = json.load(f)
            if(str(member.id) in users):
                embed=discord.Embed(title="*Level*", description=f"""
                {member.mention} is level {users[str(member.id)]['level']}
                """, color=0xd89522)
                await ctx.send(embed=embed)

    
    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        with open('leveling.json', 'r') as f:
            users = json.load(f)
        leader_board = {}
        for user in users:
            name = int(user)
            level = users[user]['level']
            leader_board[name] = level
        leader_board = sorted(leader_board.items(), key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="Leaderboard", description="The top 10 levels in the server", color=0x00ff00)
        index = 1
        for x in leader_board:
            if index > 10:
                break
            else:
                user_id = f"<@{int(x[0])}>"
                embed.add_field(name=f"{index}. {user_id}", value=f"Level: {x[1]}", inline=False)
                index += 1
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Leveling(bot))