import discord
from discord.ext import commands
from discord.ui import View
from discord import Embed
import asyncio
import random
from collections import Counter
from itertools import combinations

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RVAL = {r: i + 2 for i, r in enumerate(RANKS)}

HAND_NAMES = [
    'High Card', 'One Pair', 'Two Pair', 'Three of a Kind',
    'Straight', 'Flush', 'Full House', 'Four of a Kind', 'Straight Flush'
]

STARTING_CHIPS = 1000
BET_SIZE = 100
JOIN_TIMEOUT = 30


def fmt_hand(cards):
    return ' '.join(f"{r}{s}" for r, s in cards) if cards else '—'


def evaluate(five):
    vals = sorted([RVAL[c[0]] for c in five], reverse=True)
    suits = [c[1] for c in five]
    flush = len(set(suits)) == 1
    straight = vals == list(range(vals[0], vals[0] - 5, -1)) or vals == [14, 5, 4, 3, 2]
    if vals == [14, 5, 4, 3, 2]:
        vals = [5, 4, 3, 2, 1]
    cnt = Counter(vals)
    groups = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    gv = [g[0] for g in groups]
    gc = [g[1] for g in groups]
    if straight and flush: return (8, vals)
    if gc[0] == 4:         return (7, gv)
    if gc[:2] == [3, 2]:   return (6, gv)
    if flush:              return (5, vals)
    if straight:           return (4, vals)
    if gc[0] == 3:         return (3, gv)
    if gc[:2] == [2, 2]:   return (2, gv)
    if gc[0] == 2:         return (1, gv)
    return (0, vals)


def best_hand(cards):
    best = max(combinations(cards, 5), key=evaluate)
    return list(best), evaluate(list(best))


class PokerPlayer:
    def __init__(self, member):
        self.member = member
        self.hand = []
        self.chips = STARTING_CHIPS
        self.folded = False
        self.acted = False


class PokerGame:
    def __init__(self, channel):
        self.channel = channel
        self.players = []
        self.deck = []
        self.community = []
        self.pot = 0
        self.stage = 'waiting'
        self.act_event = asyncio.Event()

    def build_deck(self):
        self.deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)

    def deal(self, n=1):
        return [self.deck.pop() for _ in range(n)]

    def active(self):
        return [p for p in self.players if not p.folded]

    def all_acted(self):
        return all(p.acted or p.folded for p in self.players)

    def reset_actions(self):
        for p in self.players:
            if not p.folded:
                p.acted = False

    def community_embed(self):
        label = self.stage.replace('_', ' ').title()
        embed = Embed(title=f"Texas Hold'em — {label}", color=0x2ecc71)
        embed.add_field(name="Community Cards", value=fmt_hand(self.community), inline=False)
        embed.add_field(name="Pot", value=f"**{self.pot}** chips", inline=True)
        embed.add_field(name="Still in", value=', '.join(p.member.display_name for p in self.active()) or '—', inline=False)
        return embed


class BettingView(View):
    def __init__(self, player, game):
        super().__init__(timeout=60)
        self.player = player
        self.game = game
        self.responded = False

    async def _act(self, interaction, action):
        if interaction.user.id != self.player.member.id:
            return await interaction.response.send_message("It's not your turn.", ephemeral=True)
        if self.responded:
            return await interaction.response.send_message("Already acted.", ephemeral=True)
        self.responded = True
        self.stop()

        if action == 'fold':
            self.player.folded = True
            self.player.acted = True
            msg = f"{self.player.member.display_name} **folds**."
        elif action == 'check':
            self.player.acted = True
            msg = f"{self.player.member.display_name} **checks**."
        else:
            amount = min(BET_SIZE, self.player.chips)
            self.player.chips -= amount
            self.game.pot += amount
            self.player.acted = True
            for p in self.game.active():
                if p is not self.player:
                    p.acted = False
            msg = f"{self.player.member.display_name} **bets {amount}** chips. Pot: **{self.game.pot}**"

        await interaction.response.edit_message(content=msg, embed=None, view=None)
        self.game.act_event.set()

    async def on_timeout(self):
        if not self.responded:
            self.responded = True
            self.player.folded = True
            self.player.acted = True
            await self.game.channel.send(f"⏰ {self.player.member.mention} took too long and was auto-folded.")
            self.game.act_event.set()

    @discord.ui.button(label="Fold",            style=discord.ButtonStyle.red)
    async def fold(self, interaction, button): await self._act(interaction, 'fold')

    @discord.ui.button(label="Check",           style=discord.ButtonStyle.grey)
    async def check(self, interaction, button): await self._act(interaction, 'check')

    @discord.ui.button(label=f"Bet {BET_SIZE}", style=discord.ButtonStyle.green)
    async def bet(self, interaction, button):  await self._act(interaction, 'bet')


