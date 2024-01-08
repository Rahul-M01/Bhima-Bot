from discord.ext import commands
from collections import defaultdict, Counter
import discord
import json

class MessageStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_message_count = defaultdict(lambda: defaultdict(int))
        self.user_word_frequency = defaultdict(lambda: defaultdict(Counter))
        self.data_file = '../logs/message_stats.json'  # Path to your JSON file
        self.load_data()
        
    def load_data(self):
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)

                # Reconstruct defaultdict structure for user_message_count
                self.user_message_count = defaultdict(lambda: defaultdict(int))
                user_message_data = data.get('user_message_count', {})
                if isinstance(user_message_data, dict):
                    for guild_id, counts in user_message_data.items():
                        if isinstance(counts, dict):
                            self.user_message_count[int(guild_id)].update({int(user_id): count for user_id, count in counts.items()})

                # Reconstruct defaultdict structure for user_word_frequency
                self.user_word_frequency = defaultdict(lambda: defaultdict(Counter))
                user_word_data = data.get('user_word_frequency', {})
                if isinstance(user_word_data, dict):
                    for guild_id, users in user_word_data.items():
                        if isinstance(users, dict):
                            for user_id, words in users.items():
                                if isinstance(words, dict):
                                    self.user_word_frequency[int(guild_id)][int(user_id)].update(words)
        except FileNotFoundError:
            self.user_message_count = defaultdict(lambda: defaultdict(int))
            self.user_word_frequency = defaultdict(lambda: defaultdict(Counter))


    def save_data(self):
        data = {
            'user_message_count': dict(self.user_message_count),
            'user_word_frequency': {user: dict(counter) for user, counter in self.user_word_frequency.items()}
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or message.content.startswith(self.bot.command_prefix):
            return

        guild_id = message.guild.id  # Get the server ID
        author_id = message.author.id
        self.user_message_count[guild_id][author_id] += 1

        words = message.content.lower().split()
        for word in words:
            self.user_word_frequency[guild_id][message.author.id][word] += 1

        # Save data to file
        self.save_data()

    #==============================================================
    #          Shows Total Messages, along with Top 5 Words
    #==============================================================
    @commands.command(name='messages', help='Shows Total Messages, along with Top 5 Words')
    async def messages(self, ctx):
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        message_count = self.user_message_count[guild_id][user_id]
        most_used_words = self.user_word_frequency[guild_id][user_id].most_common(5)
        word_stats = '\n'.join([f'{word}: {count}' for word, count in most_used_words])
        
        embed = discord.Embed(title=f"Your Stats", color=0x3498db)
        embed.add_field(name="Message Count", value=message_count, inline=False)
        embed.add_field(name="Most Used Words", value=word_stats or "None", inline=False)

        await ctx.send(embed=embed)

    #====================================================
    #       Shows top 5 most messaging users
    #====================================================
    @commands.command(name='messagestats', help='Shows top 5 most messaging users')
    async def message_stats(self, ctx):
        guild_id = ctx.guild.id
        top_users = sorted(self.user_message_count[guild_id].items(), key=lambda x: x[1], reverse=True)[:5]
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
