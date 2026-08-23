"""Bhima Bot application entry point."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tracemalloc

import discord
from discord.ext import commands
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
COGS_DIR = ROOT_DIR / "cogs"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bhima")


def discover_cogs(cogs_dir: Path = COGS_DIR) -> list[str]:
    """Return import paths for loadable cogs in deterministic order."""
    return [
        f"cogs.{path.stem}"
        for path in sorted(cogs_dir.glob("*.py"))
        if path.name != "__init__.py" and not path.name.startswith("_")
    ]


def require_token() -> str:
    """Load and validate the Discord token before starting the client."""
    load_dotenv(ROOT_DIR / ".env")
    token = os.getenv("TOKEN", "").strip()
    if not token:
        raise RuntimeError("TOKEN is missing. Copy .env.example to .env and add a Discord bot token.")
    return token


class BhimaBot(commands.Bot):
    """Discord client with reliable one-time extension loading."""

    async def setup_hook(self) -> None:
        failures: list[str] = []
        for extension in discover_cogs():
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension %s", extension)
            except Exception:
                failures.append(extension)
                logger.exception("Failed to load extension %s", extension)

        if failures:
            logger.warning("Started with %d unavailable extension(s): %s", len(failures), ", ".join(failures))
        else:
            logger.info("Loaded all %d extensions", len(self.extensions))

    async def on_ready(self) -> None:
        logger.info(
            "Connected as %s across %d guild(s)",
            self.user,
            len(self.guilds),
        )


def create_bot() -> BhimaBot:
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.members = True
    intents.message_content = True
    return BhimaBot(command_prefix="!", intents=intents, help_command=None)


def main() -> None:
    if os.getenv("BHIMA_TRACE_MEMORY") == "1":
        tracemalloc.start()
    create_bot().run(require_token(), log_handler=None)


if __name__ == "__main__":
    main()
