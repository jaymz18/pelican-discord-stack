"""Fun-Commands: Würfeln, Münzwurf, 8-Ball, Umfragen."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import PelicanBot

EIGHT_BALL = [
    "Ja, auf jeden Fall! ✅",
    "Ohne Zweifel.",
    "Sehr wahrscheinlich.",
    "Die Zeichen stehen gut.",
    "Frag später noch einmal. 🤔",
    "Das kann ich jetzt nicht sagen.",
    "Konzentrier dich und frag erneut.",
    "Eher nicht.",
    "Meine Quellen sagen nein. ❌",
    "Sehr zweifelhaft.",
]
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class Fun(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    @app_commands.command(name="roll", description="Würfelt mit einem Würfel deiner Wahl")
    @app_commands.describe(sides="Anzahl der Seiten (Standard: 6)", dice="Anzahl Würfel (Standard: 1)")
    async def roll(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000] = 6,
        dice: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        results = [random.randint(1, sides) for _ in range(dice)]
        detail = f" ({' + '.join(map(str, results))})" if dice > 1 else ""
        await interaction.response.send_message(f"🎲 {dice}W{sides}: **{sum(results)}**{detail}")

    @app_commands.command(name="coinflip", description="Wirft eine Münze")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"🪙 **{random.choice(['Kopf', 'Zahl'])}**!")

    @app_commands.command(name="8ball", description="Stell der magischen Kugel eine Frage")
    @app_commands.checks.cooldown(1, 5.0)
    async def eight_ball(self, interaction: discord.Interaction, question: app_commands.Range[str, 3, 200]) -> None:
        embed = discord.Embed(color=discord.Color.dark_purple())
        embed.add_field(name="❓ Frage", value=question, inline=False)
        embed.add_field(name="🎱 Antwort", value=random.choice(EIGHT_BALL), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Erstellt eine Umfrage mit Reaktionen")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 30.0)
    @app_commands.describe(question="Die Frage", options="Antworten getrennt mit ; (leer = Ja/Nein)")
    async def poll(
        self, interaction: discord.Interaction, question: app_commands.Range[str, 3, 200], options: str | None = None
    ) -> None:
        choices = [o.strip() for o in (options or "").split(";") if o.strip()]
        if len(choices) == 1 or len(choices) > 10:
            await interaction.response.send_message("Bitte 2–10 Antworten angeben, getrennt mit `;`.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.teal())
        embed.set_footer(text=f"Umfrage von {interaction.user.display_name}")
        if choices:
            embed.description = "\n".join(f"{NUMBER_EMOJIS[i]} {c}" for i, c in enumerate(choices))
            reactions = NUMBER_EMOJIS[: len(choices)]
        else:
            reactions = ["👍", "👎"]

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for emoji in reactions:
            await message.add_reaction(emoji)


async def setup(bot: "PelicanBot") -> None:
    await bot.add_cog(Fun(bot))
