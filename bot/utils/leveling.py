"""Shared leveling logic: XP changes, level-ups, role rewards and announcements."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

from utils.helpers import level_for_xp

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.leveling")

DEFAULT_LEVELUP_MESSAGE = "🎉 {user} just reached **level {level}**!"
SETTINGS_TTL = 120  # seconds

# Whitelist of columns that /levelconfig may change
SETTING_COLUMNS = {"announce", "announce_channel_id", "levelup_message", "xp_multiplier", "voice_xp"}


@dataclass
class LevelSettings:
    announce: bool = True
    announce_channel_id: int | None = None
    levelup_message: str | None = None
    xp_multiplier: float = 1.0
    voice_xp: bool = True
    ignored_channels: frozenset[int] = field(default_factory=frozenset)


@dataclass
class XPResult:
    xp: int
    old_level: int
    new_level: int

    @property
    def leveled_up(self) -> bool:
        return self.new_level > self.old_level


class LevelManager:
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot
        self._cache: dict[int, tuple[float, LevelSettings]] = {}

    # ------------------------------------------------------------------ settings

    async def settings(self, guild_id: int) -> LevelSettings:
        cached = self._cache.get(guild_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        row = await self.bot.db.fetchone("SELECT * FROM level_settings WHERE guild_id = %s", guild_id)
        ignored = await self.bot.db.fetchall(
            "SELECT channel_id FROM level_ignored_channels WHERE guild_id = %s", guild_id
        )
        settings = LevelSettings(ignored_channels=frozenset(int(r["channel_id"]) for r in ignored))
        if row:
            settings.announce = bool(row["announce"])
            settings.announce_channel_id = int(row["announce_channel_id"]) if row["announce_channel_id"] else None
            settings.levelup_message = row["levelup_message"]
            settings.xp_multiplier = float(row["xp_multiplier"])
            settings.voice_xp = bool(row["voice_xp"])

        self._cache[guild_id] = (time.monotonic() + SETTINGS_TTL, settings)
        return settings

    async def update_setting(self, guild_id: int, column: str, value: object) -> None:
        if column not in SETTING_COLUMNS:
            raise ValueError(f"Unknown setting: {column}")
        await self.bot.db.execute(
            f"INSERT INTO level_settings (guild_id, {column}) VALUES (%s, %s) "
            f"ON DUPLICATE KEY UPDATE {column} = VALUES({column})",
            guild_id,
            value,
        )
        self._cache.pop(guild_id, None)

    def invalidate(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)

    # ------------------------------------------------------------------ XP

    async def change_xp(
        self,
        member: discord.Member,
        *,
        delta: int = 0,
        set_to: int | None = None,
        count_message: bool = False,
        voice_minutes: int = 0,
        channel: discord.abc.Messageable | None = None,
    ) -> XPResult | None:
        """Adds/removes (delta) or sets (set_to) XP. Handles level-ups, rewards and announcements.

        Returns None when the XP did not change (e.g. a message on cooldown).
        """
        db = self.bot.db
        gained = 1 if (set_to is None and delta > 0) else 0
        if set_to is not None:
            xp_expr, xp_param, initial_xp = "%s", max(set_to, 0), max(set_to, 0)
        else:
            xp_expr, xp_param, initial_xp = "GREATEST(0, CAST(xp AS SIGNED) + %s)", delta, max(delta, 0)

        changes_xp = set_to is not None or delta != 0
        old_level = 0
        if changes_xp:
            before = await db.fetchone(
                "SELECT level FROM levels WHERE guild_id = %s AND user_id = %s", member.guild.id, member.id
            )
            old_level = int(before["level"]) if before else 0

        await db.execute(
            f"""
            INSERT INTO levels (guild_id, user_id, username, avatar_url, xp, level, messages, voice_minutes, last_xp_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, IF(%s = 1, UTC_TIMESTAMP(), NULL))
            ON DUPLICATE KEY UPDATE
                username = VALUES(username), avatar_url = VALUES(avatar_url),
                xp = {xp_expr},
                messages = messages + VALUES(messages),
                voice_minutes = voice_minutes + VALUES(voice_minutes),
                last_xp_at = IF(%s = 1, UTC_TIMESTAMP(), last_xp_at)
            """,
            member.guild.id,
            member.id,
            str(member)[:100],
            member.display_avatar.url,
            initial_xp,
            1 if count_message else 0,
            voice_minutes,
            gained,
            xp_param,
            gained,
        )

        if not changes_xp:
            return None

        row = await db.fetchone(
            "SELECT xp FROM levels WHERE guild_id = %s AND user_id = %s", member.guild.id, member.id
        )
        xp = int(row["xp"])
        new_level = level_for_xp(xp)
        if new_level != old_level:
            await db.execute(
                "UPDATE levels SET level = %s WHERE guild_id = %s AND user_id = %s",
                new_level,
                member.guild.id,
                member.id,
            )
            earned = await self.sync_rewards(member, new_level)
            if new_level > old_level:
                await self.announce(member, new_level, channel, earned)
        return XPResult(xp=xp, old_level=old_level, new_level=new_level)

    # ------------------------------------------------------------------ rewards

    async def rewards(self, guild_id: int) -> list[dict]:
        return await self.bot.db.fetchall(
            "SELECT level, role_id FROM level_rewards WHERE guild_id = %s ORDER BY level", guild_id
        )

    async def sync_rewards(self, member: discord.Member, level: int) -> list[discord.Role]:
        """Gives all reward roles up to `level` and removes those above. Returns newly added roles."""
        guild = member.guild
        me = guild.me
        to_add: list[discord.Role] = []
        to_remove: list[discord.Role] = []
        for reward in await self.rewards(guild.id):
            role = guild.get_role(int(reward["role_id"]))
            if role is None or role.managed or role >= me.top_role:
                continue
            if reward["level"] <= level and role not in member.roles:
                to_add.append(role)
            elif reward["level"] > level and role in member.roles:
                to_remove.append(role)

        if not me.guild_permissions.manage_roles:
            if to_add or to_remove:
                log.warning("Missing 'Manage Roles' permission in %s – can't sync level rewards", guild.name)
            return []
        try:
            if to_add:
                await member.add_roles(*to_add, reason=f"Level reward (level {level})")
            if to_remove:
                await member.remove_roles(*to_remove, reason=f"Level reward removed (level {level})")
        except discord.HTTPException as exc:
            log.warning("Failed to sync level rewards for %s: %s", member, exc)
            return []
        return to_add

    # ------------------------------------------------------------------ announcements

    async def announce(
        self,
        member: discord.Member,
        level: int,
        fallback: discord.abc.Messageable | None,
        earned: list[discord.Role],
    ) -> None:
        settings = await self.settings(member.guild.id)
        if not settings.announce:
            return
        target = member.guild.get_channel(settings.announce_channel_id) if settings.announce_channel_id else fallback
        if not isinstance(target, discord.abc.Messageable):
            return

        text = (
            (settings.levelup_message or DEFAULT_LEVELUP_MESSAGE)
            .replace("{user}", member.mention)
            .replace("{level}", str(level))
            .replace("{server}", member.guild.name)
        )
        if earned:
            text += "\n🏅 New role" + ("s" if len(earned) > 1 else "") + ": " + ", ".join(r.mention for r in earned)
        try:
            await target.send(text, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except discord.HTTPException as exc:
            log.debug("Level-up announcement failed: %s", exc)
