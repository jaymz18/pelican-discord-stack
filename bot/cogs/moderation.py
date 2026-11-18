"""Moderation: warnings (stored in MariaDB), kick, timeout, purge."""
from __future__ import annotations

from datetime import timedelta, timezone
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import can_moderate, send_log

if TYPE_CHECKING:
    from main import PelicanBot

NO_REASON = "No reason given"


class Moderation(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    async def _check_target(self, interaction: discord.Interaction, member: discord.Member) -> bool:
        error = can_moderate(interaction.user, member)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return False
        return True

    @staticmethod
    async def _dm(member: discord.Member, text: str) -> None:
        try:
            await member.send(text)
        except discord.HTTPException:
            pass  # DMs disabled

    @app_commands.command(name="warn", description="Warns a member")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    async def warn(
        self, interaction: discord.Interaction, member: discord.Member, reason: app_commands.Range[str, 1, 500]
    ) -> None:
        if member.bot:
            await interaction.response.send_message("Bots can't be warned.", ephemeral=True)
            return
        if not await self._check_target(interaction, member):
            return

        warn_id = await self.bot.db.insert(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (%s, %s, %s, %s)",
            interaction.guild_id,
            member.id,
            interaction.user.id,
            reason,
        )
        count = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS n FROM warnings WHERE guild_id = %s AND user_id = %s", interaction.guild_id, member.id
        )

        embed = discord.Embed(title=f"⚠️ Warning #{warn_id}", color=discord.Color.orange())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Total warnings", value=str(count["n"]))
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)
        await self._dm(member, f"⚠️ You have been warned on **{interaction.guild.name}**: {reason}")

    @app_commands.command(name="warnings", description="Shows the warnings of a member")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to look up")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await self.bot.db.fetchall(
            "SELECT id, moderator_id, reason, created_at FROM warnings "
            "WHERE guild_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 15",
            interaction.guild_id,
            member.id,
        )
        if not rows:
            await interaction.response.send_message(f"✅ {member.display_name} has no warnings.", ephemeral=True)
            return
        lines = [
            f"**#{r['id']}** · <@{r['moderator_id']}> · "
            f"{discord.utils.format_dt(r['created_at'].replace(tzinfo=timezone.utc), 'd')}\n{r['reason']}"
            for r in rows
        ]
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}", description="\n\n".join(lines), color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Deletes all warnings of a member")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Member whose warnings will be deleted")
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        deleted = await self.bot.db.execute(
            "DELETE FROM warnings WHERE guild_id = %s AND user_id = %s", interaction.guild_id, member.id
        )
        await interaction.response.send_message(f"🧹 Deleted {deleted} warning(s) of {member.mention}.", ephemeral=True)

    @app_commands.command(name="kick", description="Kicks a member from the server")
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member, reason: Optional[app_commands.Range[str, 1, 400]] = None
    ) -> None:
        if not await self._check_target(interaction, member):
            return
        reason = reason or NO_REASON
        await self._dm(member, f"👢 You have been kicked from **{interaction.guild.name}**: {reason}")
        await member.kick(reason=f"{interaction.user} – {reason}")

        embed = discord.Embed(title="👢 Member kicked", color=discord.Color.red())
        embed.add_field(name="Member", value=str(member))
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(name="timeout", description="Times out a member for X minutes")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.describe(
        member="Member to time out",
        minutes="Duration in minutes (max. 28 days), 0 removes the timeout",
        reason="Reason for the timeout",
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 0, 40320],
        reason: Optional[app_commands.Range[str, 1, 400]] = None,
    ) -> None:
        if not await self._check_target(interaction, member):
            return
        reason = reason or NO_REASON
        if minutes == 0:
            await member.timeout(None, reason=f"{interaction.user} – {reason}")
            await interaction.response.send_message(f"🔊 Removed the timeout of {member.mention}.")
            return

        await member.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} – {reason}")
        embed = discord.Embed(title="🔇 Timeout", color=discord.Color.dark_orange())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)")
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(name="purge", description="Deletes the last N messages in this channel")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
    @app_commands.describe(amount="Number of messages (1–100)", member="Only delete messages from this member")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        member: Optional[discord.Member] = None,
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await interaction.response.send_message("I can't delete messages here.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        check = (lambda m: m.author == member) if member else (lambda m: True)
        deleted = await channel.purge(limit=amount, check=check)
        await interaction.followup.send(f"🧹 Deleted {len(deleted)} message(s).", ephemeral=True)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Moderation(bot))
