from typing import TYPE_CHECKING

from discord.ext import commands

from src.classes import Context

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot: pass


class OwnerCog(commands.Cog, name="Owner-only", ):
    """Holds commands only owners of the bot can run."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command(aliases=["rr"])
    async def reload(self, ctx: Context):
        """Reloads all cogs."""
        await self.bot.refresh_cogs()
        await ctx.reply("Cogs refreshed!")


async def check_for_ownership(ctx: Context):
    return await ctx.bot.is_owner(ctx.message.author)


async def setup(bot: Bot):
    cog = OwnerCog(bot)
    cog.bot_check = check_for_ownership
    await bot.add_cog(cog)
