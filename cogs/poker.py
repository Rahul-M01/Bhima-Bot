import discord
from discord.ext import commands
from discord.ui import View
from discord import Embed
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import economy
import poker_engine

LOGS_DIR = Path(__file__).resolve().parents[1] / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

STATS_FILE = LOGS_DIR / 'poker_stats.json'
HISTORY_FILE = LOGS_DIR / 'poker_history.json'

BUY_IN_CHIPS = 200     # economy chips each player pays to sit down
BET_SIZE = 100         # table chips per bet (hold'em/omaha/stud late streets)
STUD_SMALL_BET = 50    # third-street small bet
JOIN_TIMEOUT = 30
HAND_HISTORY_MAX = 10

VARIANTS = {
    'holdem': {'name': "Texas Hold'em"},
    'omaha': {'name': 'Omaha'},
    'stud': {'name': 'Seven-Card Stud'},
}


def load_json(path, default):
    if not path.exists():
        return default()
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default()


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def bump_stats(guild_id, user_id, won=False, pot=0):
    stats = load_json(STATS_FILE, dict)
    entry = stats.setdefault(str(guild_id), {}).setdefault(str(user_id), {
        'games': 0, 'wins': 0, 'biggest_pot': 0,
    })
    entry['games'] += 1
    if won:
        entry['wins'] += 1
        entry['biggest_pot'] = max(entry['biggest_pot'], pot)
    save_json(STATS_FILE, stats)


def log_hand(guild_id, user_id, entry):
    history = load_json(HISTORY_FILE, dict)
    hands = history.setdefault(str(guild_id), {}).setdefault(str(user_id), [])
    hands.append(entry)
    history[str(guild_id)][str(user_id)] = hands[-HAND_HISTORY_MAX:]
    save_json(HISTORY_FILE, history)


def top_poker_wins(guild_id, limit=10):
    stats = load_json(STATS_FILE, dict).get(str(guild_id), {})
    ranked = sorted(
        ((uid, s.get('wins', 0), s.get('biggest_pot', 0)) for uid, s in stats.items()),
        key=lambda row: (row[1], row[2]), reverse=True,
    )
    return ranked[:limit]


class PokerPlayer:
    def __init__(self, member):
        self.member = member
        self.hand = []
        self.up_cards = []
        self.chips = BUY_IN_CHIPS
        self.folded = False
        self.acted = False


class PokerGame:
    def __init__(self, channel, variant='holdem'):
        self.channel = channel
        self.variant = variant
        self.players = []
        self.deck = []
        self.community = []
        self.pot = 0
        self.stage = 'waiting'
        self.cancelled = False
        self.act_event = asyncio.Event()

    @property
    def variant_name(self):
        return VARIANTS[self.variant]['name']

    def build_deck(self):
        self.deck = poker_engine.new_deck()

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
        embed = Embed(title=f"{self.variant_name} — {label}", color=0x2ecc71)
        if self.variant == 'stud':
            lines = [
                f"{p.member.display_name}: {poker_engine.fmt_hand(p.up_cards)}"
                for p in self.active()
            ]
            embed.add_field(name="Up Cards", value='\n'.join(lines) or '—', inline=False)
        else:
            embed.add_field(name="Community Cards", value=poker_engine.fmt_hand(self.community), inline=False)
        embed.add_field(name="Pot", value=f"**{self.pot}** chips", inline=True)
        embed.add_field(name="Still in", value=', '.join(p.member.display_name for p in self.active()) or '—', inline=False)
        return embed


class BettingView(View):
    def __init__(self, player, game, bet_size=BET_SIZE):
        super().__init__(timeout=60)
        self.player = player
        self.game = game
        self.bet_size = bet_size
        self.responded = False
        for child in self.children:
            if getattr(child, 'custom_id', None) == 'poker_bet':
                child.label = f"Bet {bet_size}"

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
            amount = min(self.bet_size, self.player.chips)
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

    @discord.ui.button(label="Fold", style=discord.ButtonStyle.red)
    async def fold(self, interaction, button): await self._act(interaction, 'fold')

    @discord.ui.button(label="Check", style=discord.ButtonStyle.grey)
    async def check(self, interaction, button): await self._act(interaction, 'check')

    @discord.ui.button(label="Bet", style=discord.ButtonStyle.green, custom_id='poker_bet')
    async def bet(self, interaction, button): await self._act(interaction, 'bet')


