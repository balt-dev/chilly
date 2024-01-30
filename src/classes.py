# pylint: disable=import-error, too-few-public-methods
"""Assorted classes."""
from enum import Enum
from json import JSONEncoder
from typing import Any, Optional

from PIL.Image import Image
from attr import define, Factory
from discord.ext import commands


class Context(commands.Context):
    """Custom context class."""
    async def error(self, *args, **kwargs):
        """Special formatting for errors"""
        await self.message.add_reaction("\u26A0")  # warning sign
        await self.reply(*args, **kwargs)


class Tiling(Enum):
    """An enumeration of possible tiling modes for tiles."""
    NONE = -1
    DIRECTIONAL = 0
    AUTOTILED = 1
    CHARACTER = 2
    ANIMDIR = 3
    ANIMATED = 4

    @staticmethod
    def from_string(string):
        """Gets a tiling method from a string."""
        return {
            "none": Tiling.NONE,
            "directional": Tiling.DIRECTIONAL,
            "autotiled": Tiling.AUTOTILED,
            "character": Tiling.CHARACTER,
            "animdir": Tiling.ANIMDIR,
            "animated": Tiling.ANIMATED
        }[string]

    def to_string(self):
        """Serializes this tiling to a string."""
        return {
            Tiling.NONE: "none",
            Tiling.DIRECTIONAL: "directional",
            Tiling.AUTOTILED: "autotiled",
            Tiling.CHARACTER: "character",
            Tiling.ANIMDIR: "animdir",
            Tiling.ANIMATED: "animated"
        }[self]


@define
class TileData:
    """A holding class for tile data."""
    color: tuple[int, int] | tuple[int, int, int] = (0, 3)
    sprite: str = "error"
    world: str = "vanilla"
    tiling: Tiling = Tiling.NONE
    author: str = "Hempuli"
    tile_index: tuple[int, int] | None = None
    object_id: str | None = None
    layer: int | None = None


@define
class WorldData:
    """A holding class for the data of a world."""
    sprites: dict[str, TileData] = Factory(dict)


class CustomError(Exception):
    """Custom error class for passing back feedback to the user."""


class SpriteJSONEncoder(JSONEncoder):
    """A custom JSON encoder to make generated sprites.json files look prettier."""

    indentation: int

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indentation = 0

    def encode(self, o):
        if isinstance(o, list):
            return f"[{', '.join(list)}]"
        if isinstance(o, dict):
            return self.encode_dict(o)
        return super().encode(o)

    def encode_dict(self, o):
        """Encode a dictionary."""
        if not o:
            return "{}"
        self.indentation += 1
        indent = "\t" * self.indentation
        out = [
            f"{indent}{self.encode(key)}: {self.encode(value)}"
            for key, value in o.items()
        ]
        self.indentation -= 1
        indent = "\t" * self.indentation
        return "{\n" + ",\n".join(out) + "\n" + indent + "}"


@define
class Variant:
    """A single variant. May be unparsed."""
    name: str
    arguments: list[Any] = Factory(list)


@define
class Tile:
    """A single tile in a scene."""

    x: float
    y: float
    z: float
    t: float

    name: str
    variants: list[Variant] = Factory(list)
    sprite: Optional[Image] = None


@define
class Scene:
    """A full scene."""
    tiles: set[Tile]
