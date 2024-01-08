import discord
from discord.ext import commands
import asyncio
import random

class PokerGame:
    def __init__(self):
        self.players = []
        self.deck = self.create_deck()
        self.current_turn = 0
        self.game_stage = 'pre-flop'

    def create_deck(self):
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        return [f'{rank} of {suit}' for suit in suits for rank in ranks]

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def deal_cards(self, num_cards):
    # Ensure there are enough cards in the deck
        if len(self.deck) < num_cards:
            raise ValueError("Not enough cards in the deck to deal.")
        return [self.deck.pop() for _ in range(num_cards)]


    def add_player(self, player):
        self.players.append(player)
    
class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # Dictionary to track games by server

    @commands.command(name='startpoker')
    async def start_poker(self, ctx):
        if ctx.guild.id in self.games:
            await ctx.send('A game is already in progress in this server.')
            return

        self.games[ctx.guild.id] = PokerGame()
        await ctx.send('Poker game started! Type `!joinpoker` to join.')

        # Wait for players to join
        await asyncio.sleep(10)

        # Start the game
        await self.start_game(ctx)


    @commands.command(name='joinpoker')
    async def join_poker(self, ctx):
        if ctx.guild.id not in self.games:
            await ctx.send('No poker game is currently running. Start one with `!startpoker`.')
            return

        game = self.games[ctx.guild.id]
        game.add_player({'id': ctx.author.id, 'hand': []})
        await ctx.send(f'{ctx.author.name} has joined the game.')

    async def end_game(self, ctx):
        del self.games[ctx.guild.id]
        await ctx.send('Poker game ended.')


async def setup(bot):
    await bot.add_cog(PokerCog(bot))
