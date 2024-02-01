import os
import traceback
from io import BytesIO

import discord
from discord.ext import commands

from main import Bot
from src.classes import ArgumentError, Context, CustomError


class ErrorHandler(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: Exception):
        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (
            commands.CommandNotFound,
            commands.NotOwner,
            commands.CheckFailure
        )

        if isinstance(error, ignored):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, commands.CommandOnCooldown):
            if ctx.author.id == self.bot.owner_id:
                return await ctx.reinvoke()
            return await ctx.error(str(error))

        if isinstance(
            error,
            (commands.ConversionError, commands.BadArgument, commands.ArgumentParsingError)
        ):
            return await ctx.error(
                "The arguments you provided aren't valid for that command. "
                "Check the help command for the proper arguments."
            )

        if isinstance(error, CustomError):
            message: str = error.args[0]
            message = message.replace("`", "")
            return await ctx.error(message)
        
        if isinstance(error, ArgumentError):
            value = str(error.args[1]).replace("`", "")
            variant = str(error.args[2]).replace("`", "")
            return await ctx.error(f"Failed to parse a `{error.args[0].__name__}` from `{value}`" \
                    f"in variant `{variant}`.")

        if isinstance(error, NotImplementedError):
            return await ctx.error(f"Something here isn't implemented yet.\n> {error.args[0]}")

        if isinstance(error, ArithmeticError):
            return await ctx.error(f'Something failed to calculate.\n> {error.args[0]}')

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.error(f"A required argument \"{error.param}\" is missing.")

        if isinstance(error, discord.errors.HTTPException):
            if error.status == 400:
                return await ctx.error(f"Something went wrong while I was making an HTTP request.\n`{error}`")
            if error.status == 429:
                return await ctx.error("I'm being ratelimited, wait a little.")
            if error.status == 503:
                return await ctx.error("I can't reach the HTTP server.")
            return await ctx.error(
                f"I ran into an HTTP error with code `{error.status}`.\n"
                f"> `{error}`"
            )

        traceback.print_exception(error)

        # Get and clean traceback
        trace = (
            '\n'.join(traceback.format_tb(error.__traceback__))
            .replace(os.getcwd(), os.path.curdir)
        )
        if os.name == "nt":
            trace = trace.replace(os.environ["USERPROFILE"], "")

        trace = f"[COMMAND]\n{ctx.message.content}\n\n" \
                f"[EXCEPTION]\n{error.__class__.__name__}: {error}\n\n" \
                f"[TRACEBACK]\n{trace}"

        buf = BytesIO(trace.encode("utf-8"))

        return await ctx.error(
            "***An uncaught error occurred while processing this command.***\n"
            "***Report this to the bot developer ASAP.***",
            file=discord.File(buf, filename="traceback.txt")
        )


async def setup(bot: Bot):
    await bot.add_cog(ErrorHandler(bot))
