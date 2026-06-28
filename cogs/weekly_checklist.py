import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import time
from zoneinfo import ZoneInfo
import json
import os

# Edit these tasks to whatever you want on the checklist
WEEKLY_TASKS = [
    "Review weekly goals & priorities",
    "Team standup / sync",
    "Update project tracker / Notion",
    "Check emails & messages",
    "Review open pull requests / code",
    "Follow up on blockers",
    "Plan & prep for next week",
]

STATE_FILE = "checklist_state.json"
UK_TZ = ZoneInfo("Europe/London")
TARGET_GUILD = "startup"
TARGET_CHANNEL = "general"


def load_all_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(message_id: int, state: dict):
    data = load_all_states()
    data[str(message_id)] = state
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


class TaskButton(Button):
    def __init__(self, label: str, index: int, completed: bool = False):
        super().__init__(
            style=discord.ButtonStyle.success if completed else discord.ButtonStyle.secondary,
            label=f"✅ {label}" if completed else f"⬜ {label}",
            custom_id=f"checklist_task_{index}",
            row=index // 3,
        )
        self.task_label = label
        self.task_index = index
        self.completed = completed

    async def callback(self, interaction: discord.Interaction):
        self.completed = not self.completed
        self.style = discord.ButtonStyle.success if self.completed else discord.ButtonStyle.secondary
        self.label = f"✅ {self.task_label}" if self.completed else f"⬜ {self.task_label}"

        state = {str(i): btn.completed for i, btn in enumerate(self.view.children)}
        save_state(interaction.message.id, state)

        await interaction.response.edit_message(view=self.view)


class ChecklistView(View):
    def __init__(self, state: dict = None):
        super().__init__(timeout=None)
        for i, task in enumerate(WEEKLY_TASKS):
            completed = (state or {}).get(str(i), False)
            self.add_item(TaskButton(task, i, completed))


class WeeklyChecklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_checklist.start()

    def cog_unload(self):
        self.daily_checklist.cancel()

    async def post_checklist(self, channel: discord.TextChannel):
        view = ChecklistView()
        msg = await channel.send(
            "@everyone\n## 📋 Weekly Task Checklist\nClick a button to mark a task as complete!",
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        save_state(msg.id, {str(i): False for i in range(len(WEEKLY_TASKS))})

    @tasks.loop(time=time(12, 0, tzinfo=UK_TZ))
    async def daily_checklist(self):
        for guild in self.bot.guilds:
            if guild.name.lower() == TARGET_GUILD.lower():
                channel = discord.utils.get(guild.text_channels, name=TARGET_CHANNEL)
                if channel:
                    await self.post_checklist(channel)
                return

    @daily_checklist.before_loop
    async def before_daily_checklist(self):
        await self.bot.wait_until_ready()

    @commands.command(name="checklist", help="Manually post the weekly checklist (admin only)")
    @commands.has_permissions(administrator=True)
    async def checklist_cmd(self, ctx: commands.Context):
        await self.post_checklist(ctx.channel)

    @commands.Cog.listener()
    async def on_ready(self):
        # Re-register persistent views so buttons still work after restart
        self.bot.add_view(ChecklistView())


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyChecklistCog(bot))