class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def run_betting_round(self, game):
        game.reset_actions()
        while not game.all_acted() and len(game.active()) > 1:
            unacted = [p for p in game.active() if not p.acted]
            if not unacted:
                break
            player = unacted[0]
            game.act_event.clear()

            embed = Embed(
                title=f"Your turn, {player.member.display_name}!",
                description=(
                    f"**Your hand:** {fmt_hand(player.hand)}\n"
                    f"**Community:** {fmt_hand(game.community)}\n"
                    f"**Pot:** {game.pot} | **Chips:** {player.chips}"
                ),
                color=discord.Color.gold()
            )
            await game.channel.send(
                f"{player.member.mention}, it's your turn!",
                embed=embed,
                view=BettingView(player, game)
            )
            try:
                await asyncio.wait_for(game.act_event.wait(), timeout=65)
            except asyncio.TimeoutError:
                pass

    async def showdown(self, game):
        active = game.active()
        if len(active) == 1:
            w = active[0]
            w.chips += game.pot
            await game.channel.send(embed=Embed(
                title="Winner!",
                description=f"{w.member.mention} wins **{game.pot}** chips — everyone else folded!",
                color=discord.Color.gold()
            ))
            return

        embed = Embed(title="Showdown!", color=discord.Color.gold())
        results = []
        for p in active:
            hand, score = best_hand(p.hand + game.community)
            results.append((p, hand, score, HAND_NAMES[score[0]]))
            embed.add_field(
                name=p.member.display_name,
                value=f"Hole: {fmt_hand(p.hand)}\nBest: {fmt_hand(hand)} — **{HAND_NAMES[score[0]]}**",
                inline=False
            )

        top = max(r[2] for r in results)
        winners = [r for r in results if r[2] == top]
        split = game.pot // len(winners)
        for w, *_ in winners:
            w.chips += split

        embed.add_field(
            name="Result",
            value=', '.join(r[0].member.mention for r in winners) + f" win{'s' if len(winners) == 1 else ''} **{split}** chips each!",
            inline=False
        )
        await game.channel.send(embed=embed)

    async def run_game(self, ctx, game):
        game.build_deck()
        for p in game.players:
            p.hand = game.deal(2)
            try:
                await p.member.send(embed=Embed(
                    title="Your Hole Cards",
                    description=fmt_hand(p.hand),
                    color=discord.Color.blue()
                ))
            except discord.Forbidden:
                await ctx.send(f"⚠️ Couldn't DM {p.member.mention} (DMs disabled).")

        for stage_name, n in [('pre_flop', 0), ('flop', 3), ('turn', 1), ('river', 1)]:
            if n:
                game.community += game.deal(n)
            game.stage = stage_name
            await ctx.send(embed=game.community_embed())
            await self.run_betting_round(game)
            if stage_name != 'river' and len(game.active()) <= 1:
                await self.showdown(game)
                del self.games[ctx.guild.id]
                return

        await self.showdown(game)
        del self.games[ctx.guild.id]

    @commands.command(name='startpoker', help="Start a Texas Hold'em game. Others join with !joinpoker.")
    async def start_poker(self, ctx):
        if ctx.guild.id in self.games:
            await ctx.send('A game is already in progress. Join with `!joinpoker`.')
            return

        game = PokerGame(ctx.channel)
        game.players.append(PokerPlayer(ctx.author))
        self.games[ctx.guild.id] = game

        await ctx.send(embed=Embed(
            title="Texas Hold'em Starting!",
            description=f"**{ctx.author.display_name}** opened a table.\nType `!joinpoker` to join.\nGame starts in **{JOIN_TIMEOUT}s**...",
            color=discord.Color.green()
        ))
        await asyncio.sleep(JOIN_TIMEOUT)

        if len(game.players) < 2:
            await ctx.send("Not enough players (need at least 2). Game cancelled.")
            del self.games[ctx.guild.id]
            return

        await ctx.send(f"Starting with **{len(game.players)}** players! Check your DMs for hole cards.")
        await self.run_game(ctx, game)

    @commands.command(name='joinpoker', help='Join a poker lobby before the game starts.')
    async def join_poker(self, ctx):
        game = self.games.get(ctx.guild.id)
        if not game:
            await ctx.send('No poker game running. Start one with `!startpoker`.')
            return
        if game.stage != 'waiting':
            await ctx.send('The game has already started.')
            return
        if any(p.member.id == ctx.author.id for p in game.players):
            await ctx.send(f'{ctx.author.mention}, you already joined.')
            return
        game.players.append(PokerPlayer(ctx.author))
        await ctx.send(f'{ctx.author.mention} joined! ({len(game.players)} players)')

    @commands.command(name='endpoker', help='Force-end the current poker game.')
    @commands.has_permissions(manage_messages=True)
    async def end_poker(self, ctx):
        if ctx.guild.id not in self.games:
            await ctx.send('No poker game running.')
            return
        del self.games[ctx.guild.id]
        await ctx.send('Game ended.')


async def setup(bot):
    await bot.add_cog(PokerCog(bot))
