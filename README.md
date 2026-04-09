# Bhima Bot

A general-purpose Discord bot built with discord.py. Handles moderation, music, games, polls, reminders, and a few other things.

**Prefix:** `!`

## Setup

**Requirements:** Python 3.10+, [FFmpeg](https://ffmpeg.org/download.html) in PATH (for music)

```bash
git clone https://github.com/Rahul-M01/Bhima-Bot.git
cd Bhima-Bot

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your bot token:
```
TOKEN=your_bot_token_here
```

Then run:
```bash
python main.py
```

To get a bot token, go to the [Discord Developer Portal](https://discord.com/developers/applications), create an application, add a bot, and copy the token. Make sure to enable the **Message Content Intent** under the bot settings.

---

## Commands

### Moderation

| Command | Permission | Description |
|---|---|---|
| `!kick @user [reason]` | Kick Members | Kick a member |
| `!ban @user [reason]` | Ban Members | Ban a member |
| `!unban username#0000` | Ban Members | Unban by username |
| `!mute @user <minutes> [reason]` | Moderate Members | Timeout a member (up to 28 days) |
| `!unmute @user` | Moderate Members | Remove timeout |
| `!warn @user <reason>` | Manage Messages | Warn a member (saved across restarts) |
| `!warnings @user` | Manage Messages | View warnings for a member |
| `!clearwarnings @user` | Administrator | Clear all warnings |
| `!purge <amount> [@user]` | Manage Messages | Bulk delete up to 100 messages |
| `!slowmode <seconds>` | Manage Channels | Set slowmode (0 to disable) |

### Music

| Command | Description |
|---|---|
| `!play <url or search>` | Play a track, or add to queue if something's already playing |
| `!pause` / `!resume` | Pause or resume |
| `!skip` | Skip the current track |
| `!stop` | Stop and disconnect |
| `!queue` | Show the queue |
| `!nowplaying` | Show current track |
| `!volume <0-100>` | Set volume |
| `!loop track\|queue\|off` | Toggle looping |
| `!remove <position>` | Remove a track from the queue |
| `!clearqueue` | Clear the queue without stopping |
| `!join` / `!leave` | Join or leave voice |

The now-playing embed includes ⏸️ ⏭️ ⏹️ buttons for quick control.

### Games

| Command | Description |
|---|---|
| `!blackjack` | Start a blackjack game (multiplayer, uses buttons) |
| `!join_blackjack` | Join an active blackjack game |
| `!startpoker` | Start a Texas Hold'em game (30s join window) |
| `!joinpoker` | Join a poker lobby before it starts |
| `!endpoker` | Force-end a poker game (requires Manage Messages) |
| `!rps @user` | Challenge someone to rock paper scissors |
| `!rps_cancel` | Cancel an ongoing RPS game |

Poker deals hole cards via DM and runs full betting rounds (fold/check/bet) through flop, turn, and river.

### Metals

| Command | Description |
|---|---|
| `!metals` | Show current gold and silver prices |
| `!setmetals #channel` | Set a channel for scheduled metals reports |
| `!unsetmetals` | Stop metals reports in this server |

### Recipes

| Command | Description |
|---|---|
| `!recipes` | List all saved recipes |
| `!recipe <search>` | Search for a recipe |
| `!ask <question>` | Ask a cooking question based on your saved recipes |

### Utility

| Command | Description |
|---|---|
| `!poll "question" "opt1" "opt2" ...` | Create a 60-second reaction poll (up to 10 options) |
| `!remind "in 2 hours" <message>` | Set a reminder — bot DMs you when it fires |
| `!translate <text>` | Translate text to English |
| `!deleted` | Show recently deleted messages (requires Manage Messages) |
| `!edited` | Show recently edited messages (requires Manage Messages) |
| `!help` | List all commands |

The bot also posts a welcome message in `#welcome` when someone joins the server.

---

## Project structure

```
cogs/
  blackjack.py        - Blackjack game
  deleted_messages.py  - Snipe deleted/edited messages
  help.py             - Custom help command
  metals.py           - Gold/silver price tracker with scheduled reports
  moderation.py       - Kick, ban, mute, warn, purge, slowmode
  music.py            - YouTube music player
  owner.py            - Bot owner utilities (reload, etc.)
  poker.py            - Texas Hold'em
  poll.py             - Timed polls
  recipe.py           - Recipe search and cooking Q&A
  reminder.py         - Persistent reminders
  rps.py              - Rock paper scissors
  translate.py        - Translation
  welcome.py          - Welcome messages
logs/                 - Persistent data (warnings, reminders) — gitignored
main.py               - Bot entry point
```
