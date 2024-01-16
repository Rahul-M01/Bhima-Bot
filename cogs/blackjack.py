import discord
from discord.ext import commands
import random
import asyncio
from discord.ui import Button, View
from discord import Embed

class BlackjackGame:
    def __init__(self):
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11] * 4
        self.players = {}
        self.in_game = False
        self.standing_players = set()

    async def start_game(self, player):
        if self.in_game:
            return "Game is already in progress."
        self.in_game = True
        self.players = {player: {"hand": self.draw_hand(), "bet": 0}}
        self.dealer_hand = self.draw_hand()
        hand_message = f"Your starting hand: {self.players[player]['hand']}"
        asyncio.create_task(self.send_hand_dm(player, hand_message))
        return f"Game started. {player.mention}, it's your turn."


    async def send_hand_dm(self, player, message):
        try:
            await player.send(message)
        except discord.errors.Forbidden:
            print(f"Could not send DM to {player.name}. They might have DMs disabled.")

    async def join_game(self, player):
        if not self.in_game:
            return "No game is currently in progress. Please start a new game first."

        if player in self.players:
            return f"{player.mention}, you have already joined the game."

        self.players[player] = {"hand": self.draw_hand(), "bet": 0}
        hand_message = f"Your hand: {self.players[player]['hand']}"
        await self.send_hand_dm(player, hand_message)
        return f"{player.mention} has joined the game."


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
            self.dealer_turn()
            winner_message = self.evaluate_winners()
            return winner_message
        else:
            return f"{player.mention} stands."


    
    def dealer_turn(self):
        dealer_hand_value = self.hand_value(self.dealer_hand)
        action_message = ""

        while dealer_hand_value < 17:
            self.dealer_hand.append(self.draw_card())
            dealer_hand_value = self.hand_value(self.dealer_hand)
            action_message += f"Dealer draws a card: {self.dealer_hand[-1]}\n"
        
        action_message += f"Dealer's final hand: {self.dealer_hand} (Total: {dealer_hand_value})"
        return action_message
        
    def evaluate_winners(self):
        dealer_value = self.hand_value(self.dealer_hand)
        winner_message = f"Dealer's final hand: {self.dealer_hand} (Total: {dealer_value})\n"

        for player, info in self.players.items():
            player_value = self.hand_value(info["hand"])
            player_message = f"{player.mention}"

            if player_value > 21:
                player_message += "Busted\n"
            elif dealer_value > 21:
                if player_value <= 21:
                    player_message += "wins (Dealer Busted)\n"
                else:
                    player_message += "Busted\n"
            elif player_value > dealer_value:
                player_message += f"wins with total {player_value}\n"
            elif player_value == dealer_value:
                player_message += "tied with Dealer\n"
            else:
                pass

            winner_message += player_message

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
    async def blackjack(self, ctx):
        response = await self.game.start_game(ctx.author)

        embed = Embed(title="Blackjack Game", description=response, color=0x00ff00)

        hit_button = Button(label="Hit", style=discord.ButtonStyle.green)
        stand_button = Button(label="Stand", style=discord.ButtonStyle.red)

        async def hit_button_callback(interaction):
            # Use interaction.user instead of ctx.author
            hit_response = await self.game.hit(interaction.user)
            embed.description = hit_response
            await interaction.response.edit_message(embed=embed, view=view)

        async def stand_button_callback(interaction):
            # Use interaction.user instead of ctx.author
            stand_response = await self.game.stand(interaction.user)
            embed.description = stand_response
            await interaction.response.edit_message(embed=embed, view=view)

        hit_button.callback = hit_button_callback
        stand_button.callback = stand_button_callback

        view = View()
        view.add_item(hit_button)
        view.add_item(stand_button)
        await ctx.send(embed=embed, view=view)

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
