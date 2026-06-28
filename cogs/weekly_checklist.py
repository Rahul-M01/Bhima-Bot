import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import time
from zoneinfo import ZoneInfo
import json
import os

TASKS_FILE = "checklist_tasks.json"
STATE_FILE = "checklist_state.json"
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
    def __init__(self, task_list: list[str] = None, state: dict = None):
        super().__init__(timeout=None)
        for i, task in enumerate(task_list or load_tasks()):
            completed = (state or {}).get(str(i), False)
            self.add_item(TaskButton(task, i, completed))


class WeeklyChecklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_checklist.start()

    def cog_unload(self):
        self.daily_checklist.cancel()

    async def post_checklist(self, channel: discord.TextChannel):
        task_list = load_tasks()
        view = ChecklistView(task_list=task_list)
        msg = await channel.send(
            "@everyone\n## 📋 Weekly Task Checklist\nClick a button to mark a task as complete!",
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        save_state(msg.id, {str(i): False for i in range(len(task_list))})

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

    # --- Task management commands (admin only) ---

    @commands.command(name="tasks", help="Show current tasks or use '!tasks help' for commands")
    @commands.has_permissions(administrator=True)
    async def list_tasks(self, ctx: commands.Context, subcommand: str = None):
        if subcommand and subcommand.lower() == "help":
            embed = discord.Embed(title="📋 Checklist Commands", color=discord.Color.blurple())
            embed.add_field(name="!tasks", value="Show all current checklist tasks with their numbers", inline=False)
            embed.add_field(name="!addtask <text>", value="Add a new task\n*Example: `!addtask Review finances`*", inline=False)
            embed.add_field(name="!removetask <number>", value="Remove a task by its number\n*Example: `!removetask 3`*", inline=False)
            embed.add_field(name="!edittask <number> <text>", value="Rename an existing task\n*Example: `!edittask 2 Weekly team sync`*", inline=False)
            embed.add_field(name="!cleartasks", value="Delete all tasks from the checklist", inline=False)
            embed.add_field(name="!checklist", value="Post the checklist immediately (for testing)", inline=False)
            embed.set_footer(text="The checklist auto-posts every day at 12pm UK time in #general")
            await ctx.send(embed=embed)
            return

        task_list = load_tasks()
        if not task_list:
            await ctx.send("No tasks set. Use `!addtask <task>` to add one, or `!tasks help` for all commands.")
            return
        lines = "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(task_list))
        await ctx.send(f"**Current checklist tasks:**\n{lines}\n\n*Use `!tasks help` to see how to edit these.*")

    @commands.command(name="addtask", help="Add a task to the checklist. Usage: !addtask <task text>")
    @commands.has_permissions(administrator=True)
    async def add_task(self, ctx: commands.Context, *, task: str):
        task_list = load_tasks()
        if len(task_list) >= 25:
            await ctx.send("Maximum 25 tasks allowed (Discord button limit).")
            return
        task_list.append(task)
        save_tasks(task_list)
        await ctx.send(f"Added task `{len(task_list)}.` **{task}**")

    @commands.command(name="removetask", help="Remove a task by number. Usage: !removetask <number>")
    @commands.has_permissions(administrator=True)
    async def remove_task(self, ctx: commands.Context, number: int):
        task_list = load_tasks()
        if number < 1 or number > len(task_list):
            await ctx.send(f"Invalid number. Pick between 1 and {len(task_list)}.")
            return
        removed = task_list.pop(number - 1)
        save_tasks(task_list)
        await ctx.send(f"Removed task: **{removed}**")

    @commands.command(name="edittask", help="Edit a task by number. Usage: !edittask <number> <new text>")
    @commands.has_permissions(administrator=True)
    async def edit_task(self, ctx: commands.Context, number: int, *, new_text: str):
        task_list = load_tasks()
        if number < 1 or number > len(task_list):
            await ctx.send(f"Invalid number. Pick between 1 and {len(task_list)}.")
            return
        old = task_list[number - 1]
        task_list[number - 1] = new_text
        save_tasks(task_list)
        await ctx.send(f"Updated task `{number}`:\n~~{old}~~ → **{new_text}**")

    @commands.command(name="cleartasks", help="Remove all checklist tasks")
    @commands.has_permissions(administrator=True)
    async def clear_tasks(self, ctx: commands.Context):
        save_tasks([])
        await ctx.send("All tasks cleared.")

    @commands.command(name="checklist", help="Manually post the checklist now")
    @commands.has_permissions(administrator=True)
    async def checklist_cmd(self, ctx: commands.Context):
        await self.post_checklist(ctx.channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyChecklistCog(bot))
