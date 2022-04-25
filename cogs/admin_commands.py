import re
import discord
from discord.ext import commands
from discord import utils
import os

class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='reload')
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx, *, cog: str):
        if(ctx.author.id == self.bot.owner_id):
            try:
                self.bot.reload_extension(f"cogs.{cog}")
                await ctx.send(f'Reloaded {cog}')
            except Exception as error:
                await ctx.send(f'Error: {error}')
        else:
            await ctx.send("You don't have permission to use this command.")
        
    @commands.command(name='load')
    @commands.has_permissions(administrator=True)
    async def load(self, ctx, *, cog: str):
        if(ctx.author.id == self.bot.owner_id):
            try:
                self.bot.load_extension(f"cogs.{cog}")
                await ctx.send(f'Loaded {cog}')
            except Exception as error:
                await ctx.send(f'Error: {error}')
        else:
            await ctx.send("You don't have permission to use this command.")
    
    @commands.command(name='unload')
    @commands.has_permissions(administrator=True)
    async def unload(self, ctx, *, cog: str):
        if(ctx.author.id == self.bot.owner_id):
            try:
                self.bot.unload_extension(f"cogs.{cog}")
                await ctx.send(f'Unloaded {cog}')
            except Exception as error:
                await ctx.send(f'Error: {error}')
        else:
            await ctx.send("You don't have permission to do that.")

    @commands.command(name='list')
    @commands.has_permissions(administrator=True)
    async def list(self, ctx):
        if(ctx.author.id == self.bot.owner_id):
            cogs = [c.replace('.py', '') for c in os.listdir('./cogs') if c.endswith('.py')]
            await ctx.send(f'Loaded cogs: {", ".join(cogs)}')
        else:
            await ctx.send("You don't have permission to do that.")

def setup(bot):
    bot.add_cog(Maintenance(bot))
