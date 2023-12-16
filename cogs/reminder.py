import discord
from discord.ext import commands, tasks
import asyncio
import dateparser
from datetime import datetime

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @commands.command(name='remind', help='Set a reminder. Usage: !remind "in 1 hour" "message" or !remind "2023-01-01 12:00:00" "message"')
    async def set_reminder(self, ctx, time, *, message):
        # Parse the time using dateparser
        reminder_time = dateparser.parse(time, settings={'TIMEZONE': 'UTC', 'TO_TIMEZONE': 'UTC'})
        if reminder_time is None:
            await ctx.send("Invalid time format. Please try again.")
            return

        # Store the reminder details
        self.reminders.append((ctx.author.id, reminder_time, message))
        await ctx.send(f"Reminder set for {reminder_time} UTC.")

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        current_time = datetime.utcnow()
        for reminder in self.reminders.copy():
            user_id, reminder_time, message = reminder
            if current_time >= reminder_time:
                user = await self.bot.fetch_user(user_id)
                await user.send(f"Reminder: {message}")
                self.reminders.remove(reminder)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))
