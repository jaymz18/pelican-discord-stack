"""General commands – hybrid commands usable as /slash AND with the prefix (e.g. !ping)."""
from __future__ import annotations

import platform
import time
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import PelicanBot


class General(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Shows the latency of the bot and the database")
    async def ping(self, ctx: commands.Context) -> None:
        start = time.perf_counter()
        db_ok = await self.bot.db.ping()
        db_ms = round((time.perf_counter() - start) * 1000)
        db_text = f"{db_ms} ms" if db_ok else "❌ unreachable"
        await ctx.send(f"🏓 Pong! Gateway: **{round(self.bot.latency * 1000)} ms** · Database: **{db_text}**")

    @commands.hybrid_command(name="help", description="Lists all commands")
    async def help(self, ctx: commands.Context) -> None:
        lines: list[str] = []
        for cmd in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            if isinstance(cmd, app_commands.Group):
                for sub in cmd.commands:
                    lines.append(f"`/{cmd.name} {sub.name}` – {sub.description}")
            else:
                lines.append(f"`/{cmd.name}` – {cmd.description}")
        embed = discord.Embed(title="📖 Commands", description="\n".join(lines)[:4096], color=discord.Color.gold())
        prefix = (await self.bot.get_prefix(ctx.message))[-1] if ctx.message else "!"
        embed.set_footer(text=f"General commands also work with the prefix, e.g. {prefix}ping")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Shows information about this server")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        g = ctx.guild
        embed = discord.Embed(title=g.name, color=discord.Color.gold())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "–")
        embed.add_field(name="Members", value=str(g.member_count))
        embed.add_field(name="Boost level", value=f"{g.premium_tier} ({g.premium_subscription_count} boosts)")
        embed.add_field(name="Channels", value=f"{len(g.text_channels)} text · {len(g.voice_channels)} voice")
        embed.add_field(name="Roles", value=str(len(g.roles)))
        embed.add_field(name="Created", value=discord.utils.format_dt(g.created_at, "D"))
        embed.set_footer(text=f"ID: {g.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="userinfo", description="Shows information about a member")
    @commands.guild_only()
    @app_commands.describe(member="Member to look up (default: you)")
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        member = member or ctx.author
        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        embed = discord.Embed(title=str(member), color=member.color if member.color.value else discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Display name", value=member.display_name)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No")
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        if member.joined_at:
            embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "R"))
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:15]) or "–", inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="avatar", description="Shows a user's avatar")
    @app_commands.describe(user="User (default: you)")
    async def avatar(self, ctx: commands.Context, user: Optional[discord.User] = None) -> None:
        user = user or ctx.author
        embed = discord.Embed(title=f"{user.display_name}'s avatar", color=discord.Color.gold())
        embed.set_image(url=user.display_avatar.with_size(1024).url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="botinfo", description="Shows information and statistics about the bot")
    async def botinfo(self, ctx: commands.Context) -> None:
        row = await self.bot.db.fetchone("SELECT COUNT(*) AS total FROM command_log")
        embed = discord.Embed(title=f"🤖 {self.bot.user.name}", color=discord.Color.gold())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        embed.add_field(name="Commands run", value=str(row["total"] if row else 0))
        embed.add_field(name="Online since", value=discord.utils.format_dt(self.bot.started_at, "R"))
        embed.add_field(name="Python", value=platform.python_version())
        embed.add_field(name="discord.py", value=discord.__version__)
        embed.add_field(name="Database", value="MariaDB ✅" if await self.bot.db.ping() else "MariaDB ❌")
        await ctx.send(embed=embed)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(General(bot))
