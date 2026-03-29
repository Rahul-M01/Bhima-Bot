import discord
from discord.ext import commands

import os
from dotenv import load_dotenv

import tracemalloc
tracemalloc.start()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

load_dotenv()
TOKEN = os.getenv("TOKEN")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                print(f'Loaded cog: {cog_name}')
            except Exception as e:
                print(f'Failed to load cog {cog_name}: {e}')
    print(f'Logged in as {bot.user}')

bot.run(TOKEN)
