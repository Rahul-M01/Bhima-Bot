import discord
from discord.ext import commands
from collections import deque

class DeletedMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deleted_messages = deque(maxlen=10)  # Adjust maxlen as needed
        self.edited_messages = deque(maxlen=10)   # Adjust maxlen as needed

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.author.bot:
            self.deleted_messages.append(f"{message.author.name}: {message.content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.author.bot:
            self.edited_messages.append(f"{before.author.name} (Original): {before.content}")

    @commands.command(name='deleted', help='Shows recently deleted messages')
    @commands.has_permissions(manage_messages=True)
    async def show_deleted(self, ctx):
        if not self.deleted_messages:
            await ctx.send("No recently deleted messages.")
            return

        embed = discord.Embed(title="Recently Deleted Messages", description="\n".join(self.deleted_messages), color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name='edited', help='Shows recently edited messages')
    @commands.has_permissions(manage_messages=True)
    async def show_edited(self, ctx):
        if not self.edited_messages:
            await ctx.send("No recently edited messages.")
            return

        embed = discord.Embed(title="Recently Edited Messages (Original Versions)", description="\n".join(self.edited_messages), color=discord.Color.blue())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(DeletedMessages(bot))
