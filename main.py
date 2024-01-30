import asyncio
import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from os import environ
from sys import stderr

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.classes import Context
from src.cogs.data import DataCog
from src.cogs.parser import ParserCog


class Bot(commands.Bot):
    """The main class of the bot."""
    renderer: None
    parser: ParserCog
    data: DataCog
    started: datetime
    loaded: bool = False
    config: dict

    async def refresh_cogs(self):
        """Load or reload all cogs."""
        cogs = Path("src/cogs").glob("*.py")
        cogs = [".".join(path.parts).removesuffix(".py") for path in cogs]
        if self.loaded:
            await asyncio.gather(*(self.reload_extension(cog, package="main") for cog in cogs))
        else:
            await asyncio.gather(*(self.load_extension(cog, package="main") for cog in cogs))
        self.loaded = True

    async def get_context(self, message: discord.Message, **kwargs) -> Context:
        return await super().get_context(message, cls=Context)

    def __init__(self):
        # Parse the configuration
        with open("config.json", "r") as conf:
            config = json.load(conf)
        self.started = datetime.utcnow()
        self.config = config
        super().__init__(
            command_prefix=config["prefix"],
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False),
            intents=discord.Intents(messages=True, reactions=True, message_content=True),
            member_cache_flags=discord.MemberCacheFlags.none(),
            max_messages=None,
            chunk_guilds_at_startup=False
        )
        # Load cogs
        asyncio.run(self.refresh_cogs())


def main():
    load_dotenv()
    token = environ["CHILL_TOKEN"]
    try:
        bot = Bot()
    except (JSONDecodeError, KeyError):
        stderr.write("Failed to decode configuration! Check your config file.\n")
        return
    except FileNotFoundError:
        stderr.write("Configuration file not found!\n")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
