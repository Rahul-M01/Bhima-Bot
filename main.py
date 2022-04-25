import os
import discord
from discord.ext import commands
import json
# from perspective import PerspectiveAPI
from googleapiclient import discovery
from discord.ext.commands import has_permissions, MissingPermissions
from decouple import config

API_key = API_USERNAME = config('API_key')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
owner_id = config('OWNER_ID')


@bot.event
async def on_ready():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            bot.load_extension(f"cogs.{file[:-3]}")
    print('Logged in succesfully.')
  



# @client.event
# async def on_message(message):
#     await client.process_commands(message)
#     p = PerspectiveAPI(API_key)
#     result = p.score(message.content)
#     if isclose(result["TOXICITY"], 0.93, abs_tol=10**-1) or isclose(
#             result["TOXICITY"], 0.99, abs_tol=10**-1) or isclose(
#                 result["TOXICITY"], 0.75, abs_tol=10**-1) or isclose(
#                     result["TOXICITY"], 1.0, abs_tol=10**-1):
#         await message.channel.send("Seek help. Find god.")


key = config('TOKEN')
bot.run(key)
