import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
from discord import Embed

CHOICES = ("rock", "paper", "scissors")
EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

def decide_winner(p1_choice: str, p2_choice: str) -> int:
    """
    Returns:
      0 = tie
      1 = player1 wins
      2 = player2 wins
    """
    if p1_choice == p2_choice:
        return 0
    wins_against = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    return 1 if wins_against[p1_choice] == p2_choice else 2


class RPSGame:
    def __init__(self):
        self.in_game = False
        self.channel = None
        self.p1 = None
        self.p2 = None
        self.choices = {}  # {user_id: "rock"/"paper"/"scissors"}
        self.lock = asyncio.Lock()

    def reset(self):
        self.in_game = False
        self.channel = None
        self.p1 = None
        self.p2 = None
        self.choices = {}

    async def start_challenge(self, ctx: commands.Context, opponent: discord.Member) -> str:
        async with self.lock:
            if self.in_game:
                return "A game is already in progress. Please wait for it to finish."

            if opponent.bot:
                return "You can’t challenge a bot."

            if opponent.id == ctx.author.id:
                return "You can’t challenge yourself."

            self.in_game = True
            self.channel = ctx.channel
            self.p1 = ctx.author
            self.p2 = opponent
            self.choices = {}

            return f"{opponent.mention}, you’ve been challenged to Rock Paper Scissors by {ctx.author.mention}!"

    async def accept(self) -> str:
        async with self.lock:
            if not self.in_game:
                return "No active challenge."
            return f"Challenge accepted! I’ll DM both players to pick their move."

    async def set_choice(self, user: discord.User, choice: str):
        async with self.lock:
            self.choices[user.id] = choice

    async def both_chosen(self) -> bool:
        async with self.lock:
            return self.p1 and self.p2 and (self.p1.id in self.choices) and (self.p2.id in self.choices)

    async def reveal_result(self) -> Embed:
        # assumes both chosen
        p1_choice = self.choices[self.p1.id]
        p2_choice = self.choices[self.p2.id]

        outcome = decide_winner(p1_choice, p2_choice)

        desc = (
            f"{self.p1.mention} chose {EMOJI[p1_choice]} **{p1_choice}**\n"
            f"{self.p2.mention} chose {EMOJI[p2_choice]} **{p2_choice}**\n\n"
        )

        if outcome == 0:
            desc += "🤝 It’s a **tie**!"
            color = discord.Color.gold()
        elif outcome == 1:
            desc += f"🏆 **{self.p1.display_name} wins!**"
            color = discord.Color.green()
        else:
            desc += f"🏆 **{self.p2.display_name} wins!**"
            color = discord.Color.green()

        embed = Embed(title="Rock Paper Scissors", description=desc, color=color)
        return embed


class AcceptDeclineView(View):
    def __init__(self, cog, challenger_id: int, opponent_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id

    async def on_timeout(self):
        # If still in game and no one accepted, reset.
        game = self.cog.game
        if game.in_game and game.p1 and game.p2 and game.p2.id == self.opponent_id:
            await self.cog.safe_send(game.channel, "⏰ Challenge timed out (no response).")
            game.reset()

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            return await interaction.response.send_message("Only the challenged player can accept.", ephemeral=True)

        msg = await self.cog.game.accept()
        await interaction.response.edit_message(content=msg, view=None)

        # DM both players to pick
        await self.cog.dm_choice_prompt(self.cog.game.p1)
        await self.cog.dm_choice_prompt(self.cog.game.p2)

        # Start a background wait (not “async later”; it runs in this event loop)
        self.cog.bot.loop.create_task(self.cog.wait_and_finish())

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            return await interaction.response.send_message("Only the challenged player can decline.", ephemeral=True)

        await interaction.response.edit_message(content="Challenge declined.", view=None)
        self.cog.game.reset()


class ChoiceView(View):
    def __init__(self, cog, player_id: int, timeout: float = 45.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.player_id = player_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This isn’t your selection.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # If player didn't choose in time, we just leave it; the main wait task will handle it.
        pass

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.blurple)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.record_choice(interaction, "rock")

    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.blurple)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.record_choice(interaction, "paper")

    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.blurple)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.record_choice(interaction, "scissors")


class RPS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = RPSGame()

    async def safe_send(self, channel, content=None, embed=None, view=None):
        try:
            if channel:
                return await channel.send(content=content, embed=embed, view=view)
        except Exception as e:
            print("Send failed:", e)

    async def dm_choice_prompt(self, user: discord.User):
        try:
            embed = Embed(
                title="Pick your move",
                description="Choose **Rock**, **Paper**, or **Scissors**.\n(Your choice is private.)",
                color=discord.Color.blue(),
            )
            view = ChoiceView(self, user.id)
            await user.send(embed=embed, view=view)
        except discord.Forbidden:
            # If DMs are blocked, cancel the game (otherwise it's unfair)
            await self.safe_send(self.game.channel, f"❌ {user.mention} has DMs disabled. Game cancelled.")
            self.game.reset()

    async def record_choice(self, interaction: discord.Interaction, choice: str):
        # Store choice and acknowledge in DM
        await self.game.set_choice(interaction.user, choice)
        await interaction.response.edit_message(
            embed=Embed(
                title="Choice locked in ✅",
                description=f"You chose {EMOJI[choice]} **{choice}**.",
                color=discord.Color.green(),
            ),
            view=None
        )

        # If both chosen, finish immediately
        if await self.game.both_chosen():
            await self.finish_game()

    async def wait_and_finish(self):
        # Wait up to 45 seconds for both players
        for _ in range(45):
            if not self.game.in_game:
                return
            if await self.game.both_chosen():
                return
            await asyncio.sleep(1)

        # Timeout: someone didn't pick
        if self.game.in_game:
            p1_picked = self.game.p1 and self.game.p1.id in self.game.choices
            p2_picked = self.game.p2 and self.game.p2.id in self.game.choices

            if p1_picked and not p2_picked:
                await self.safe_send(self.game.channel, f"⏰ {self.game.p2.mention} didn’t choose in time. **{self.game.p1.mention} wins by default.**")
            elif p2_picked and not p1_picked:
                await self.safe_send(self.game.channel, f"⏰ {self.game.p1.mention} didn’t choose in time. **{self.game.p2.mention} wins by default.**")
            else:
                await self.safe_send(self.game.channel, "⏰ No one chose in time. Game cancelled.")

            self.game.reset()

    async def finish_game(self):
        embed = await self.game.reveal_result()
        await self.safe_send(self.game.channel, embed=embed)
        self.game.reset()

    @commands.command()
    async def rps(self, ctx, opponent: discord.Member):
        msg = await self.game.start_challenge(ctx, opponent)
        if not self.game.in_game:
            return await ctx.send(msg)

        embed = Embed(title="Rock Paper Scissors", description=msg, color=discord.Color.purple())
        view = AcceptDeclineView(self, ctx.author.id, opponent.id, timeout=30.0)
        await ctx.send(embed=embed, view=view)

    @commands.command()
    async def rps_cancel(self, ctx):
        if not self.game.in_game:
            return await ctx.send("No active game.")
        if ctx.author.id not in (self.game.p1.id, self.game.p2.id):
            return await ctx.send("Only the players in the current game can cancel.")
        self.game.reset()
        await ctx.send("Game cancelled.")

async def setup(bot):
    await bot.add_cog(RPS(bot))
