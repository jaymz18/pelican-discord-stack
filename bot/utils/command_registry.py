"""Writes all slash commands to the bot_commands table – the website lists them on /commands."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.commands")

# Cog class name -> category on the website (order = display order)
CATEGORIES = {
    "General": "General",
    "Levels": "Leveling",
    "Moderation": "Moderation",
    "Fun": "Fun",
    "Settings": "Settings",
}

PERMISSION_NAMES = {
    "administrator": "Administrator",
    "manage_guild": "Manage Server",
    "manage_messages": "Manage Messages",
    "moderate_members": "Moderate Members",
    "kick_members": "Kick Members",
    "ban_members": "Ban Members",
    "manage_roles": "Manage Roles",
}


def _permissions(perms: discord.Permissions | None) -> str | None:
    if perms is None:
        return None
    names = [PERMISSION_NAMES.get(name, name.replace("_", " ").title()) for name, value in perms if value]
    return ", ".join(names) or None


def _options(command: app_commands.Command) -> list[dict]:
    return [
        {
            "name": p.display_name,
            "description": "" if p.description in ("…", "...") else p.description,
            "required": p.required,
        }
        for p in command.parameters
    ]


def _collect(bot: "PelicanBot") -> list[dict]:
    rows: list[dict] = []
    category_order = list(CATEGORIES.values())

    def add(cmd: app_commands.Command, parent: app_commands.Group | None = None) -> None:
        binding = cmd.binding or (parent and getattr(parent, "binding", None))
        category = CATEGORIES.get(type(binding).__name__, "Other") if binding else "Other"
        perms = cmd.default_permissions or (parent.default_permissions if parent else None)
        guild_only = bool(getattr(cmd, "guild_only", False) or (parent and getattr(parent, "guild_only", False)))
        rows.append(
            {
                "name": cmd.qualified_name,
                "category": category,
                "description": cmd.description[:200],
                "options": json.dumps(_options(cmd), ensure_ascii=False),
                "permissions": _permissions(perms),
                "guild_only": guild_only,
                # Hybrid commands also exist as text commands (e.g. !ping)
                "prefix_supported": parent is None and bot.get_command(cmd.name) is not None,
            }
        )

    for cmd in bot.tree.get_commands():
        if isinstance(cmd, app_commands.Group):
            for sub in cmd.walk_commands():
                if isinstance(sub, app_commands.Command):
                    add(sub, parent=cmd)
        elif isinstance(cmd, app_commands.Command):
            add(cmd)

    def sort_key(row: dict) -> tuple[int, str]:
        cat = row["category"]
        return (category_order.index(cat) if cat in category_order else len(category_order), row["name"])

    rows.sort(key=sort_key)
    for i, row in enumerate(rows):
        row["sort_order"] = i
    return rows


async def publish_commands(bot: "PelicanBot") -> None:
    rows = _collect(bot)
    try:
        for r in rows:
            await bot.db.execute(
                """
                INSERT INTO bot_commands (name, category, description, options, permissions, guild_only, prefix_supported, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE category = VALUES(category), description = VALUES(description),
                    options = VALUES(options), permissions = VALUES(permissions), guild_only = VALUES(guild_only),
                    prefix_supported = VALUES(prefix_supported), sort_order = VALUES(sort_order)
                """,
                r["name"], r["category"], r["description"], r["options"], r["permissions"],
                r["guild_only"], r["prefix_supported"], r["sort_order"],
            )
        # Remove commands that no longer exist
        if rows:
            placeholders = ", ".join(["%s"] * len(rows))
            await bot.db.execute(
                f"DELETE FROM bot_commands WHERE name NOT IN ({placeholders})", *[r["name"] for r in rows]
            )
        log.info("Published %d commands for the website", len(rows))
    except Exception:  # noqa: BLE001 – the command list is not critical for the bot
        log.exception("Could not store the command list")
