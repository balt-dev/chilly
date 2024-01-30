"""Data cog."""
# pylint: disable=import-error, too-few-public-methods

import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from discord.ext import commands

from src.classes import Context, TileData, Tiling, WorldData, CustomError, SpriteJSONEncoder
from src.constants import COLOR_NAMES

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot:
        """Dummy"""

# Store this outside of the cog so that it won't refresh when the cog's reloaded
data = {}
object_keys = {}
key_objects = {}


class DataCog(commands.Cog, name="Data"):
    """Holds the data for the bot."""
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    @staticmethod
    async def load_sprite(world: str, name: str, obj: dict):
        """Loads a single sprite from its serialized representation."""
        if isinstance(obj["color"], str):
            obj["color"] = COLOR_NAMES[obj["color"]]
        tile_data = TileData(
            color=obj["color"],
            tiling=Tiling.from_string([obj["tiling"]]),
            world=world,
            author=obj["author"],
            sprite=obj.get("sprite", name),
            tile_index=obj.get("tile")
        )
        data[world].sprites[name] = tile_data

    @staticmethod
    def parse_value(value: str):
        """Parse a value from values.lua."""
        value = value.strip()
        if value.startswith('"'):
            # String
            return value[1:-1]
        if value in {"true", "false"}:
            # Boolean
            return value == "true"
        if re.match(r"-?\d+", value):
            # Integer
            return int(value)
        if value.startswith("{"):
            # Array
            values = value[1:-1].split(",")
            return tuple(DataCog.parse_value(v) for v in values)
        return None

    @staticmethod
    def load_sprites(world: str):
        """Loads a single world's sprite data."""
        sprites_path = Path("data", world, "sprites.json")
        if sprites_path.exists():
            with open(sprites_path, "r", encoding="utf-8") as file:
                obj = json.load(file)
            for name, attributes in obj.items():
                DataCog.load_sprite(world, name, attributes)

    @staticmethod
    async def load_data(world_name: str | None = None, kind: Literal["sprites"] | None = None):
        """Load all data from a specified directory, or all of them if not specified."""
        worlds = []
        if world_name is None:
            for path in Path("data").glob("*/"):
                worlds.append(path.name)
        else:
            worlds.append(world_name)
        for world in worlds:
            data[world] = WorldData()
            if kind is None or kind == "sprites":
                DataCog.load_sprites(world)

    @commands.command()
    async def load(self, ctx: Context, kind: Literal["sprites"] = None, world: str = None):
        """Loads data of all worlds."""
        await ctx.typing()
        await DataCog.load_data(world, kind)
        await ctx.reply("Reloaded data!")

    @commands.command()
    async def dumpvanilla(self, ctx: Context):
        """Loads assets from Baba Is You."""
        await ctx.typing()
        path: str | None = self.bot.config.get("babapath", None)
        if path is None:
            return await ctx.error("No baba path is set in the bot's configuration!")
        path: Path = Path(path, "Data")
        DataCog.dump_vanilla_json(path)
        shutil.copytree(path / "Palettes", "data/vanilla/palettes", dirs_exist_ok=True)
        shutil.copytree(path / "Sprites", "data/vanilla/sprites", dirs_exist_ok=True)
        await ctx.reply("Dumped vanilla assets to bot folder.")

    @staticmethod
    def parse_tile(data_string):
        """Parse a single tile from its lua data."""
        tile_data = {}
        for match in re.finditer(r"(\w+) = ((?:(?!,\n).)+)", data_string):
            key, value = match.groups()
            tile_data[key] = DataCog.parse_value(value)
        if tile_data.get("does_not_exist", False):
            return None, None
        json_data = {
            'color': tile_data.get("colour_active", tile_data["colour"]),
            'tiling': Tiling(tile_data["tiling"]).to_string(),
            'author': "Hempuli"
        }
        if tile_data["name"] != tile_data.get("sprite", tile_data["name"]):
            json_data['sprite'] = tile_data["sprite"]
        if tile := tile_data.get("tile", False):
            json_data["tile"] = tile
        if layer := tile_data.get("layer", False):
            json_data["layer"] = layer
        color_values = {value: key for key, value in COLOR_NAMES.items()}
        json_data["color"] = color_values.get(tuple(json_data["color"]), json_data["color"])
        return tile_data["name"], json_data

    @staticmethod
    def dump_vanilla_json(path: Path):
        """Dump vanilla data into vanilla/sprites.json."""
        # values.lua contains the data about which color (on the palette) is
        # associated with each tile.
        with open(path / "values.lua", errors='ignore', encoding="utf-8") as fp:
            values_data = fp.read()

        start = values_data.find("tileslist =\n{") + 13  # 13 being the length of the search string
        end = values_data.find("\n}\n", start)

        if start >= end:
            raise CustomError("Failed to extract tileslist from values.lua!")

        vanilla_json = {}

        tileslist = values_data[start:end]
        for tile in re.finditer(
                r"(\w+) =\n\t{((?:(?!\n\t},).)+)",
                tileslist,
                flags=re.S
        ):
            object_id, data_string = tile.groups()
            # Special case
            if object_id == "edge":
                continue
            data_string = data_string[:-1]  # Strip trailing comma
            name, json_data = DataCog.parse_tile(data_string)
            if name is None:
                continue
            json_data["object"] = object_id
            vanilla_json[name] = json_data

        # editor_objectlist.lua contains general data about most tiles.
        with open(
                path / "Editor" / "editor_objectlist.lua",
                errors='ignore',
                encoding="utf-8"
        ) as fp:
            objlist_data = fp.read()

        start = objlist_data.find("editor_objlist = {") + 18
        end = objlist_data.find("\n}", start)

        if start >= end:
            raise CustomError("Failed to extract editor_objlist from editor_objectlist.lua!")

        tileslist = objlist_data[start:end]
        for tile in re.finditer(
                r"\[\d+] = {((?:(?!\n\t},).)+)",
                tileslist,
                flags=re.S
        ):
            data_string, = tile.groups()
            data_string = data_string[:-1]  # Strip trailing comma
            name, json_data = DataCog.parse_tile(data_string)
            if name is None:
                continue
            vanilla_json[name] = vanilla_json.get(name, {}) | json_data

        # Get patched in sprites
        with open("data/vanilla-ext.json", "r", encoding="utf-8") as ext:
            ext = json.load(ext)
            vanilla_json |= ext

        with open("data/vanilla/sprites.json", "w+", encoding="utf-8") as vanilla:
            # json.dump doesn't play nice with overriding encode
            vanilla.write(json.dumps(
                vanilla_json, check_circular=False, cls=SpriteJSONEncoder
            ))


async def setup(bot: Bot):
    """Cog setup"""
    cog = DataCog(bot)
    bot.data = cog
