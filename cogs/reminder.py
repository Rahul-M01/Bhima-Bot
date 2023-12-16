import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import pytz  # You might need to install pytz: pip install pytz


class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []

    @commands.command(name='remindme')
    async def set_reminder(self, ctx, time, *, reminder):
        """Set a reminder. Time format: DD/MM/YYYY HH:MM TZ"""
        try:
            reminder_time = datetime.strptime(time, '%d/%m/%Y %H:%M')
            reminder_time = pytz.timezone('UTC').localize(reminder_time)  # Convert to UTC
            now = datetime.now(pytz.timezone('UTC'))

            if reminder_time <= now:
                await ctx.send("Please specify a time in the future.")
                return

            self.reminders.append((reminder_time, reminder, ctx.author.id))
            await ctx.send(f"Reminder set for {time}.")
        except ValueError:
            await ctx.send("Invalid time format. Use DD/MM/YYYY HH:MM TZ.")

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        now = datetime.now(pytz.timezone('UTC'))
        to_remove = []
        for reminder_time, reminder, user_id in self.reminders:
            if now >= reminder_time:
                user = await self.bot.fetch_user(user_id)
                await user.send(f"Reminder: {reminder}")
                to_remove.append((reminder_time, reminder, user_id))

        for item in to_remove:
            self.reminders.remove(item)

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_reminders.start()

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))
