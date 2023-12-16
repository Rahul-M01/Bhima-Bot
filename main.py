import discord
from discord.ext import commands
import config
import os

import tracemalloc
tracemalloc.start()

intents = discord.Intents.default()
intents.messages = True  # Enable the message content intent
intents.guilds = True
intents.members = True
intents.message_content = True  # Add this line

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'cogs.{cog_name}')  # Use await here
                print(f'Loaded cog: {cog_name}')
            except Exception as e:
                print(f'Failed to load cog {cog_name}: {e}')
    print(f'Logged in as {bot.user}')

bot.run(config.TOKEN)
