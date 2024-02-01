# pylint: disable=import-error, too-few-public-methods
"""General commands."""
from typing import TYPE_CHECKING

from discord.ext import commands

from src.classes import Context

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot:
        """Dummy"""


class GeneralCog(commands.Cog, name="General"):
    """General commands and functions."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: Context):
        """Sends back the latency of the bot."""
        await ctx.reply(f"Pong! Took {self.bot.latency*1000:.2f}ms.")


async def setup(bot: Bot):
    """Cog setup."""
    await bot.add_cog(GeneralCog(bot))
