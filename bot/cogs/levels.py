"""Level-System: XP für Nachrichten, /rank und /leaderboard."""
from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import level_for_xp, progress_bar, xp_for_level

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.levels")

XP_COOLDOWN = 60  # Sekunden zwischen zwei XP-Vergaben pro Mitglied
XP_RANGE = (15, 25)


class Levels(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot
        self._cooldowns: dict[tuple[int, int], float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        gain = 0
        if now - self._cooldowns.get(key, 0.0) >= XP_COOLDOWN:
            gain = random.randint(*XP_RANGE)
            self._cooldowns[key] = now

        try:
            await self.bot.db.execute(
                """
                INSERT INTO levels (guild_id, user_id, username, avatar_url, xp, level, messages, last_xp_at)
                VALUES (%s, %s, %s, %s, %s, 0, 1, IF(%s > 0, UTC_TIMESTAMP(), NULL))
                ON DUPLICATE KEY UPDATE username = VALUES(username), avatar_url = VALUES(avatar_url),
                    xp = xp + VALUES(xp), messages = messages + 1,
                    last_xp_at = IF(VALUES(xp) > 0, UTC_TIMESTAMP(), last_xp_at)
                """,
                message.guild.id,
                message.author.id,
                str(message.author)[:100],
                message.author.display_avatar.url,
                gain,
                gain,
            )
            if not gain:
                return

            row = await self.bot.db.fetchone(
                "SELECT xp, level FROM levels WHERE guild_id = %s AND user_id = %s", message.guild.id, message.author.id
            )
            new_level = level_for_xp(row["xp"])
            if new_level > row["level"]:
                await self.bot.db.execute(
                    "UPDATE levels SET level = %s WHERE guild_id = %s AND user_id = %s",
                    new_level,
                    message.guild.id,
                    message.author.id,
                )
                await message.channel.send(f"🎉 {message.author.mention} hat **Level {new_level}** erreicht!")
        except discord.HTTPException:
            pass
        except Exception:  # noqa: BLE001
            log.exception("XP-Vergabe fehlgeschlagen")

    @app_commands.command(name="rank", description="Zeigt Level und XP eines Mitglieds")
    @app_commands.guild_only()
    @app_commands.describe(member="Mitglied (Standard: du selbst)")
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        member = member or interaction.user
        row = await self.bot.db.fetchone(
            "SELECT xp, level, messages FROM levels WHERE guild_id = %s AND user_id = %s", interaction.guild_id, member.id
        )
        if not row:
            await interaction.response.send_message(f"{member.display_name} hat noch keine XP gesammelt.", ephemeral=True)
            return

        pos = await self.bot.db.fetchone(
            "SELECT COUNT(*) + 1 AS pos FROM levels WHERE guild_id = %s AND xp > %s", interaction.guild_id, row["xp"]
        )
        level = level_for_xp(row["xp"])
        floor, ceil = xp_for_level(level), xp_for_level(level + 1)
        current, needed = row["xp"] - floor, ceil - floor

        embed = discord.Embed(title=f"Rang von {member.display_name}", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Platz", value=f"#{pos['pos']}")
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Nachrichten", value=str(row["messages"]))
        embed.add_field(
            name=f"Fortschritt ({row['xp']} XP gesamt)",
            value=f"{progress_bar(current, needed)} {current}/{needed} XP",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Die Top 10 Mitglieder nach XP")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall(
            "SELECT user_id, username, xp, messages FROM levels WHERE guild_id = %s ORDER BY xp DESC LIMIT 10",
            interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message("Noch keine Daten – schreibt ein paar Nachrichten! 💬")
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = [
            f"{medals.get(i, f'`#{i}`')} <@{r['user_id']}> – Level **{level_for_xp(r['xp'])}** · {r['xp']} XP"
            for i, r in enumerate(rows, start=1)
        ]
        embed = discord.Embed(
            title=f"🏆 Leaderboard – {interaction.guild.name}", description="\n".join(lines), color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Levels(bot))
