"""Gemeinsame Hilfsfunktionen für die Cogs."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.helpers")


def level_for_xp(xp: int) -> int:
    """Level-Kurve: Level L wird bei 100 * L² XP erreicht."""
    return int(math.sqrt(max(xp, 0) / 100))


def xp_for_level(level: int) -> int:
    return 100 * level * level


def progress_bar(current: int, total: int, length: int = 12) -> str:
    filled = 0 if total <= 0 else round(length * min(current / total, 1))
    return "▰" * filled + "▱" * (length - filled)


async def upsert_guild(bot: "PelicanBot", guild: discord.Guild) -> None:
    await bot.db.execute(
        """
        INSERT INTO guilds (guild_id, name, icon_url, member_count, active)
        VALUES (%s, %s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE name = VALUES(name), icon_url = VALUES(icon_url),
                                member_count = VALUES(member_count), active = 1
        """,
        guild.id,
        guild.name[:100],
        guild.icon.url if guild.icon else None,
        guild.member_count or 0,
    )


async def send_log(bot: "PelicanBot", guild: discord.Guild, embed: discord.Embed) -> None:
    """Sendet ein Embed in den konfigurierten Log-Kanal (falls gesetzt)."""
    try:
        row = await bot.db.fetchone("SELECT log_channel_id FROM guilds WHERE guild_id = %s", guild.id)
    except Exception:  # noqa: BLE001
        log.exception("Log-Kanal konnte nicht gelesen werden")
        return
    if not row or not row["log_channel_id"]:
        return
    channel = guild.get_channel(int(row["log_channel_id"]))
    if isinstance(channel, discord.abc.Messageable):
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            log.warning("Log-Nachricht in %s fehlgeschlagen: %s", guild.name, exc)


def can_moderate(actor: discord.Member, target: discord.Member) -> str | None:
    """Prüft die Rollen-Hierarchie. Gibt eine Fehlermeldung zurück oder None."""
    guild = target.guild
    if target == actor:
        return "Du kannst dich nicht selbst moderieren."
    if target == guild.owner:
        return "Der Server-Owner kann nicht moderiert werden."
    if actor != guild.owner and target.top_role >= actor.top_role:
        return "Dieses Mitglied hat eine gleich hohe oder höhere Rolle als du."
    if target.top_role >= guild.me.top_role:
        return "Meine Rolle ist nicht hoch genug, um dieses Mitglied zu moderieren."
    return None
