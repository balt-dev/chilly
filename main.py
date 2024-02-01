"""Main executable of the bot."""
# pylint: disable=import-error, too-few-public-methods

import asyncio
import json
from datetime import datetime
from json import JSONDecodeError
from os import environ
from pathlib import Path
from sys import stderr

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.classes import Context, Database
from src.cogs.data import DataCog
from src.cogs.parser import ParserCog
from src.cogs.render import RendererCog
from src.cogs.variants import VariantRegistry


class Bot(commands.Bot):
    """The main class of the bot."""
    renderer: RendererCog
    parser: ParserCog
    data: DataCog
    database: Database
    variant_registry: VariantRegistry
    started: datetime
    loaded: bool = False
    config: dict
    ready: bool = False

    async def refresh_cogs(self):
        """Load or reload all cogs."""
        cogs = Path("src/cogs").glob("*.py")
        cogs = [".".join(path.parts).removesuffix(".py") for path in cogs if path.stem != "__init__"]
        if self.loaded:
            await asyncio.gather(*(self.reload_extension(cog, package="main") for cog in cogs))
        else:
            await asyncio.gather(*(self.load_extension(cog, package="main") for cog in cogs))
        self.loaded = True

    async def get_context(self, message: discord.Message, **kwargs) -> Context:
        """Alter the context to our own custom class."""
        # false alarm
        # pylint: disable=arguments-differ
        return await super().get_context(message, cls=Context, **kwargs)

    async def startup(self):
        """Startup stuff."""
        print("Loading cogs...")
        await self.refresh_cogs()
        print("Loading data...")
        self.database = Database()
        await self.data.load_data()
        print("Bot is ready!")
        self.ready = True

    def __init__(self):
        self.ready = False
        # Parse the configuration
        with open("config.json", "r", encoding="utf-8") as conf:
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
        asyncio.run(self.startup())


def main():
    """Entrypoint"""
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
