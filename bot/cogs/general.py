"""Allgemeine Commands – als Hybrid-Commands per /slash UND per Prefix (z. B. !ping) nutzbar."""
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

    @commands.hybrid_command(name="ping", description="Zeigt die Latenz des Bots und der Datenbank")
    async def ping(self, ctx: commands.Context) -> None:
        start = time.perf_counter()
        db_ok = await self.bot.db.ping()
        db_ms = round((time.perf_counter() - start) * 1000)
        db_text = f"{db_ms} ms" if db_ok else "❌ nicht erreichbar"
        await ctx.send(f"🏓 Pong! Gateway: **{round(self.bot.latency * 1000)} ms** · Datenbank: **{db_text}**")

    @commands.hybrid_command(name="help", description="Listet alle Befehle auf")
    async def help(self, ctx: commands.Context) -> None:
        lines: list[str] = []
        for cmd in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            if isinstance(cmd, app_commands.Group):
                for sub in cmd.commands:
                    lines.append(f"`/{cmd.name} {sub.name}` – {sub.description}")
            else:
                lines.append(f"`/{cmd.name}` – {cmd.description}")
        embed = discord.Embed(title="📖 Befehle", description="\n".join(lines), color=discord.Color.blurple())
        prefix = (await self.bot.get_prefix(ctx.message))[-1] if ctx.message else "!"
        embed.set_footer(text=f"Allgemeine Befehle gehen auch mit Prefix, z. B. {prefix}ping")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Informationen über diesen Server")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        g = ctx.guild
        embed = discord.Embed(title=g.name, color=discord.Color.blurple())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "–")
        embed.add_field(name="Mitglieder", value=str(g.member_count))
        embed.add_field(name="Boost-Level", value=f"{g.premium_tier} ({g.premium_subscription_count} Boosts)")
        embed.add_field(name="Kanäle", value=f"{len(g.text_channels)} Text · {len(g.voice_channels)} Voice")
        embed.add_field(name="Rollen", value=str(len(g.roles)))
        embed.add_field(name="Erstellt", value=discord.utils.format_dt(g.created_at, "D"))
        embed.set_footer(text=f"ID: {g.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="userinfo", description="Informationen über ein Mitglied")
    @commands.guild_only()
    @app_commands.describe(member="Mitglied (Standard: du selbst)")
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        member = member or ctx.author
        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        embed = discord.Embed(title=str(member), color=member.color if member.color.value else discord.Color.blurple())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Anzeigename", value=member.display_name)
        embed.add_field(name="Bot", value="Ja" if member.bot else "Nein")
        embed.add_field(name="Account erstellt", value=discord.utils.format_dt(member.created_at, "R"))
        if member.joined_at:
            embed.add_field(name="Beigetreten", value=discord.utils.format_dt(member.joined_at, "R"))
        embed.add_field(name=f"Rollen ({len(roles)})", value=" ".join(roles[:15]) or "–", inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="avatar", description="Zeigt den Avatar eines Mitglieds")
    @app_commands.describe(user="Benutzer (Standard: du selbst)")
    async def avatar(self, ctx: commands.Context, user: Optional[discord.User] = None) -> None:
        user = user or ctx.author
        embed = discord.Embed(title=f"Avatar von {user.display_name}", color=discord.Color.blurple())
        embed.set_image(url=user.display_avatar.with_size(1024).url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="botinfo", description="Informationen und Statistiken zum Bot")
    async def botinfo(self, ctx: commands.Context) -> None:
        row = await self.bot.db.fetchone("SELECT COUNT(*) AS total FROM command_log")
        embed = discord.Embed(title=f"🤖 {self.bot.user.name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Server", value=str(len(self.bot.guilds)))
        embed.add_field(name="Befehle ausgeführt", value=str(row["total"] if row else 0))
        embed.add_field(name="Online seit", value=discord.utils.format_dt(self.bot.started_at, "R"))
        embed.add_field(name="Python", value=platform.python_version())
        embed.add_field(name="discord.py", value=discord.__version__)
        embed.add_field(name="Datenbank", value="MariaDB ✅" if await self.bot.db.ping() else "MariaDB ❌")
        await ctx.send(embed=embed)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(General(bot))
