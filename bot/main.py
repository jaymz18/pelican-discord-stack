"""Entry point of the Discord bot (pelican-discord-stack)."""
from __future__ import annotations

import logging
import os
import re
import sys
import warnings

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.command_registry import publish_commands
from utils.database import Database

load_dotenv()

logging.basicConfig(
    level=(os.getenv("LOG_LEVEL") or "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("discord.http").setLevel(logging.WARNING)
# MariaDB emits notes for idempotent schema statements (IF NOT EXISTS) – that's expected.
warnings.filterwarnings("ignore", message=r"Table '.*' already exists")
warnings.filterwarnings("ignore", message=r"Duplicate column name")
# The bot doesn't play audio – hide the hints about missing voice packages.
logging.getLogger("discord.client").addFilter(lambda r: "voice will NOT be supported" not in r.getMessage())
log = logging.getLogger("bot")

EXTENSIONS = (
    "cogs.events",
    "cogs.general",
    "cogs.levels",
    "cogs.moderation",
    "cogs.fun",
    "cogs.settings",
)


class PelicanBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True  # privileged: enable in the Developer Portal
        intents.message_content = True  # privileged: needed for prefix commands & XP
        intents.voice_states = True  # voice XP

        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv("BOT_PREFIX") or "!"),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.db = Database.from_env()
        self.started_at = discord.utils.utcnow()
        self.levels = None  # set by the Levels cog (utils.leveling.LevelManager)

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.db.init_schema()

        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Loaded extension: %s", ext)

        await publish_commands(self)

        dev_guild = (os.getenv("DEV_GUILD_ID") or "").strip()
        if dev_guild and not re.fullmatch(r"\d{17,20}", dev_guild):
            log.warning(
                "DEV_GUILD_ID '%s' is not a valid server ID (17–20 digits) – "
                "syncing slash commands globally instead.",
                dev_guild,
            )
            dev_guild = ""
        if dev_guild:
            guild = discord.Object(id=int(dev_guild))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d slash commands to test server %s", len(synced), dev_guild)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d slash commands globally (may take up to 1 hour to appear)", len(synced))

    async def close(self) -> None:
        log.info("Shutting down ...")
        await super().close()
        await self.db.close()


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.critical("DISCORD_TOKEN is not set – please enter it in the Pelican startup variables.")
        sys.exit(1)

    bot = PelicanBot()
    if not bot.db.configured:
        log.critical("Database not configured – please set DB_DATABASE, DB_USERNAME and DB_PASSWORD.")
        sys.exit(1)

    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        log.critical("Login failed – the Discord token is invalid.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.critical(
            "Privileged intents missing – enable 'Server Members Intent' and "
            "'Message Content Intent' in the Discord Developer Portal."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
