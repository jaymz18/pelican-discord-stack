"""Server settings (/setup ...), stored in MariaDB."""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

from config import DEFAULT_WELCOME_CHANNEL_ID
from utils.helpers import upsert_guild

if TYPE_CHECKING:
    from main import PelicanBot


class Settings(commands.Cog):
    setup = app_commands.Group(
        name="setup",
        description="Bot settings for this server",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    async def _set(self, guild: discord.Guild, column: str, value: object) -> None:
        # column only ever comes from the fixed values below – never from user input.
        await upsert_guild(self.bot, guild)
        await self.bot.db.execute(f"UPDATE guilds SET {column} = %s WHERE guild_id = %s", value, guild.id)

    @setup.command(name="welcome", description="Sets the channel for welcome messages")
    @app_commands.describe(channel="Channel for welcome messages")
    async def welcome(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set(interaction.guild, "welcome_channel_id", channel.id)
        await interaction.response.send_message(f"✅ Welcome messages will be sent to {channel.mention}.", ephemeral=True)

    @setup.command(name="welcome-message", description="Custom welcome text – placeholders: {user} {server} {count}")
    @app_commands.describe(text="New welcome text")
    async def welcome_message(self, interaction: discord.Interaction, text: app_commands.Range[str, 5, 500]) -> None:
        await self._set(interaction.guild, "welcome_message", text)
        preview = (
            text.replace("{user}", interaction.user.mention)
            .replace("{server}", interaction.guild.name)
            .replace("{count}", str(interaction.guild.member_count))
        )
        await interaction.response.send_message(f"✅ Saved. Preview:\n> {preview}", ephemeral=True)

    @setup.command(name="logs", description="Sets the channel for moderation and event logs")
    @app_commands.describe(channel="Channel for logs")
    async def logs(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set(interaction.guild, "log_channel_id", channel.id)
        await interaction.response.send_message(f"✅ Logs will be sent to {channel.mention}.", ephemeral=True)

    @setup.command(name="disable", description="Disables welcome messages or logs")
    @app_commands.describe(feature="Feature to disable")
    async def disable(self, interaction: discord.Interaction, feature: Literal["welcome", "logs"]) -> None:
        if feature == "welcome":
            # 0 = explicitly disabled (NULL would fall back to the default welcome channel)
            await self._set(interaction.guild, "welcome_channel_id", 0)
        else:
            await self._set(interaction.guild, "log_channel_id", None)
        await interaction.response.send_message(f"✅ `{feature}` disabled.", ephemeral=True)

    @setup.command(name="show", description="Shows the current settings")
    async def show(self, interaction: discord.Interaction) -> None:
        await upsert_guild(self.bot, interaction.guild)
        row = await self.bot.db.fetchone(
            "SELECT welcome_channel_id, welcome_message, log_channel_id FROM guilds WHERE guild_id = %s",
            interaction.guild_id,
        )

        def channel(cid: int | None) -> str:
            return f"<#{cid}>" if cid else "*disabled*"

        embed = discord.Embed(title=f"⚙️ Settings – {interaction.guild.name}", color=discord.Color.gold())
        welcome_id = row["welcome_channel_id"]
        if welcome_id == 0:
            welcome = "*disabled*"
        elif welcome_id:
            welcome = f"<#{welcome_id}>"
        elif interaction.guild.get_channel(DEFAULT_WELCOME_CHANNEL_ID):
            welcome = f"<#{DEFAULT_WELCOME_CHANNEL_ID}> (default)"
        else:
            welcome = "*not set*"
        embed.add_field(name="Welcome channel", value=welcome)
        embed.add_field(name="Log channel", value=channel(row["log_channel_id"]))
        embed.add_field(name="Welcome text", value=row["welcome_message"] or "*default*", inline=False)
        embed.add_field(name="Placeholders", value="`{user}` `{server}` `{count}`", inline=False)
        embed.set_footer(text="Leveling settings: /levelconfig show")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Settings(bot))
