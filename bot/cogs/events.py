"""Events: ready, member join/leave, guild join/leave, message logs, command logging, error handling."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import send_log, upsert_guild

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.events")

DEFAULT_WELCOME = "Welcome to **{server}**, {user}! You are member **#{count}**."


class Events(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.tree.on_error = self.on_tree_error
        self.heartbeat.start()

    async def cog_unload(self) -> None:
        self.heartbeat.cancel()

    # ------------------------------------------------------------------ lifecycle

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            await upsert_guild(self.bot, guild)
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.bot.guilds)} servers | /help")
        )
        # NOTE: "Bot online als" is the startup marker the Pelican egg waits for – do not change this text.
        log.info("Bot online als %s (ID %s) – ready on %d servers", self.bot.user, self.bot.user.id, len(self.bot.guilds))

    @tasks.loop(seconds=60)
    async def heartbeat(self) -> None:
        """Writes the bot status to the database – the website shows online/offline from it."""
        try:
            latency = None if math.isinf(self.bot.latency) else round(self.bot.latency * 1000)
            user = self.bot.user
            await self.bot.db.execute(
                """
                INSERT INTO bot_status (id, bot_name, bot_avatar, guild_count, user_count, latency_ms, started_at, last_heartbeat)
                VALUES (1, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
                ON DUPLICATE KEY UPDATE bot_name = VALUES(bot_name), bot_avatar = VALUES(bot_avatar),
                    guild_count = VALUES(guild_count), user_count = VALUES(user_count),
                    latency_ms = VALUES(latency_ms), started_at = VALUES(started_at),
                    last_heartbeat = UTC_TIMESTAMP()
                """,
                str(user),
                user.display_avatar.url if user else None,
                len(self.bot.guilds),
                sum(g.member_count or 0 for g in self.bot.guilds),
                latency,
                self.bot.started_at.replace(tzinfo=None),
            )
        except Exception:  # noqa: BLE001
            log.exception("Heartbeat failed")

    @heartbeat.before_loop
    async def before_heartbeat(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ guilds

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await upsert_guild(self.bot, guild)
        log.info("Joined server: %s (%s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.bot.db.execute("UPDATE guilds SET active = 0 WHERE guild_id = %s", guild.id)
        log.info("Left server: %s (%s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        if before.name != after.name or before.icon != after.icon:
            await upsert_guild(self.bot, after)

    # ------------------------------------------------------------------ members

    async def _member_event(self, member: discord.Member, event: str) -> None:
        await self.bot.db.execute(
            "INSERT INTO member_events (guild_id, user_id, username, event) VALUES (%s, %s, %s, %s)",
            member.guild.id,
            member.id,
            str(member)[:100],
            event,
        )
        await upsert_guild(self.bot, member.guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._member_event(member, "join")

        row = await self.bot.db.fetchone(
            "SELECT welcome_channel_id, welcome_message FROM guilds WHERE guild_id = %s", member.guild.id
        )
        if row and row["welcome_channel_id"]:
            channel = member.guild.get_channel(int(row["welcome_channel_id"]))
            if isinstance(channel, discord.TextChannel):
                text = (
                    (row["welcome_message"] or DEFAULT_WELCOME)
                    .replace("{user}", member.mention)
                    .replace("{server}", member.guild.name)
                    .replace("{count}", str(member.guild.member_count))
                )
                embed = discord.Embed(title="👋 Welcome!", description=text, color=discord.Color.green())
                embed.set_thumbnail(url=member.display_avatar.url)
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException as exc:
                    log.warning("Welcome message failed: %s", exc)

        # Members who rejoin get their level reward roles back
        levels = getattr(self.bot, "levels", None)
        if levels is not None:
            stored = await self.bot.db.fetchone(
                "SELECT level FROM levels WHERE guild_id = %s AND user_id = %s", member.guild.id, member.id
            )
            if stored and stored["level"] > 0:
                await levels.sync_rewards(member, int(stored["level"]))

        embed = discord.Embed(description=f"📥 {member.mention} joined the server.", color=discord.Color.green())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        await send_log(self.bot, member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._member_event(member, "leave")
        embed = discord.Embed(description=f"📤 **{member}** left the server.", color=discord.Color.orange())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        await send_log(self.bot, member.guild, embed)

    # ------------------------------------------------------------------ messages

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        embed = discord.Embed(
            title="🗑️ Message deleted",
            description=(message.content or "*no text*")[:4000],
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention)
        await send_log(self.bot, message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.guild is None or after.author.bot or before.content == after.content:
            return
        embed = discord.Embed(title="✏️ Message edited", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_author(name=str(after.author), icon_url=after.author.display_avatar.url)
        embed.add_field(name="Before", value=(before.content or "*empty*")[:1024], inline=False)
        embed.add_field(name="After", value=(after.content or "*empty*")[:1024], inline=False)
        embed.add_field(name="Link", value=f"[Jump to message]({after.jump_url})")
        await send_log(self.bot, after.guild, embed)

    # ------------------------------------------------------------------ command logging

    async def _log_command(self, guild_id: int | None, user_id: int, name: str) -> None:
        try:
            await self.bot.db.execute(
                "INSERT INTO command_log (guild_id, user_id, command) VALUES (%s, %s, %s)", guild_id, user_id, name[:100]
            )
        except Exception:  # noqa: BLE001
            log.exception("Command logging failed")

    @commands.Cog.listener()
    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: app_commands.Command | app_commands.ContextMenu
    ) -> None:
        await self._log_command(interaction.guild_id, interaction.user.id, command.qualified_name)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        # Hybrid commands used as slash commands are already logged by on_app_command_completion.
        if ctx.interaction is None and ctx.command is not None:
            await self._log_command(ctx.guild.id if ctx.guild else None, ctx.author.id, ctx.command.qualified_name)

    # ------------------------------------------------------------------ errors

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            msg = f"You're missing permissions: {', '.join(error.missing_permissions)}"
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = f"I'm missing permissions: {', '.join(error.missing_permissions)}"
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Slow down! Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.NoPrivateMessage):
            msg = "This command only works in servers."
        elif isinstance(error, app_commands.CheckFailure):
            msg = "You're not allowed to use this command."
        else:
            log.error("Error in /%s", interaction.command.qualified_name if interaction.command else "?", exc_info=error)
            msg = "❌ Something went wrong. Please try again later."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound) or ctx.interaction is not None:
            return
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.reply(f"Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ Please wait {error.retry_after:.1f}s.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.reply("You're not allowed to use this command.")
        else:
            log.error("Error in prefix command %s", ctx.command, exc_info=error)
            await ctx.reply("❌ Something went wrong. Please try again later.")


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Events(bot))
