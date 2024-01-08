import discord
from discord.ext import commands, tasks
import asyncio
import dateparser
from datetime import datetime
from datetime import timedelta
import json

class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []
        self.load_reminders()
        self.check_reminders.start()

    def save_reminders(self):
        with open('../logs/reminders.json', 'w') as f:
            json.dump(self.reminders, f, default=str)  # Convert to string for JSON serialization
        
    def load_reminders(self):
        try:
            with open('../logs/reminders.json', 'r') as f:
                self.reminders = json.load(f)
                # Convert string dates back to datetime objects
                self.reminders = [(user_id, dateparser.parse(reminder_time), message) for user_id, reminder_time, message in self.reminders]
        except FileNotFoundError:
            self.reminders = []

    @commands.command(name='remind', help='Set a reminder. Usage: !remind "in 1 hour" "message" or !remind "2023-01-01 12:00:00" "message"')
    async def set_reminder(self, ctx, time, *, message):
        # Attempt to parse the time
        reminder_time = dateparser.parse(time, settings={'TIMEZONE': 'UTC', 'TO_TIMEZONE': 'UTC', 'PREFER_DATES_FROM': 'future'})

        if reminder_time is None:
            await ctx.send("Invalid time format. Please try again.")
            return
        
        # Check if the time is too far in the past
        if reminder_time < datetime.utcnow():
            await ctx.send("The specified time is in the past. Please try again.")
            return

        # Check if the time is too far in the future (10 years as 3650 days)
        max_future_time = datetime.utcnow() + timedelta(days=365 * 10)  # 10 years in days
        if reminder_time > max_future_time:
            await ctx.send("The specified time is too far in the future. Please set a reminder within 10 years.")
            return

        # Store the reminder details
        self.reminders.append((ctx.author.id, reminder_time, message))
        await ctx.send(f"Reminder set for {reminder_time} UTC.")
        self.save_reminders()
        
    @tasks.loop(seconds=10)
    async def check_reminders(self):
        current_time = datetime.utcnow()
        reminders_to_remove = []

        for reminder in self.reminders:
            user_id, reminder_time, message = reminder
            if current_time >= reminder_time:
                user = await self.bot.fetch_user(user_id)
                await user.send(f"Reminder: {message}")
                reminders_to_remove.append(reminder)

        # Remove sent reminders and update the file
        for reminder in reminders_to_remove:
            self.reminders.remove(reminder)
        
        if reminders_to_remove:
            self.save_reminders()

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ReminderCog(bot))
