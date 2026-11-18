"""Shared helper functions for the cogs."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.helpers")


def level_for_xp(xp: int) -> int:
    """Level curve: level L is reached at 100 * L² XP (same formula as the website)."""
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
    """Sends an embed to the configured log channel (if any)."""
    try:
        row = await bot.db.fetchone("SELECT log_channel_id FROM guilds WHERE guild_id = %s", guild.id)
    except Exception:  # noqa: BLE001
        log.exception("Could not read log channel")
        return
    if not row or not row["log_channel_id"]:
        return
    channel = guild.get_channel(int(row["log_channel_id"]))
    if isinstance(channel, discord.abc.Messageable):
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            log.warning("Failed to send log message in %s: %s", guild.name, exc)


def can_moderate(actor: discord.Member, target: discord.Member) -> str | None:
    """Checks the role hierarchy. Returns an error message or None."""
    guild = target.guild
    if target == actor:
        return "You can't moderate yourself."
    if target == guild.owner:
        return "The server owner can't be moderated."
    if actor != guild.owner and target.top_role >= actor.top_role:
        return "This member has an equal or higher role than you."
    if target.top_role >= guild.me.top_role:
        return "My role isn't high enough to moderate this member."
    return None
