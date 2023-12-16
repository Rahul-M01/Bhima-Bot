from discord.ext import commands
from collections import defaultdict, Counter
import discord

class MessageStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_message_count = defaultdict(int)
        self.user_word_frequency = defaultdict(Counter)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith(self.bot.command_prefix):
            return
        # Update message count
        self.user_message_count[message.author.id] += 1

        words = message.content.lower().split()
        for word in words:
            self.user_word_frequency[message.author.id][word] += 1

    #==============================================================
    #          Shows Total Messages, along with Top 5 Words
    #==============================================================
    @commands.command()
    async def messages(self, ctx):
        user_id = ctx.author.id
        message_count = self.user_message_count[user_id]
        most_used_words = self.user_word_frequency[user_id].most_common(5)
        word_stats = '\n'.join([f'{word}: {count}' for word, count in most_used_words])
        
        embed = discord.Embed(title=f"Your Stats", color=0x3498db)
        embed.add_field(name="Message Count", value=message_count, inline=False)
        embed.add_field(name="Most Used Words", value=word_stats or "None", inline=False)

        await ctx.send(embed=embed)

    #====================================================
    #       Shows top 5 most messaging users
    #====================================================
    @commands.command()
    async def message_stats(self, ctx):
        top_users = sorted(self.user_message_count.items(), key=lambda x: x[1], reverse=True)[:5]
        embed = discord.Embed(title="Top Messaging Users", color=0x3498db)

        for user_id, count in top_users:
            try:
                # Fetch user from Discord API
                user = await self.bot.fetch_user(user_id)
                name = user.display_name if user else f"ID: {user_id}"
            except discord.NotFound:
                # Handle case where user is not found
                name = f"ID: {user_id}"

            embed.add_field(name=name, value=f"{count} messages", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MessageStats(bot))
