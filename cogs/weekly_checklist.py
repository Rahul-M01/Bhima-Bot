import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
from datetime import time
from zoneinfo import ZoneInfo
import json
import os

TASKS_FILE = "checklist_tasks.json"
STATE_FILE = "checklist_state.json"
LAST_MSG_FILE = "checklist_last_msg.json"
UK_TZ = ZoneInfo("Europe/London")
TARGET_GUILD = "startup"
TARGET_CHANNEL = "general"

DEFAULT_TASKS = [
    "Review weekly goals & priorities",
    "Team standup / sync",
    "Update project tracker / Notion",
    "Check emails & messages",
    "Review open pull requests / code",
    "Follow up on blockers",
    "Plan & prep for next week",
]


def load_tasks() -> list[str]:
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            return json.load(f)
    return DEFAULT_TASKS.copy()


def save_tasks(tasks: list[str]):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def load_all_states() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(message_id: int, state: dict):
    data = load_all_states()
    data[str(message_id)] = state
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


def save_last_msg(channel_id: int, message_id: int):
    with open(LAST_MSG_FILE, "w") as f:
        json.dump({str(channel_id): message_id}, f)


def load_last_msg(channel_id: int) -> int | None:
    if os.path.exists(LAST_MSG_FILE):
        with open(LAST_MSG_FILE) as f:
            data = json.load(f)
        return data.get(str(channel_id))
    return None


def build_embed(task_list: list[str], state: dict = None) -> discord.Embed:
    embed = discord.Embed(title="📋 Weekly Task Checklist", color=discord.Color.blurple())
    if not task_list:
        embed.description = "*No tasks yet — click ➕ Add Task to get started.*"
    else:
        lines = []
        for i, task in enumerate(task_list):
            done = (state or {}).get(str(i), False)
            icon = "🟢" if done else "🔘"
            lines.append(f"{icon} `{i+1}.` {task}")
        embed.description = "\n".join(lines)
    embed.set_footer(text="Press a number to toggle a task • 🟢 = done  🔘 = not done")
    return embed


class ToggleButton(Button):
    """Small numbered button that toggles a task on/off."""
    def __init__(self, index: int, completed: bool):
        super().__init__(
            style=discord.ButtonStyle.success if completed else discord.ButtonStyle.secondary,
            label=str(index + 1),
            custom_id=f"checklist_task_{index}",
            row=index // 5,
        )
        self.task_index = index
        self.completed = completed

    async def callback(self, interaction: discord.Interaction):
        self.completed = not self.completed
        self.style = discord.ButtonStyle.success if self.completed else discord.ButtonStyle.secondary

        state = {
            str(item.task_index): item.completed
            for item in self.view.children
            if isinstance(item, ToggleButton)
        }
        save_state(interaction.message.id, state)

        task_list = load_tasks()
        embed = build_embed(task_list, state)
        await interaction.response.edit_message(embed=embed, view=self.view)


class AddTaskModal(Modal, title="Add a Task"):
    task_input = TextInput(label="Task name", placeholder="e.g. Send weekly report", max_length=80)

    def __init__(self, checklist_message: discord.Message):
        super().__init__()
        self.checklist_message = checklist_message

    async def on_submit(self, interaction: discord.Interaction):
        task_list = load_tasks()
        if len(task_list) >= 20:
            await interaction.response.send_message("Maximum 20 tasks reached.", ephemeral=True)
            return
        task_list.append(self.task_input.value)
        save_tasks(task_list)
        new_view = ChecklistView(task_list=task_list)
        embed = build_embed(task_list)
        await self.checklist_message.edit(embed=embed, view=new_view)
        await interaction.response.send_message(f"Added: **{self.task_input.value}**", ephemeral=True)


class RemoveTaskSelect(Select):
    def __init__(self, task_list: list[str], checklist_message: discord.Message):
        self.checklist_message = checklist_message
        options = [
            discord.SelectOption(label=f"{i+1}. {task[:90]}", value=str(i))
            for i, task in enumerate(task_list)
        ]
        super().__init__(placeholder="Choose a task to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        task_list = load_tasks()
        index = int(self.values[0])
        removed = task_list.pop(index)
        save_tasks(task_list)
        new_view = ChecklistView(task_list=task_list)
        embed = build_embed(task_list)
        await self.checklist_message.edit(embed=embed, view=new_view)
        await interaction.response.edit_message(content=f"Removed: **{removed}**", view=None)


class RemoveTaskView(View):
    def __init__(self, task_list: list[str], checklist_message: discord.Message):
        super().__init__(timeout=30)
        self.add_item(RemoveTaskSelect(task_list, checklist_message))


class AddTaskButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="➕ Add Task", custom_id="checklist_add", row=4)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return
        await interaction.response.send_modal(AddTaskModal(interaction.message))


class RemoveTaskButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="🗑️ Remove Task", custom_id="checklist_remove", row=4)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return
        task_list = load_tasks()
        if not task_list:
            await interaction.response.send_message("No tasks to remove.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select a task to remove:", view=RemoveTaskView(task_list, interaction.message), ephemeral=True
        )


class ChecklistView(View):
    def __init__(self, task_list: list[str] = None, state: dict = None):
        super().__init__(timeout=None)
        tasks = task_list if task_list is not None else load_tasks()
        for i, _ in enumerate(tasks[:20]):
            completed = (state or {}).get(str(i), False)
            self.add_item(ToggleButton(i, completed))
        self.add_item(AddTaskButton())
        self.add_item(RemoveTaskButton())


class WeeklyChecklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_checklist.start()

    def cog_unload(self):
        self.daily_checklist.cancel()

    async def post_checklist(self, channel: discord.TextChannel):
        # Delete previous checklist message if it exists
        last_id = load_last_msg(channel.id)
        if last_id:
            try:
                old_msg = await channel.fetch_message(last_id)
                await old_msg.delete()
            except discord.NotFound:
                pass

        task_list = load_tasks()
        state = {str(i): False for i in range(len(task_list))}
        view = ChecklistView(task_list=task_list, state=state)
        embed = build_embed(task_list, state)
        msg = await channel.send(
            "@everyone",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        save_state(msg.id, state)
        save_last_msg(channel.id, msg.id)

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

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ChecklistView())

    @commands.command(name="checklist", help="Manually post the checklist now (admin only)")
    @commands.has_permissions(administrator=True)
    async def checklist_cmd(self, ctx: commands.Context):
        await ctx.message.delete()
        await self.post_checklist(ctx.channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyChecklistCog(bot))
