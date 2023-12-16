import discord
from discord.ext import commands

class CustomHelpCog(commands.Cog, name="Help"):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = CustomHelpCommand()
        bot.help_command.cog = self  # Set the cog

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Bot Commands", color=discord.Color.blue())
        for cog, commands in mapping.items():
            filtered = [command for command in commands if not command.hidden]
            command_signatures = [self.get_command_signature(command) for command in filtered]
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=self.get_command_signature(command),
                              description=command.help or "No description provided",
                              color=discord.Color.green())
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = discord.Embed(title=self.get_command_signature(group),
                              description=group.help or "No description provided",
                              color=discord.Color.green())
        filtered = [command for command in group.commands if not command.hidden]
        for command in filtered:
            embed.add_field(name=self.get_command_signature(command), 
                            value=command.help or "No description provided", 
                            inline=False)
        await self.get_destination().send(embed=embed)

    def get_command_signature(self, command):
        return f'{self.context.prefix}{command.qualified_name} {command.signature}'


async def setup(bot):
    await bot.add_cog(CustomHelpCog(bot))
