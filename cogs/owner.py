# reload_cog.py
from discord.ext import commands
import discord
import asyncio

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
    #          Shows Stats
    #==================================
    @commands.command(name='userstats')
    @commands.is_owner()
    async def user_stats(self, ctx, member: discord.Member):
        message_cog = self.bot.get_cog("MessageStats")
        if not message_cog:
            await ctx.send("MessageStats cog is not loaded.")
            return

        message_count = message_cog.user_message_count[member.id]
        most_used_words = message_cog.user_word_frequency[member.id].most_common(5)
        word_stats = '\n'.join([f'{word}: {count}' for word, count in most_used_words])

        embed = discord.Embed(title=f"Stats for {member.display_name}", color=0x3498db)
        embed.add_field(name="Message Count", value=message_count, inline=False)
        embed.add_field(name="Most Used Words", value=word_stats or "None", inline=False)

        await ctx.send(embed=embed)

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
    @commands.is_owner()
    async def purge(self, ctx, amount: int):
        if amount < 1:
            await ctx.send("Please specify a number greater than 0.")
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f'Deleted {len(deleted)} message(s)', delete_after=5)



async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
