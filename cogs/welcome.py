import discord
from discord.ext import commands
import random

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_messages = [
            "Welcome to the server, {user}!",
            "Glad you're here, {user}!",
            "Fantastic! {user} has joined us!",
            "Hey {user}, welcome to our Discord server!",
            "It's great to have you with us, {user}!"
        ]
        self.welcome_channel_name = "welcome"

    async def get_or_create_welcome_channel(self, guild):
        # Check if the welcome channel exists
        for channel in guild.text_channels:
            if channel.name == self.welcome_channel_name:
                return channel

        # If not, create the welcome channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False),
            guild.me: discord.PermissionOverwrite(send_messages=True)
        }
        welcome_channel = await guild.create_text_channel(self.welcome_channel_name, overwrites=overwrites)
        return welcome_channel

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        welcome_message = random.choice(self.welcome_messages).format(user=member.mention)

        # Get or create the welcome channel
        channel = await self.get_or_create_welcome_channel(guild)

        if channel:
            await channel.send(welcome_message)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
