import discord
from discord.ext import commands, tasks
import random
import asyncio

class BlackjackGame:
    def __init__(self):
        self.deck = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
        random.shuffle(self.deck)
        self.players = []
        self.hands = {}
        self.current_turn = 0

    def deal_card(self, hand):
        if len(self.deck) == 0:
            self.deck = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
            random.shuffle(self.deck)
        card = self.deck.pop()
        hand.append(card)
        return card

    def calculate_score(self, hand):
        score = 0
        ace_count = 0
        for card in hand:
            if card in 'JQK':
                score += 10
            elif card == 'A':
                ace_count += 1
                score += 11
            else:
                score += int(card)
        while score > 21 and ace_count:
            score -= 10
            ace_count -= 1
        return score

    def start_game(self):
        for player in self.players:
            self.hands[player] = []
            self.deal_card(self.hands[player])
            self.deal_card(self.hands[player])

class BlackjackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = None
        self.game_starter = None
        self.current_turn= 0 # Initialize current_turn here
        self.start_time = 30 # seconds until the game starts automatically

    @commands.command()
    async def join_blackjack(self, ctx):
        if not self.game:
            self.game = BlackjackGame()
            self.game_starter = ctx.author
            self.start_game_timer.start()
        if ctx.author not in self.game.players:
            self.game.players.append(ctx.author)
            await ctx.send(f"{ctx.author.display_name} has joined the blackjack game.")
        else:
            await ctx.send("You're already in the game.")

    @tasks.loop(seconds=1.0)
    async def start_game_timer(self):
        if self.start_time > 0:
            self.start_time -= 1

        else:
            self.start_game_timer.stop()
            await self.start_game()

    async def start_game(self):
        if not self.game or len(self.game.players) < 2:
            await self.game_starter.send("Not enough players to start the game.")
            self.reset_game()
            return

        self.game.start_game()
        for player in self.game.players:
            hand = self.game.hands[player]
            score = self.game.calculate_score(hand)
            try:
                await player.send(f"Your starting hand: {', '.join(hand)}. Score: {score}")
            except discord.Forbidden:
                pass  # Handle if DMs are closed
        await self.next_turn()

    async def next_turn(self, ctx):
        if self.game:
            self.current_turn += 1
            if self.current_turn >= len(self.game.players):
                await self.dealer_turn()
            else:
                player = self.game.players[self.current_turn]
                try:
                    await ctx.send("{self.player} turn. Use !hit or !stand.")
                except discord.Forbidden:
                    # Notify in the channel if DMs are closed or an error occurs
                    await self.bot.get_channel(self.game_starter.channel.id).send(
                    f"{player.mention}, it's your turn, but I couldn't send you a DM. Please check your DM settings!")

    @commands.command()
    async def hit(self, ctx):
        if not self.game or ctx.author != self.game.players[self.current_turn]:
            return

        hand = self.game.hands[ctx.author]
        self.game.deal_card(hand)
        score = self.game.calculate_score(hand)

        if score > 21:
            await ctx.send("Bust! You're out of the game.")
            self.current_turn += 1
            await self.next_turn()
        else:
            await ctx.send(f"You drew a card. Your hand: {', '.join(hand)}. Score: {score}")

    @commands.command()
    async def stand(self, ctx):
        if not self.game or ctx.author != self.game.players[self.current_turn]:
            return

        self.current_turn += 1
        await self.next_turn()

    async def dealer_turn(self):
        dealer_hand = []
        self.game.deal_card(dealer_hand)
        self.game.deal_card(dealer_hand)
        dealer_score = self.game.calculate_score(dealer_hand)

        while dealer_score < 17:
            self.game.deal_card(dealer_hand)
            dealer_score = self.game.calculate_score(dealer_hand)

        dealer_message = f"Dealer's final hand: {', '.join(dealer_hand)}. Score: {dealer_score}\n"
        results = [dealer_message]

        for player in self.game.players:
            player_hand = self.game.hands[player]
            player_score = self.game.calculate_score(player_hand)

            if player_score > 21:
                result = f"{player.display_name} busted with {player_score}. Dealer wins."
            elif dealer_score > 21 or player_score > dealer_score:
                result = f"{player.display_name} wins with {player_score} against dealer's {dealer_score}."
            elif player_score == dealer_score:
                result = f"{player.display_name} ties with the dealer at {player_score}."
            else:
                result = f"Dealer wins with {dealer_score} against {player.display_name}'s {player_score}."

            results.append(result)

        for player in self.game.players:
            try:
                await player.send('\n'.join(results))
            except discord.Forbidden:
                pass  # Handle if DMs are closed

        self.reset_game()


    def reset_game(self):
        self.game = None
        self.game_starter = None
        self.current_turn = 0
        self.start_time = 10

async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))