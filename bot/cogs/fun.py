"""Fun commands: dice, coin flip, magic 8-ball, polls."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import PelicanBot

EIGHT_BALL = [
    "Yes, definitely! ✅",
    "Without a doubt.",
    "Most likely.",
    "Signs point to yes.",
    "Ask again later. 🤔",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "Don't count on it.",
    "My sources say no. ❌",
    "Very doubtful.",
]
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class Fun(commands.Cog):
    def __init__(self, bot: "PelicanBot") -> None:
        self.bot = bot

    @app_commands.command(name="roll", description="Rolls one or more dice")
    @app_commands.describe(sides="Number of sides (default: 6)", dice="Number of dice (default: 1)")
    async def roll(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000] = 6,
        dice: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        results = [random.randint(1, sides) for _ in range(dice)]
        detail = f" ({' + '.join(map(str, results))})" if dice > 1 else ""
        await interaction.response.send_message(f"🎲 {dice}d{sides}: **{sum(results)}**{detail}")

    @app_commands.command(name="coinflip", description="Flips a coin")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"🪙 **{random.choice(['Heads', 'Tails'])}**!")

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question")
    @app_commands.checks.cooldown(1, 5.0)
    async def eight_ball(self, interaction: discord.Interaction, question: app_commands.Range[str, 3, 200]) -> None:
        embed = discord.Embed(color=discord.Color.dark_purple())
        embed.add_field(name="❓ Question", value=question, inline=False)
        embed.add_field(name="🎱 Answer", value=random.choice(EIGHT_BALL), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Creates a poll with reactions")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 30.0)
    @app_commands.describe(question="The question", options="Answers separated by ; (empty = yes/no)")
    async def poll(
        self, interaction: discord.Interaction, question: app_commands.Range[str, 3, 200], options: str | None = None
    ) -> None:
        choices = [o.strip() for o in (options or "").split(";") if o.strip()]
        if len(choices) == 1 or len(choices) > 10:
            await interaction.response.send_message("Please provide 2–10 answers separated by `;`.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.gold())
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")
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
