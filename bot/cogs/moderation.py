"""Moderation: Verwarnungen (in MariaDB), Kick, Timeout, Purge."""
from __future__ import annotations

from datetime import timedelta, timezone
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import can_moderate, send_log

if TYPE_CHECKING:
    from main import PelicanBot


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
            pass  # DMs deaktiviert

    @app_commands.command(name="warn", description="Verwarnt ein Mitglied")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="Mitglied", reason="Grund der Verwarnung")
    async def warn(
        self, interaction: discord.Interaction, member: discord.Member, reason: app_commands.Range[str, 1, 500]
    ) -> None:
        if member.bot:
            await interaction.response.send_message("Bots können nicht verwarnt werden.", ephemeral=True)
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

        embed = discord.Embed(title=f"⚠️ Verwarnung #{warn_id}", color=discord.Color.orange())
        embed.add_field(name="Mitglied", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Verwarnungen gesamt", value=str(count["n"]))
        embed.add_field(name="Grund", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)
        await self._dm(member, f"⚠️ Du wurdest auf **{interaction.guild.name}** verwarnt: {reason}")

    @app_commands.command(name="warnings", description="Zeigt die Verwarnungen eines Mitglieds")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = await self.bot.db.fetchall(
            "SELECT id, moderator_id, reason, created_at FROM warnings "
            "WHERE guild_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 15",
            interaction.guild_id,
            member.id,
        )
        if not rows:
            await interaction.response.send_message(f"✅ {member.display_name} hat keine Verwarnungen.", ephemeral=True)
            return
        lines = [
            f"**#{r['id']}** · <@{r['moderator_id']}> · "
            f"{discord.utils.format_dt(r['created_at'].replace(tzinfo=timezone.utc), 'd')}\n{r['reason']}"
            for r in rows
        ]
        embed = discord.Embed(
            title=f"Verwarnungen von {member.display_name}", description="\n\n".join(lines), color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Löscht alle Verwarnungen eines Mitglieds")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        deleted = await self.bot.db.execute(
            "DELETE FROM warnings WHERE guild_id = %s AND user_id = %s", interaction.guild_id, member.id
        )
        await interaction.response.send_message(f"🧹 {deleted} Verwarnung(en) von {member.mention} gelöscht.", ephemeral=True)

    @app_commands.command(name="kick", description="Kickt ein Mitglied vom Server")
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member, reason: Optional[app_commands.Range[str, 1, 400]] = None
    ) -> None:
        if not await self._check_target(interaction, member):
            return
        reason = reason or "Kein Grund angegeben"
        await self._dm(member, f"👢 Du wurdest von **{interaction.guild.name}** gekickt: {reason}")
        await member.kick(reason=f"{interaction.user} – {reason}")

        embed = discord.Embed(title="👢 Mitglied gekickt", color=discord.Color.red())
        embed.add_field(name="Mitglied", value=str(member))
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Grund", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(name="timeout", description="Schaltet ein Mitglied für X Minuten stumm")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.describe(minutes="Dauer in Minuten (max. 28 Tage), 0 hebt den Timeout auf")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 0, 40320],
        reason: Optional[app_commands.Range[str, 1, 400]] = None,
    ) -> None:
        if not await self._check_target(interaction, member):
            return
        reason = reason or "Kein Grund angegeben"
        if minutes == 0:
            await member.timeout(None, reason=f"{interaction.user} – {reason}")
            await interaction.response.send_message(f"🔊 Timeout von {member.mention} aufgehoben.")
            return

        await member.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} – {reason}")
        embed = discord.Embed(title="🔇 Timeout", color=discord.Color.dark_orange())
        embed.add_field(name="Mitglied", value=member.mention)
        embed.add_field(name="Dauer", value=f"{minutes} Minuten")
        embed.add_field(name="Grund", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(name="purge", description="Löscht die letzten N Nachrichten in diesem Kanal")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
    @app_commands.describe(amount="Anzahl (1–100)", member="Nur Nachrichten dieses Mitglieds löschen")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        member: Optional[discord.Member] = None,
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await interaction.response.send_message("Hier kann ich keine Nachrichten löschen.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        check = (lambda m: m.author == member) if member else (lambda m: True)
        deleted = await channel.purge(limit=amount, check=check)
        await interaction.followup.send(f"🧹 {len(deleted)} Nachricht(en) gelöscht.", ephemeral=True)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Moderation(bot))
