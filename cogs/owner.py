# reload_cog.py
from discord.ext import commands
import discord
import asyncio
import json

class ReloadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #==================================
    #          Reloads Cogs
    #==================================
    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_cogs(self, ctx):
        for extension in list(self.bot.extensions):
            await self.bot.reload_extension(extension)
        await ctx.send('All cogs have been reloaded.')

    #==================================
    #          Mutes Members
    #==================================
    @commands.command(name='mute')
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        
        if not mute_role:
            try:
                mute_role = await ctx.guild.create_role(name="Muted")
                for channel in ctx.guild.channels:
                    # Make sure to deny the 'send_messages' permission for each channel
                    await channel.set_permissions(mute_role, send_messages=False)
            except discord.Forbidden:
                await ctx.send("I don't have permission to create a new role.")
                return
            except discord.HTTPException:
                await ctx.send("Failed to create a mute role.")
                return

        try:
            await member.add_roles(mute_role, reason=reason)
            await ctx.send(f'Muted {member.display_name} for reason: {reason}')
        except discord.Forbidden:
            await ctx.send("I don't have permission to add roles.")
        except discord.HTTPException:
            await ctx.send("Failed to add the mute role.")

    @mute.error
    async def mute_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        else:
            # Handle other types of errors if necessary
            pass

    
    #==================================
    #          Unmutes Members
    #==================================
    @commands.command(name='unmute')
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member):
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            await ctx.send("There is no mute role to remove.")
            return

        try:
            await member.remove_roles(mute_role)
            await ctx.send(f'Unmuted {member.display_name}.')
        except discord.Forbidden:
            await ctx.send("I don't have permission to add roles.")
        except discord.HTTPException:
            await ctx.send("Failed to remove the mute role.")
    
    #==================================
    #          Purges Messages
    #==================================
    @commands.command(name='purge')
    @commands.has_permissions(manage_roles=True)
    async def purge(self, ctx, amount: int):
        if amount < 1:
            await ctx.send("Please specify a number greater than 0.")
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f'Deleted {len(deleted)} message(s)', delete_after=5)

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        else:
            # Handle other types of errors if necessary
            pass

async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
