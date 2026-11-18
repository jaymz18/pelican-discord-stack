"""Leveling system: message & voice XP, ranks, leaderboard, role rewards and admin configuration."""
from __future__ import annotations

import logging
import math
import random
import time
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import level_for_xp, progress_bar, xp_for_level
from utils.leveling import DEFAULT_LEVELUP_MESSAGE, LevelManager

if TYPE_CHECKING:
    from main import PelicanBot

log = logging.getLogger("bot.levels")

MESSAGE_XP_COOLDOWN = 60  # seconds between two XP grants per member
MESSAGE_XP_RANGE = (15, 25)
VOICE_XP_PER_MINUTE = 10
LEADERBOARD_PAGE_SIZE = 10
MAX_ADMIN_XP = 10_000_000

GOLD = discord.Color.gold()


class ConfirmView(discord.ui.View):
    """Simple yes/no confirmation that only the invoking user can answer."""

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=30)
        self.author_id = author_id
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, reset everything", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


class Levels(commands.Cog):
    xp = app_commands.Group(
        name="xp",
        description="Manage member XP",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )
    levelconfig = app_commands.Group(
        name="levelconfig",
        description="Configure the leveling system for this server",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot
        self.levels = LevelManager(bot)
        bot.levels = self.levels
        self._cooldowns: dict[tuple[int, int], float] = {}

    async def cog_load(self) -> None:
        self.voice_xp_loop.start()

    async def cog_unload(self) -> None:
        self.voice_xp_loop.cancel()

    # ================================================================== XP sources

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return
        try:
            settings = await self.levels.settings(message.guild.id)
            channel_id = getattr(message.channel, "parent_id", None) or message.channel.id
            gain = 0
            if message.channel.id not in settings.ignored_channels and channel_id not in settings.ignored_channels:
                key = (message.guild.id, message.author.id)
                now = time.monotonic()
                if now - self._cooldowns.get(key, 0.0) >= MESSAGE_XP_COOLDOWN:
                    self._cooldowns[key] = now
                    gain = max(1, round(random.randint(*MESSAGE_XP_RANGE) * settings.xp_multiplier))
            await self.levels.change_xp(message.author, delta=gain, count_message=True, channel=message.channel)
        except Exception:  # noqa: BLE001
            log.exception("Failed to award message XP")

    @tasks.loop(minutes=1)
    async def voice_xp_loop(self) -> None:
        """Awards XP every minute to members who are actively talking with others in voice."""
        for guild in self.bot.guilds:
            try:
                settings = await self.levels.settings(guild.id)
                if not settings.voice_xp:
                    continue
                gain = max(1, round(VOICE_XP_PER_MINUTE * settings.xp_multiplier))
                for channel in [*guild.voice_channels, *guild.stage_channels]:
                    if channel == guild.afk_channel or channel.id in settings.ignored_channels:
                        continue
                    humans = [m for m in channel.members if not m.bot]
                    if len(humans) < 2:
                        continue
                    for member in humans:
                        state = member.voice
                        if state is None or state.self_mute or state.self_deaf or state.mute or state.deaf:
                            continue
                        await self.levels.change_xp(member, delta=gain, voice_minutes=1)
            except Exception:  # noqa: BLE001
                log.exception("Voice XP failed for guild %s", guild.id)

    @voice_xp_loop.before_loop
    async def before_voice_xp(self) -> None:
        await self.bot.wait_until_ready()

    # ================================================================== public commands

    @app_commands.command(name="rank", description="Shows the level, XP and rank of a member")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to look up (default: you)")
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        member = member or interaction.user
        row = await self.bot.db.fetchone(
            "SELECT xp, messages, voice_minutes FROM levels WHERE guild_id = %s AND user_id = %s",
            interaction.guild_id,
            member.id,
        )
        if not row or row["xp"] == 0:
            who = "You haven't" if member == interaction.user else f"{member.display_name} hasn't"
            await interaction.response.send_message(f"{who} earned any XP yet.", ephemeral=True)
            return

        pos = await self.bot.db.fetchone(
            "SELECT COUNT(*) + 1 AS pos FROM levels WHERE guild_id = %s AND xp > %s", interaction.guild_id, row["xp"]
        )
        total = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS n FROM levels WHERE guild_id = %s AND xp > 0", interaction.guild_id
        )
        xp = int(row["xp"])
        level = level_for_xp(xp)
        floor, ceil = xp_for_level(level), xp_for_level(level + 1)
        current, needed = xp - floor, ceil - floor

        embed = discord.Embed(color=GOLD)
        embed.set_author(name=f"{member.display_name}'s rank", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Rank", value=f"#{pos['pos']} of {total['n']}")
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Total XP", value=f"{xp:,}")
        embed.add_field(
            name=f"Progress to level {level + 1}",
            value=f"{progress_bar(current, needed)} {current:,} / {needed:,} XP ({math.floor(current / needed * 100)}%)",
            inline=False,
        )
        embed.add_field(name="Messages", value=f"{row['messages']:,}")
        embed.add_field(name="Voice time", value=f"{row['voice_minutes'] // 60}h {row['voice_minutes'] % 60}m")

        next_reward = next((r for r in await self.levels.rewards(interaction.guild_id) if r["level"] > level), None)
        if next_reward:
            role = interaction.guild.get_role(int(next_reward["role_id"]))
            if role:
                embed.add_field(name="Next reward", value=f"{role.mention} at level {next_reward['level']}")
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="leaderboard", description="Shows the members with the most XP")
    @app_commands.guild_only()
    @app_commands.describe(page="Page number (10 members per page)")
    async def leaderboard(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 1000] = 1) -> None:
        total = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS n FROM levels WHERE guild_id = %s AND xp > 0", interaction.guild_id
        )
        pages = max(1, math.ceil(total["n"] / LEADERBOARD_PAGE_SIZE))
        page = min(page, pages)
        rows = await self.bot.db.fetchall(
            "SELECT user_id, xp, voice_minutes FROM levels WHERE guild_id = %s AND xp > 0 "
            "ORDER BY xp DESC LIMIT %s OFFSET %s",
            interaction.guild_id,
            LEADERBOARD_PAGE_SIZE,
            (page - 1) * LEADERBOARD_PAGE_SIZE,
        )
        if not rows:
            await interaction.response.send_message("No one has earned XP yet – start chatting! 💬")
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        start = (page - 1) * LEADERBOARD_PAGE_SIZE
        lines = [
            f"{medals.get(i, f'`#{i}`')} <@{r['user_id']}> – Level **{level_for_xp(r['xp'])}** · {r['xp']:,} XP"
            for i, r in enumerate(rows, start=start + 1)
        ]
        embed = discord.Embed(
            title=f"🏆 Leaderboard – {interaction.guild.name}", description="\n".join(lines), color=GOLD
        )
        embed.set_footer(text=f"Page {page}/{pages} · {total['n']} ranked members")
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="rewards", description="Lists the roles you can earn by leveling up")
    @app_commands.guild_only()
    async def rewards(self, interaction: discord.Interaction) -> None:
        rewards = await self.levels.rewards(interaction.guild_id)
        lines = []
        for r in rewards:
            role = interaction.guild.get_role(int(r["role_id"]))
            lines.append(f"**Level {r['level']}** → {role.mention if role else '*deleted role*'}")
        embed = discord.Embed(
            title="🏅 Level rewards",
            description="\n".join(lines) or "No level rewards have been set up yet.",
            color=GOLD,
        )
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # ================================================================== /xp (admin)

    async def _xp_reply(self, interaction: discord.Interaction, member: discord.Member, result, action: str) -> None:
        text = f"✅ {action} – {member.mention} now has **{result.xp:,} XP** (level {result.new_level})."
        if result.new_level != result.old_level:
            text += f"\nLevel changed: {result.old_level} → {result.new_level}"
        await interaction.response.send_message(text, ephemeral=True)

    @xp.command(name="give", description="Gives XP to a member")
    @app_commands.describe(member="Member", amount="Amount of XP to give")
    async def xp_give(
        self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, MAX_ADMIN_XP]
    ) -> None:
        if member.bot:
            await interaction.response.send_message("Bots can't earn XP.", ephemeral=True)
            return
        result = await self.levels.change_xp(member, delta=amount, channel=interaction.channel)
        await self._xp_reply(interaction, member, result, f"Gave {amount:,} XP")

    @xp.command(name="take", description="Removes XP from a member")
    @app_commands.describe(member="Member", amount="Amount of XP to remove")
    async def xp_take(
        self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, MAX_ADMIN_XP]
    ) -> None:
        result = await self.levels.change_xp(member, delta=-amount)
        await self._xp_reply(interaction, member, result, f"Removed {amount:,} XP")

    @xp.command(name="set", description="Sets a member's XP to an exact value")
    @app_commands.describe(member="Member", amount="New total XP")
    async def xp_set(
        self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 0, MAX_ADMIN_XP]
    ) -> None:
        if member.bot:
            await interaction.response.send_message("Bots can't earn XP.", ephemeral=True)
            return
        result = await self.levels.change_xp(member, set_to=amount, channel=interaction.channel)
        await self._xp_reply(interaction, member, result, "XP set")

    @xp.command(name="reset", description="Resets a member's XP and level to 0")
    async def xp_reset(self, interaction: discord.Interaction, member: discord.Member) -> None:
        result = await self.levels.change_xp(member, set_to=0)
        await self._xp_reply(interaction, member, result, "XP reset")

    # ================================================================== /levelconfig (admin)

    @levelconfig.command(name="show", description="Shows the current leveling settings")
    async def config_show(self, interaction: discord.Interaction) -> None:
        s = await self.levels.settings(interaction.guild_id)
        rewards = await self.levels.rewards(interaction.guild_id)
        embed = discord.Embed(title=f"⚙️ Leveling settings – {interaction.guild.name}", color=GOLD)
        embed.add_field(name="Level-up messages", value="On" if s.announce else "Off")
        embed.add_field(
            name="Announcement channel",
            value=f"<#{s.announce_channel_id}>" if s.announce_channel_id else "Same channel as the message",
        )
        embed.add_field(name="XP multiplier", value=f"×{s.xp_multiplier:g}")
        embed.add_field(name="Voice XP", value=f"On ({VOICE_XP_PER_MINUTE} XP/min)" if s.voice_xp else "Off")
        embed.add_field(
            name="No-XP channels",
            value=" ".join(f"<#{c}>" for c in s.ignored_channels) or "None",
        )
        embed.add_field(name="Rewards", value=f"{len(rewards)} role(s) – see /rewards")
        embed.add_field(name="Level-up message", value=s.levelup_message or DEFAULT_LEVELUP_MESSAGE, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @levelconfig.command(name="announcements", description="Turns level-up messages on or off")
    async def config_announcements(self, interaction: discord.Interaction, enabled: bool) -> None:
        await self.levels.update_setting(interaction.guild_id, "announce", int(enabled))
        await interaction.response.send_message(
            f"✅ Level-up messages are now **{'on' if enabled else 'off'}**.", ephemeral=True
        )

    @levelconfig.command(name="channel", description="Sets the channel for level-up messages (empty = same channel)")
    @app_commands.describe(channel="Channel for level-up messages – leave empty to reply where the member chatted")
    async def config_channel(
        self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None
    ) -> None:
        await self.levels.update_setting(interaction.guild_id, "announce_channel_id", channel.id if channel else None)
        where = channel.mention if channel else "the channel where the member leveled up"
        await interaction.response.send_message(f"✅ Level-up messages will be sent to {where}.", ephemeral=True)

    @levelconfig.command(name="message", description="Custom level-up message – placeholders: {user} {level} {server}")
    @app_commands.describe(text="New message, or 'default' to restore the default message")
    async def config_message(self, interaction: discord.Interaction, text: app_commands.Range[str, 3, 500]) -> None:
        value = None if text.strip().lower() == "default" else text
        await self.levels.update_setting(interaction.guild_id, "levelup_message", value)
        preview = (
            (value or DEFAULT_LEVELUP_MESSAGE)
            .replace("{user}", interaction.user.mention)
            .replace("{level}", "5")
            .replace("{server}", interaction.guild.name)
        )
        await interaction.response.send_message(f"✅ Saved. Preview:\n> {preview}", ephemeral=True)

    @levelconfig.command(name="multiplier", description="Sets the XP multiplier for this server")
    @app_commands.describe(value="Multiplier between 0.1 and 5.0 (default 1.0)")
    async def config_multiplier(
        self, interaction: discord.Interaction, value: app_commands.Range[float, 0.1, 5.0]
    ) -> None:
        await self.levels.update_setting(interaction.guild_id, "xp_multiplier", round(value, 2))
        await interaction.response.send_message(f"✅ XP multiplier set to **×{round(value, 2):g}**.", ephemeral=True)

    @levelconfig.command(name="voice-xp", description="Turns XP for time spent in voice channels on or off")
    async def config_voice(self, interaction: discord.Interaction, enabled: bool) -> None:
        await self.levels.update_setting(interaction.guild_id, "voice_xp", int(enabled))
        await interaction.response.send_message(f"✅ Voice XP is now **{'on' if enabled else 'off'}**.", ephemeral=True)

    @levelconfig.command(name="ignore", description="Members won't earn XP in this channel")
    async def config_ignore(
        self, interaction: discord.Interaction, channel: discord.TextChannel | discord.VoiceChannel
    ) -> None:
        await self.bot.db.execute(
            "INSERT IGNORE INTO level_ignored_channels (guild_id, channel_id) VALUES (%s, %s)",
            interaction.guild_id,
            channel.id,
        )
        self.levels.invalidate(interaction.guild_id)
        await interaction.response.send_message(f"✅ No XP will be earned in {channel.mention}.", ephemeral=True)

    @levelconfig.command(name="unignore", description="Members earn XP in this channel again")
    async def config_unignore(
        self, interaction: discord.Interaction, channel: discord.TextChannel | discord.VoiceChannel
    ) -> None:
        removed = await self.bot.db.execute(
            "DELETE FROM level_ignored_channels WHERE guild_id = %s AND channel_id = %s",
            interaction.guild_id,
            channel.id,
        )
        self.levels.invalidate(interaction.guild_id)
        msg = f"✅ {channel.mention} gives XP again." if removed else f"{channel.mention} wasn't on the ignore list."
        await interaction.response.send_message(msg, ephemeral=True)

    @levelconfig.command(name="reward-add", description="Gives a role when members reach a level")
    @app_commands.describe(level="Level at which the role is given", role="Role to give")
    async def config_reward_add(
        self, interaction: discord.Interaction, level: app_commands.Range[int, 1, 1000], role: discord.Role
    ) -> None:
        me = interaction.guild.me
        if role.managed or role.is_default():
            await interaction.response.send_message("This role can't be assigned by bots.", ephemeral=True)
            return
        if role >= me.top_role:
            await interaction.response.send_message(
                f"{role.mention} is above my highest role – move my role higher first.", ephemeral=True
            )
            return
        await self.bot.db.execute(
            "INSERT INTO level_rewards (guild_id, level, role_id) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE role_id = VALUES(role_id)",
            interaction.guild_id,
            level,
            role.id,
        )
        note = "" if me.guild_permissions.manage_roles else "\n⚠️ I need the **Manage Roles** permission to give it."
        await interaction.response.send_message(
            f"✅ Members reaching **level {level}** will get {role.mention}.{note}\n"
            "Existing members receive it the next time they level up.",
            ephemeral=True,
        )

    @levelconfig.command(name="reward-remove", description="Removes the role reward for a level")
    async def config_reward_remove(
        self, interaction: discord.Interaction, level: app_commands.Range[int, 1, 1000]
    ) -> None:
        removed = await self.bot.db.execute(
            "DELETE FROM level_rewards WHERE guild_id = %s AND level = %s", interaction.guild_id, level
        )
        msg = f"✅ Reward for level {level} removed." if removed else f"There is no reward for level {level}."
        await interaction.response.send_message(msg, ephemeral=True)

    @levelconfig.command(name="reset-all", description="Resets XP and levels of ALL members on this server")
    async def config_reset_all(self, interaction: discord.Interaction) -> None:
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(
            "⚠️ This deletes the XP and level of **every member** on this server. This can't be undone.",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.confirmed:
            await interaction.edit_original_response(content="Cancelled – nothing was reset.", view=None)
            return
        deleted = await self.bot.db.execute("DELETE FROM levels WHERE guild_id = %s", interaction.guild_id)
        await interaction.edit_original_response(
            content=f"🧹 Leveling data of {deleted} member(s) has been reset. Reward roles were not removed.",
            view=None,
        )


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Levels(bot))
