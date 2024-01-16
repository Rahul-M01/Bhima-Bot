import discord
from discord.ext import commands
import random
import asyncio

class BlackjackGame:
    def __init__(self):
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11] * 4
        self.players = {}
        self.in_game = False
        self.standing_players = set()

    def start_game(self, player):
        if self.in_game:
            return "Game is already in progress."
        self.in_game = True
        self.players = {player: {"hand": self.draw_hand(), "bet": 0}}
        hand_message = f"Your starting hand: {self.players[player]['hand']}"
        asyncio.create_task(self.send_hand_dm(player, hand_message))
        return f"Game started. {player.mention}, it's your turn."


    async def send_hand_dm(self, player, message):
        try:
            await player.send(message)
        except discord.errors.Forbidden:
            print(f"Could not send DM to {player.name}. They might have DMs disabled.")

    async def join_game(self, player):
        if self.in_game and player not in self.players:
            self.players[player] = {"hand": self.draw_hand(), "bet": 0}
            hand_message = f"Your hand: {self.players[player]['hand']}"
            await self.send_hand_dm(player, hand_message)
            return f"{player.mention} has joined the game."
        return "Unable to join the game at this time."

    def draw_card(self):
        return random.choice(self.deck)

    def draw_hand(self):
        return [self.draw_card(), self.draw_card()]

    def hand_value(self, hand):
        value = sum(hand)
        if value > 21 and 11 in hand:
            hand[hand.index(11)] = 1
            value = sum(hand)
        return value

    async def hit(self, player):
        if player not in self.players:
            return "You're not in the game."

        player_hand = self.players[player]["hand"]
        player_hand.append(self.draw_card())
        value = self.hand_value(player_hand)
        
        hand_message = f"Your new hand: {value}"
        await self.send_hand_dm(player, hand_message)

        if value > 21:
            return f"{player.mention} busted with {value}!"
        return f"{player.mention} hits."

    async def stand(self, player):
        if player not in self.players:
            return "You're not in the game."

        self.standing_players.add(player)
        player_hand = self.players[player]["hand"]
        value = self.hand_value(player_hand)
        
        hand_message = f"Your final hand: {value}"
        await self.send_hand_dm(player, hand_message)
        if len(self.standing_players) == len(self.players):
            return self.evaluate_winners()
        else:
            return f"{player.mention} stands with {value}."

    def evaluate_winners(self):
        winner_message = ""
        highest_score = 0
        winners = []

        for player, info in self.players.items():
            hand_value = self.hand_value(info["hand"])
            if hand_value > highest_score and hand_value <= 21:
                winners = [player]
                highest_score = hand_value
            elif hand_value == highest_score:
                winners.append(player)

        if winners:
            winner_message = "Winner: " + ", ".join([winner.mention for winner in winners]) + f" with {highest_score}!"
        else:
            winner_message = "No winners this round."

        self.reset_game()
        return winner_message        
    
    def reset_game(self):
        self.players = {}
        self.standing_players = set()
        self.in_game = False

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = BlackjackGame()

    @commands.command()
    async def start_blackjack(self, ctx):
        response = self.game.start_game(ctx.author)
        await ctx.send(response)

    @commands.command()
    async def join_blackjack(self, ctx):
        response = await self.game.join_game(ctx.author)
        await ctx.send(response)

    @commands.command()
    async def hit(self, ctx):
        response = await self.game.hit(ctx.author)
        await ctx.send(response)

    @commands.command()
    async def stand(self, ctx):
        response = await self.game.stand(ctx.author)
        await ctx.send(response)

async def setup(bot):
    await bot.add_cog(Blackjack(bot))
