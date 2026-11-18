"""Einstiegspunkt des Discord-Bots (pelican-discord-stack)."""
from __future__ import annotations

import logging
import os
import re
import sys
import warnings

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database

load_dotenv()

logging.basicConfig(
    level=(os.getenv("LOG_LEVEL") or "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("discord.http").setLevel(logging.WARNING)
# MariaDB meldet bei CREATE TABLE IF NOT EXISTS eine Note – das ist erwartet.
warnings.filterwarnings("ignore", message=r"Table '.*' already exists")
# Der Bot nutzt kein Voice – die Hinweise auf fehlende Voice-Pakete ausblenden.
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
        intents.members = True  # privilegiert: im Developer Portal aktivieren
        intents.message_content = True  # privilegiert: für Prefix-Commands & XP

        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv("BOT_PREFIX") or "!"),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.db = Database.from_env()
        self.started_at = discord.utils.utcnow()

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.db.init_schema()

        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Erweiterung geladen: %s", ext)

        dev_guild = (os.getenv("DEV_GUILD_ID") or "").strip()
        if dev_guild and not re.fullmatch(r"\d{17,20}", dev_guild):
            log.warning(
                "DEV_GUILD_ID '%s' ist keine gültige Server-ID (17–20 Ziffern) – "
                "synchronisiere Slash-Commands stattdessen global.",
                dev_guild,
            )
            dev_guild = ""
        if dev_guild:
            guild = discord.Object(id=int(dev_guild))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("%d Slash-Commands auf Test-Server %s synchronisiert", len(synced), dev_guild)
        else:
            synced = await self.tree.sync()
            log.info("%d Slash-Commands global synchronisiert (kann bis zu 1h dauern)", len(synced))

    async def close(self) -> None:
        log.info("Bot wird beendet ...")
        await super().close()
        await self.db.close()


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.critical("DISCORD_TOKEN ist nicht gesetzt – bitte in den Pelican-Variablen eintragen.")
        sys.exit(1)

    bot = PelicanBot()
    if not bot.db.configured:
        log.critical("Datenbank nicht konfiguriert – bitte DB_DATABASE, DB_USERNAME und DB_PASSWORD setzen.")
        sys.exit(1)

    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        log.critical("Login fehlgeschlagen – der Discord-Token ist ungültig.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.critical(
            "Privilegierte Intents fehlen – aktiviere 'Server Members Intent' und "
            "'Message Content Intent' im Discord Developer Portal."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
