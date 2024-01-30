# pylint: disable=import-error, too-few-public-methods
"""Owner-only stuff."""

from typing import TYPE_CHECKING

from discord.ext import commands

from src.classes import Context

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot:
        """Dummy"""


class OwnerCog(commands.Cog, name="Owner-only", ):
    """Holds commands only owners of the bot can run."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    async def bot_check(self, ctx: Context) -> bool:
        """Check that the author is an owner."""
        return await ctx.bot.is_owner(ctx.message.author)

    @commands.command(aliases=["rr"])
    async def reload(self, ctx: Context):
        """Reloads all cogs."""
        await self.bot.refresh_cogs()
        await ctx.reply("Cogs refreshed!")


async def setup(bot: Bot):
    """Cog setup."""
    cog = OwnerCog(bot)
    await bot.add_cog(cog)
