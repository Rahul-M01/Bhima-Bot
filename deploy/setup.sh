#!/bin/bash
# Run this on a fresh Ubuntu 22.04 Oracle Cloud instance
# Usage: bash setup.sh

set -e

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg git

# clone the repo
cd ~
git clone https://github.com/Rahul-M01/Bhima-Bot.git
cd Bhima-Bot

# set up venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# The moderation, reminder, and metals cogs currently store their persistent
# JSON files one directory above the repository.
mkdir -p /home/ubuntu/logs

# Prompt without echoing the bot token to the terminal or shell history.
read -rsp "Paste your bot token: " TOKEN
printf '\nTOKEN=%s\n' "$TOKEN" > .env
chmod 600 .env
unset TOKEN

echo ""
echo "Done! Now run:"
echo "  sudo cp deploy/bhima-bot.service /etc/systemd/system/"
echo "  sudo systemctl enable bhima-bot"
echo "  sudo systemctl start bhima-bot"
echo ""
echo "Check status with: sudo systemctl status bhima-bot"
echo "View logs with:    sudo journalctl -u bhima-bot -f"