class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def run_betting_round(self, game, bet_size=BET_SIZE, first_player=None):
        players = game.players
        start = players.index(first_player) + 1 if first_player in players else 0
        order = players[start:] + players[:start]

        game.reset_actions()
        while not game.cancelled and not game.all_acted() and len(game.active()) > 1:
            unacted = [p for p in order if not p.acted and not p.folded]
            if not unacted:
                break
            player = unacted[0]
            game.act_event.clear()

            embed = Embed(
                title=f"Your turn, {player.member.display_name}!",
                description=(
                    f"**Your cards:** {poker_engine.fmt_hand(player.hand)}\n"
                    f"**Board:** {poker_engine.fmt_hand(game.community)}\n"
                    f"**Up cards:** {poker_engine.fmt_hand(player.up_cards)}\n"
                    f"**Pot:** {game.pot} | **Chips:** {player.chips}"
                ),
                color=discord.Color.gold()
            )
            await game.channel.send(
                f"{player.member.mention}, it's your turn!",
                embed=embed,
                view=BettingView(player, game, bet_size)
            )
            try:
                await asyncio.wait_for(game.act_event.wait(), timeout=65)
            except asyncio.TimeoutError:
                pass

    async def dm_hole_cards(self, ctx, player):
        try:
            await player.member.send(embed=Embed(
                title="Your Cards",
                description=poker_engine.fmt_hand(player.hand),
                color=discord.Color.blue()
            ))
        except discord.Forbidden:
            await ctx.send(f"⚠️ Couldn't DM {player.member.mention} (DMs disabled).")

    async def deal_initial(self, ctx, game):
        for p in game.players:
            if game.variant == 'stud':
                p.hand = game.deal(3)          # two down, door card up
                p.up_cards = p.hand[2:]
            else:
                p.hand = game.deal(4 if game.variant == 'omaha' else 2)
            await self.dm_hole_cards(ctx, p)

    def resolve_hand(self, game, player):
        """Shared evaluator across variants — Omaha must use exactly two hole cards."""
        if game.variant == 'omaha':
            return poker_engine.best_omaha_hand(player.hand, game.community)
        return poker_engine.best_hand(tuple(player.hand) + tuple(game.community))

    async def showdown(self, game):
        game.stage = 'showdown'
        active = game.active()
        if len(active) == 1:
            winner = active[0]
            winner.chips += game.pot
            await game.channel.send(embed=Embed(
                title="Winner!",
                description=f"{winner.member.mention} wins **{game.pot}** chips — everyone else folded!",
                color=discord.Color.gold()
            ))
            return [winner], {winner.member.id: game.pot}

        embed = Embed(title=f"{game.variant_name} — Showdown!", color=discord.Color.gold())
        results = []
        for p in active:
            best, score = self.resolve_hand(game, p)
            results.append((p, best, score))
            embed.add_field(
                name=p.member.display_name,
                value=(
                    f"Cards: {poker_engine.fmt_hand(p.hand)}\n"
                    f"Best: {poker_engine.fmt_hand(best)} — **{poker_engine.HAND_NAMES[score[0]]}**"
                ),
                inline=False
            )

        top = max(score for _, _, score in results)
        winners = [r for r in results if r[2] == top]
        share, remainder = divmod(game.pot, len(winners))
        awarded = {}
        for i, (winner, _, _) in enumerate(winners):
            amount = share + (remainder if i == 0 else 0)
            winner.chips += amount
            awarded[winner] = amount

        embed.add_field(
            name="Result",
            value=', '.join(w.member.mention for w, _, _ in winners)
                  + f" win{'s' if len(winners) == 1 else ''} **{share}** chips each!",
            inline=False
        )
        await game.channel.send(embed=embed)
        return [w for w, _, _ in winners], {w.member.id: amount for w, amount in awarded.items()}

    async def conclude(self, ctx, game, winners, awarded=None, note=None):
        """Record stats/hand histories and cash table chips back into the economy."""
        awarded = awarded or {}
        winners = winners or []
        winner_ids = {w.member.id for w in winners}
        pot_total = game.pot
        game.pot = 0
        for p in game.players:
            won = p.member.id in winner_ids
            best = ''
            if not p.folded:
                _, score = self.resolve_hand(game, p)
                best = poker_engine.HAND_NAMES[score[0]]
            if note == 'ended':
                result = 'Ended early'
            elif won:
                result = f"Won {awarded.get(p.member.id, pot_total)}"
            elif p.folded:
                result = 'Folded'
            else:
                result = 'Lost'
            log_hand(ctx.guild.id, p.member.id, {
                'variant': game.variant_name,
                'hand': poker_engine.fmt_hand(p.hand),
                'board': poker_engine.fmt_hand(game.community),
                'best': best,
                'result': result,
                'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            })
            bump_stats(ctx.guild.id, p.member.id, won=won, pot=pot_total if won else 0)
            economy.add_chips(ctx.guild.id, p.member.id, p.chips)
            p.chips = 0

        self.games.pop(ctx.guild.id, None)

    async def run_game(self, ctx, game):
        try:
            game.build_deck()
            await self.deal_initial(ctx, game)

            if game.variant == 'stud':
                streets = [('third_street', STUD_SMALL_BET), ('seventh_street', BET_SIZE)]
                deals = [None, 4]
            else:
                streets = [('pre_flop', BET_SIZE), ('flop', BET_SIZE),
                           ('turn', BET_SIZE), ('river', BET_SIZE)]
                deals = [0, 3, 1, 1]

            winners = []
            awarded = None
            door_holder = None

            for i, (stage_name, bet_size) in enumerate(streets):
                n = deals[i]
                if n:
                    for p in game.active():
                        p.hand += game.deal(n)
                        if game.variant == 'stud':
                            if stage_name == 'third_street':
                                p.up_cards = p.hand[2:]
                            else:
                                p.up_cards += p.hand[-4:-1]
                            await self.dm_hole_cards(ctx, p)
                game.community += game.deal(n) if game.variant != 'stud' else []
                game.stage = stage_name
                await ctx.send(embed=game.community_embed())

                first_player = door_holder
                if game.variant == 'stud' and stage_name == 'third_street':
                    # Simplified bring-in: act starts left of the lowest up card.
                    door_holder = min(game.active(), key=lambda p: poker_engine.RVAL[p.hand[2][0]])
                    embed = discord.Embed(
                        title="Door Card",
                        description=f"{door_holder.member.display_name} has the door card "
                                    f"({door_holder.up_cards[0]}); betting starts to their left.",
                        color=discord.Color.blurple()
                    )
                    await ctx.send(embed=embed)
                    first_player = door_holder

                await self.run_betting_round(game, bet_size, first_player)
                if game.cancelled:
                    return await self.conclude(ctx, game, [], note='ended')
                if len(game.active()) <= 1:
                    break

            if game.cancelled:
                return await self.conclude(ctx, game, [], note='ended')
            winners, awarded = await self.showdown(game)
            await self.conclude(ctx, game, winners, awarded)
        finally:
            # Safety net: never leave a stale game or unreturned chips behind.
            if ctx.guild.id in self.games and self.games[ctx.guild.id] is game:
                game.cancelled = True
                await self.conclude(ctx, game, [], note='ended')

    @commands.command(name='startpoker',
                      help="Start a poker game: !startpoker [holdem|omaha|stud]. Others join with !joinpoker.")
    async def start_poker(self, ctx, variant: str = 'holdem'):
        key = poker_engine.variant_key(variant)
        if key is None:
            await ctx.send("Unknown variant. Choose `holdem`, `omaha` or `stud`.")
            return
        if ctx.guild.id in self.games:
            await ctx.send('A game is already in progress. Join with `!joinpoker`.')
            return

        game = PokerGame(ctx.channel, key)
        game.players.append(PokerPlayer(ctx.author))
        self.games[ctx.guild.id] = game

        await ctx.send(embed=Embed(
            title=f"{game.variant_name} Starting!",
            description=(
                f"**{ctx.author.display_name}** opened a table.\n"
                f"Type `!joinpoker` to join.\n"
                f"Buy-in: **{BUY_IN_CHIPS}** chips from your balance (`!balance`).\n"
                f"Game starts in **{JOIN_TIMEOUT}s**..."
            ),
            color=discord.Color.green()
        ))
        await asyncio.sleep(JOIN_TIMEOUT)

        if ctx.guild.id not in self.games:
            return
        if len(game.players) < 2:
            await ctx.send(f"Not enough players (need at least 2). Game cancelled.")
            self.games.pop(ctx.guild.id, None)
            return

        seated = []
        for p in game.players:
            if economy.spend_chips(ctx.guild.id, p.member.id, BUY_IN_CHIPS):
                seated.append(p)
            else:
                balance = economy.get_balance(ctx.guild.id, p.member.id)
                await ctx.send(f"{p.member.mention} can't afford the **{BUY_IN_CHIPS}** chip buy-in "
                               f"(balance **{balance}**) and was dropped.")
        if len(seated) < 2:
            for p in seated:
                economy.add_chips(ctx.guild.id, p.member.id, BUY_IN_CHIPS)
            await ctx.send("Not enough players could cover the buy-in. Game cancelled, buy-ins refunded.")
            self.games.pop(ctx.guild.id, None)
            return
        game.players = seated

        await ctx.send(f"Starting **{game.variant_name}** with **{len(seated)}** players! Check your DMs for cards.")
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
        if economy.get_balance(ctx.guild.id, ctx.author.id) < BUY_IN_CHIPS:
            await ctx.send(f"You need at least **{BUY_IN_CHIPS}** chips to buy in. Try `!daily`.")
            return
        game.players.append(PokerPlayer(ctx.author))
        await ctx.send(f'{ctx.author.mention} joined! ({len(game.players)} players)')

    @commands.command(name='endpoker', help='Force-end the current poker game and refund remaining chips.')
    @commands.has_permissions(manage_messages=True)
    async def end_poker(self, ctx):
        game = self.games.get(ctx.guild.id)
        if not game:
            await ctx.send('No poker game running.')
            return
        game.cancelled = True
        game.act_event.set()
        if game.stage == 'waiting':
            self.games.pop(ctx.guild.id, None)
        await ctx.send('Game ended; remaining chips will be refunded.')

    @commands.command(name='pokertop', help='Top chip holders on this server.')
    async def poker_top(self, ctx):
        holders = economy.top_holders(ctx.guild.id)
        if not holders:
            await ctx.send('No chip balances yet — claim some with `!daily`.')
            return
        lines = []
        for i, (user_id, amount) in enumerate(holders, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f'User {user_id}'
            lines.append(f"`{i}.` **{name}** — {amount:,} chips")
        await ctx.send(embed=Embed(title="🏆 Top Chip Holders", description='\n'.join(lines),
                                   color=discord.Color.gold()))

    @commands.command(name='pokerwins', help='Leaderboard of poker wins and biggest pots.')
    async def poker_wins(self, ctx):
        rows = top_poker_wins(ctx.guild.id)
        rows = [row for row in rows if row[1]]
        if not rows:
            await ctx.send('No poker wins recorded yet. Play a hand with `!startpoker`!')
            return
        lines = []
        for i, (user_id, wins, biggest_pot) in enumerate(rows, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f'User {user_id}'
            lines.append(f"`{i}.` **{name}** — {wins} win(s), biggest pot **{biggest_pot:,}**")
        await ctx.send(embed=Embed(title="♠️ Poker Wins Leaderboard", description='\n'.join(lines),
                                   color=0x2ecc71))

    @commands.command(name='pokerstats', aliases=['mystats'],
                      help='Show your (or another member\'s) poker record. Usage: !pokerstats [@user]')
    async def poker_stats(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        stats = load_json(STATS_FILE, dict).get(str(ctx.guild.id), {}).get(str(member.id))
        if not stats or not stats.get('games'):
            await ctx.send(f"No hands recorded for {member.mention} yet.")
            return
        games = stats.get('games', 0)
        wins = stats.get('wins', 0)
        rate = round((wins / games) * 100, 1) if games else 0
        await ctx.send(embed=Embed(
            title=f"Poker Record — {member.display_name}",
            description=(
                f"**Games played:** {games}\n"
                f"**Wins:** {wins} ({rate}%)\n"
                f"**Biggest pot:** {stats.get('biggest_pot', 0):,} chips"
            ),
            color=0x2ecc71
        ))

    @commands.command(name='handhistory', help='Show your last recorded poker hands. Usage: !handhistory [@user]')
    async def hand_history(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        hands = load_json(HISTORY_FILE, dict).get(str(ctx.guild.id), {}).get(str(member.id), [])
        if not hands:
            await ctx.send(f"No hand history for {member.mention} yet.")
            return
        lines = []
        for h in reversed(hands[-5:]):
            line = f"`[{h.get('ts', '?')}]` **{h.get('variant', '?')}** — {h.get('hand', '—')}"
            if h.get('board') and h['board'] != '—':
                line += f" | Board: {h['board']}"
            line += f" → *{h.get('result', '?')}*"
            if h.get('best'):
                line += f" ({h['best']})"
            lines.append(line)
        await ctx.send(embed=Embed(
            title=f"Last Hands — {member.display_name}",
            description='\n'.join(lines),
            color=discord.Color.blurple()
        ))

    @start_poker.error
    @join_poker.error
    @end_poker.error
    @poker_top.error
    @poker_wins.error
    @poker_stats.error
    @hand_history.error
    async def poker_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument. Make sure you're mentioning a valid user.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(PokerCog(bot))
