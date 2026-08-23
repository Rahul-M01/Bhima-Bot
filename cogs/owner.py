from discord.ext import commands

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

    @reload_cogs.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Only the bot owner can use this command.")
        else:
            raise error

async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
