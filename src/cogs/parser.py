"""Parsing stuff."""
# pylint: disable=import-error, too-few-public-methods
from typing import TYPE_CHECKING
from discord.ext import commands
from src.classes import Scene

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot:
        """Dummy"""


class ParserCog(commands.Cog, name="Parsing"):
    """Holds methods relating to parsing tilemaps."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    def parse(self, raw_scene: str) -> Scene:
        """Parses a whole scene from a raw string, including flags."""
        raise NotImplementedError("TODO: Parsing")


async def setup(bot: Bot):
    """Cog setup"""
    cog = ParserCog(bot)
    await bot.add_cog(cog)
