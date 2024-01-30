from discord.ext import commands

from typing import TYPE_CHECKING

from src.classes import Context

if TYPE_CHECKING:
    from main import Bot


class ParserCog(commands.Cog, name="Parsing", ):
    """Holds methods relating to parsing tilemaps."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    def parse(self, raw_scene: str) -> Scene:
        """Parses a whole scene from a raw string, including flags."""


async def setup(bot: Bot):
    cog = ParserCog(bot)
    await bot.add_cog(cog)
