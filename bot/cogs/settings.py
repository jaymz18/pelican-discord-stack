"""Server-Einstellungen (/setup ...), gespeichert in MariaDB."""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import upsert_guild

if TYPE_CHECKING:
    from main import PelicanBot


class Settings(commands.Cog):
    setup = app_commands.Group(
        name="setup",
        description="Bot-Einstellungen für diesen Server",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    async def _set(self, guild: discord.Guild, column: str, value: object) -> None:
        # column stammt ausschließlich aus dem festen Mapping unten – kein User-Input.
        await upsert_guild(self.bot, guild)
        await self.bot.db.execute(f"UPDATE guilds SET {column} = %s WHERE guild_id = %s", value, guild.id)

    @setup.command(name="welcome", description="Legt den Kanal für Willkommensnachrichten fest")
    async def welcome(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set(interaction.guild, "welcome_channel_id", channel.id)
        await interaction.response.send_message(f"✅ Willkommensnachrichten gehen jetzt in {channel.mention}.", ephemeral=True)

    @setup.command(name="welcome-message", description="Eigener Willkommenstext – Platzhalter: {user} {server} {count}")
    async def welcome_message(self, interaction: discord.Interaction, text: app_commands.Range[str, 5, 500]) -> None:
        await self._set(interaction.guild, "welcome_message", text)
        preview = (
            text.replace("{user}", interaction.user.mention)
            .replace("{server}", interaction.guild.name)
            .replace("{count}", str(interaction.guild.member_count))
        )
        await interaction.response.send_message(f"✅ Gespeichert. Vorschau:\n> {preview}", ephemeral=True)

    @setup.command(name="logs", description="Legt den Kanal für Moderations- und Event-Logs fest")
    async def logs(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set(interaction.guild, "log_channel_id", channel.id)
        await interaction.response.send_message(f"✅ Logs gehen jetzt in {channel.mention}.", ephemeral=True)

    @setup.command(name="disable", description="Deaktiviert Willkommensnachrichten oder Logs")
    async def disable(self, interaction: discord.Interaction, feature: Literal["welcome", "logs"]) -> None:
        column = {"welcome": "welcome_channel_id", "logs": "log_channel_id"}[feature]
        await self._set(interaction.guild, column, None)
        await interaction.response.send_message(f"✅ `{feature}` deaktiviert.", ephemeral=True)

    @setup.command(name="show", description="Zeigt die aktuellen Einstellungen")
    async def show(self, interaction: discord.Interaction) -> None:
        await upsert_guild(self.bot, interaction.guild)
        row = await self.bot.db.fetchone(
            "SELECT welcome_channel_id, welcome_message, log_channel_id FROM guilds WHERE guild_id = %s",
            interaction.guild_id,
        )

        def channel(cid: int | None) -> str:
            return f"<#{cid}>" if cid else "*deaktiviert*"

        embed = discord.Embed(title=f"⚙️ Einstellungen – {interaction.guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Willkommenskanal", value=channel(row["welcome_channel_id"]))
        embed.add_field(name="Log-Kanal", value=channel(row["log_channel_id"]))
        embed.add_field(name="Willkommenstext", value=row["welcome_message"] or "*Standard*", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Settings(bot))
