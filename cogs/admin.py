import re
import discord
from discord.ext import commands
from discord import utils
import os

class ServerAdmin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='clear')
    @commands.has_permissions(administrator=True)
    async def clear(self, ctx, amount: int):
        if ctx.author.guild_permissions.administrator:
            await ctx.channel.purge(limit=amount)
            await ctx.send(f'Cleared {amount} messages.')
        else:
            await ctx.send("You don't have permission to do that.")

    @commands.command(name='kick')
    @commands.has_permissions(administrator=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.guild_permissions.administrator:
            await member.kick(reason=reason)
            await ctx.send(f'Kicked {member.mention}')
        else:
            await ctx.send("You don't have permission to do that.")
    
    @commands.command(name='ban')
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.guild_permissions.administrator:
            await member.ban(reason=reason)
            await ctx.send(f'Banned {member.mention}')
        else:
            await ctx.send("You don't have permission to do that.")
    
    @commands.command(name='unban')
    @commands.has_permissions(administrator=True)
    async def unban(self, ctx, *, member):
        if ctx.author.guild_permissions.administrator:
            banned_users = await ctx.guild.bans()
            member_name, member_discriminator = member.split('#')

            for ban_entry in banned_users:
                user = ban_entry.user

                if (user.name, user.discriminator) == (member_name, member_discriminator):
                    await ctx.guild.unban(user)
                    await ctx.send(f'Unbanned {user.mention}')
                    return

        await ctx.send("That user is not banned.")
    
    @commands.command(name='mute')
    @commands.has_permissions(administrator=True)
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.guild_permissions.administrator:
            role = discord.utils.get(ctx.guild.roles, name='Muted')
            await member.add_roles(role, reason=reason)
            await ctx.send(f'Muted {member.mention}')
        else:
            await ctx.send("You don't have permission to do that.")
    
    @commands.command(name='unmute')
    @commands.has_permissions(administrator=True)
    async def unmute(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.guild_permissions.administrator:
            role = discord.utils.get(ctx.guild.roles, name='Muted')
            await member.remove_roles(role, reason=reason)
            await ctx.send(f'Unmuted {member.mention}')
        else:
            await ctx.send("You don't have permission to do that.")
    
def setup(bot):
    bot.add_cog(ServerAdmin(bot))
