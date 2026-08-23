import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import random
from pathlib import Path

import economy

LOGS_DIR = Path(__file__).resolve().parents[1] / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

STATS_FILE = LOGS_DIR / 'blackjack_stats.json'

MIN_BET = 10
MAX_BET = 5000

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS = ['♠', '♥', '♦', '♣']


def load_stats():
    if not STATS_FILE.exists():
        return {}
    try:
        with open(STATS_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_stats(data):
    with open(STATS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def card_value(rank):
    if rank == 'A':
        return 11
    if rank in ('10', 'J', 'Q', 'K'):
        return 10
    return int(rank)


def hand_value(cards):
    """Best total with aces counted as 11 then demoted as needed."""
    total = sum(card_value(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def fmt_cards(cards):
    return ' '.join(f"{r}{s}" for r, s in cards)


def resolve_outcome(player_total, player_natural, dealer_total, dealer_natural):
    if player_natural or dealer_natural:
        if player_natural and dealer_natural:
            return 'push'
        return 'player_blackjack' if player_natural else 'dealer_blackjack'
    if player_total > 21:
        return 'bust'
    if dealer_total > 21:
        return 'dealer_bust'
    if player_total > dealer_total:
        return 'win'
    if player_total == dealer_total:
        return 'push'
    return 'lose'


def payout_for(bet, outcome):
    """Total chips returned to the player (stake included); 3:2 for naturals."""
    if outcome == 'player_blackjack':
        return bet + (bet * 3) // 2
    if outcome in ('win', 'dealer_bust'):
        return bet * 2
    if outcome == 'push':
        return bet
    return 0


def bump_stats(guild_id, user_id, payout, bet):
    stats = load_stats()
    entry = stats.setdefault(str(guild_id), {}).setdefault(str(user_id), {
        'hands': 0, 'wins': 0, 'losses': 0, 'pushes': 0, 'net': 0, 'biggest_win': 0,
    })
    entry['hands'] += 1
    net = payout - bet
    if payout == 0:
        entry['losses'] += 1
    elif net == 0:
        entry['pushes'] += 1
    else:
        entry['wins'] += 1
        entry['biggest_win'] = max(entry['biggest_win'], net)
    entry['net'] += net
    save_stats(stats)
    return entry


class BlackjackView(View):
    def __init__(self, cog, ctx, state):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.state = state

    async def interaction_check(self, interaction):
        if self.state.get('resolved'):
            await interaction.response.send_message("This hand is already finished.", ephemeral=True)
            return False
        if interaction.user.id != self.state['user'].id:
            await interaction.response.send_message("This isn't your hand.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction, button):
        state = self.state
        state['cards'].append(state['deck'].pop())
        total = hand_value(state['cards'])
        if total >= 21:
            await self.cog.settle(self.ctx, state)
        else:
            await interaction.response.edit_message(embed=self.cog.table_embed(state))
            return
        await interaction.response.edit_message(embed=state.get('embed'), view=None)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction, button):
        await self.cog.settle(self.ctx, self.state)
        await interaction.response.edit_message(embed=self.state.get('embed'), view=None)

    async def on_timeout(self):
        if not self.state.get('resolved'):
            try:
                await self.cog.settle(self.ctx, self.state)
                await self.ctx.channel.send(
                    f"⏰ {self.state['user'].mention} timed out — hand auto-stood."
                )
            except Exception:
                pass


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables = {}   # channel_id -> active hand state

    def table_embed(self, state, *, reveal=False):
        dealer = state['dealer']
        hole = dealer if reveal else [dealer[0], ('🂠', '')]
        color = discord.Color.green() if state.get('resolved') else discord.Color.blurple()
        embed = Embed(title=f"Blackjack — {state['user'].display_name}", color=color)
        embed.add_field(name="Dealer", value=fmt_cards(hole), inline=False)
        embed.add_field(
            name="Your Hand",
            value=f"{fmt_cards(state['cards'])} (**{hand_value(state['cards'])}**)",
            inline=False
        )
        embed.add_field(name="Bet", value=f"**{state['bet']:,}** chips", inline=True)
        return embed

    def new_deck(self):
        deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        return deck

    async def settle(self, ctx, state):
        if state.get('resolved'):
            return
        state['resolved'] = True
        self.tables.pop(ctx.channel.id, None)

        while hand_value(state['dealer']) < 17:
            state['dealer'].append(state['deck'].pop())

        player_total = hand_value(state['cards'])
        dealer_total = hand_value(state['dealer'])
        outcome = resolve_outcome(
            player_total, player_total == 21 and len(state['cards']) == 2,
            dealer_total, dealer_total == 21 and len(state['dealer']) == 2,
        )
        payout = payout_for(state['bet'], outcome)
        entry = bump_stats(ctx.guild.id, state['user'].id, payout, state['bet'])
        if payout:
            economy.add_chips(ctx.guild.id, state['user'].id, payout)

        labels = {
            'player_blackjack': '🃏 Blackjack! Paid 3:2',
            'dealer_blackjack': '💀 Dealer blackjack',
            'win': '✅ You win!',
            'dealer_bust': '🎉 Dealer busts — you win!',
            'push': '🤝 Push — bet returned',
            'bust': '💥 Bust!',
            'lose': '😔 Dealer wins',
        }
        net = payout - state['bet']
        embed = self.table_embed(state, reveal=True)
        embed.description = (
            f"{labels[outcome]} {'**+' if net > 0 else ''}{f'{net:,}' if net else '0'} chips\n"
            f"Dealer total: **{dealer_total}** | Your total: **{player_total}**\n"
            f"Balance: **{economy.get_balance(ctx.guild.id, state['user'].id):,}** chips "
            f"(net this session: {entry['net']:+,})"
        )
        state['embed'] = embed
        await ctx.send(embed=embed)

    @commands.command(name='blackjack',
                      help=f'Play blackjack against the dealer. Usage: !blackjack <amount> '
                           f'(min {MIN_BET}). Naturals pay 3:2.')
    async def blackjack(self, ctx, amount: int):
        if ctx.author.bot:
            return
        if amount < MIN_BET:
            await ctx.send(f"Minimum bet is **{MIN_BET}** chips.")
            return
        if amount > MAX_BET:
            await ctx.send(f"Maximum bet is **{MAX_BET:,}** chips.")
            return
        if ctx.channel.id in self.tables:
            await ctx.send("A hand is already running in this channel. Finish it first!")
            return
        if not economy.spend_chips(ctx.guild.id, ctx.author.id, amount):
            balance = economy.get_balance(ctx.guild.id, ctx.author.id)
            await ctx.send(f"You can't afford that bet. Balance: **{balance:,}** chips (`!daily` helps).")
            return

        deck = self.new_deck()
        state = {
            'user': ctx.author,
            'bet': amount,
            'deck': deck,
            'cards': [deck.pop(), deck.pop()],
            'dealer': [deck.pop(), deck.pop()],
            'resolved': False,
        }
        self.tables[ctx.channel.id] = state

        player_total = hand_value(state['cards'])
        if player_total == 21:
            await ctx.send(embed=self.table_embed(state))
            await self.settle(ctx, state)
            return

        view = BlackjackView(self, ctx, state)
        await ctx.send(embed=self.table_embed(state), view=view)

    @commands.command(name='bjtop', help='Blackjack leaderboard: biggest single wins and net profit.')
    async def bj_top(self, ctx):
        guild_stats = load_stats().get(str(ctx.guild.id), {})
        if not guild_stats:
            await ctx.send('No blackjack hands played yet. Try `!blackjack <amount>`!')
            return

        def member_name(user_id):
            member = ctx.guild.get_member(int(user_id))
            return member.display_name if member else f'User {user_id}'

        biggest = sorted(guild_stats.items(),
                         key=lambda kv: kv[1].get('biggest_win', 0), reverse=True)[:5]
        profitable = sorted(guild_stats.items(),
                            key=lambda kv: kv[1].get('net', 0), reverse=True)[:5]

        def fmt(rows, key):
            lines = []
            for i, (uid, s) in enumerate(rows, 1):
                if not s.get(key):
                    continue
                lines.append(f"`{i}.` **{member_name(uid)}** — {s[key]:+,} chips")
            return '\n'.join(lines) or '—'

        embed = Embed(title="🃏 Blackjack Leaderboard", color=0x9b59b6)
        embed.add_field(name="💰 Biggest Single Wins", value=fmt(biggest, 'biggest_win'), inline=False)
        embed.add_field(name="📈 Net Profit", value=fmt(profitable, 'net'), inline=False)
        await ctx.send(embed=embed)

    @blackjack.error
    @bj_top.error
    async def blackjack_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Usage: `!blackjack <amount>` (min {MIN_BET} chips).")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Bet must be a whole number of chips.")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send("Something went wrong resolving that hand — your chips are safe.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
