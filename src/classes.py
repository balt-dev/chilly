# pylint: disable=import-error, too-few-public-methods
"""Assorted classes."""
from enum import Enum, auto
from json import JSONEncoder
from typing import Any, Tuple, Self

from attr import Factory, define
from discord.ext import commands
from PIL.Image import Image

from src.constants import COLOR_NAMES, TILE_SPACING


class CustomError(Exception):
    """Custom error class for passing back feedback to the user."""


class Color:
    """A color. May be palette indexed or RGB."""
    r: int
    g: int
    b: int | None
    __slots__ = ('r', 'g', 'b')

    def clone(self) -> Self:
        return Color.from_tuple((self.r, self.g, self.b))

    def __repr__(self):
        if self.b is None:
            return f"{self.r},{self.g}"
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @classmethod
    def from_tuple(cls, rgb: tuple[int, int, int] | tuple[int, int]) -> Self:
        v = cls("0,0")
        v.r, v.g = rgb[:2]
        if len(rgb) > 2:
            v.b = rgb[2]
        else:
            v.b = None
        return v

    def __init__(self, index: str):
        self.b = None
        err = CustomError(
            f"Failed to parse `{index}` as a color.")
        if "," in index:
            x, y = index.split(",", 1)
            try:
                self.r = int(x)
                self.g = int(y)
            except ValueError as e:
                raise err from e
        elif index in COLOR_NAMES:
            self.r, self.g = COLOR_NAMES[index]
        elif index.startswith("#"):
            try:
                hex_color = index[1:]
                if len(hex_color) != 6:
                    raise ValueError(
                        "Hexadecimal color must be exactly 6 characters long")
                rgb = int(hex_color, base=16)
                self.r, self.g, self.b = \
                    (rgb & 0xFF0000) >> 16, (rgb & 0xFF00) >> 8, (rgb & 0xFF)
            except ValueError as e:
                raise err from e
        else:
            raise err

    def __iter__(self):
        if self.b is None:
            return (self.r, self.g).__iter__()
        return (self.r, self.g, self.b).__iter__()


@define
class Position:
    """A tile position."""
    x: int
    y: int
    z: int
    t: int

    def __iter__(self):
        return (self.x, self.y, self.z, self.t).__iter__()

    def __hash__(self):
        return hash((self.x, self.y, self.z, self.t))

    def __lt__(self, other):
        if self.z != other.z:
            return self.z < other.z
        if self.y != other.y:
            return self.y < other.y
        if self.x != other.x:
            return self.x < other.x
        return False


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
    color: Color = Color("white")
    sprite: str = "error"
    world: str = "vanilla"
    tiling: Tiling = Tiling.NONE
    author: str = "Hempuli"
    tile_index: tuple[int, int] | None = None
    object_id: str | None = None
    layer: int | None = None

    def dump(self) -> dict:
        """Dumps this tile data into a dictionary suited for JSON."""
        return {
            "color": (self.color.r, self.color.g, self.color.b),
            "sprite": self.sprite,
            "world": self.world,
            "tiling": self.tiling,
            "author": self.author,
            "tile_index": self.tile_index,
            "object_id": self.object_id,
            "layer": self.layer
        }

    def clone(self) -> Self:
        """Clones this tile data into a new object."""
        return TileData(self.color.clone(), self.sprite, self.world, self.tiling, self.author, self.tile_index, self.object_id, self.layer)


@define
class Database:
    """A holding class for the database."""
    sprites: dict[str, TileData] = Factory(dict)
    palettes: dict[str, str] = Factory(dict)

    def dump(self) -> dict:
        """Dump the database to a dictionary."""
        data = {}
        data |= {name: sprite.dump() for name, sprite in self.sprites.items()}
        data |= {name: world for name, world in self.palettes.items()}
        return data


class SpriteJSONEncoder(JSONEncoder):
    """A custom JSON encoder to make generated sprites.json files look prettier."""

    indentation: int

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indentation = 0

    def default(self, o):
        if isinstance(o, Tiling):
            return o.value
        return super().default(o)

    def encode(self, o):
        if isinstance(o, list):
            return f"[{', '.join(str(v) for v in o)}]"
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
class VariantData:
    """The metadata of a variant."""
    names: Tuple[str, ...]
    description: str
    example: str
    arguments: Tuple[type, ...] = ()
    defaults: Tuple[Any | None, ...] = ()

    def __hash__(self):
        return hash((self.names, self.description, self.example,
                     self.arguments, self.defaults))


@define
class Variant:
    """A single variant. May be unparsed."""
    name: str
    arguments: list[Any | None] = Factory(list)

    def __repr__(self):
        return f":{self.name}" + (
            "/" + "/".join(
                str(arg) for arg in self.arguments
            ) if len(self.arguments) else ""
        )


class CompositingMode(Enum):
    NORMAL = auto()

    @classmethod
    def _missing_(cls, value):
        if value == "normal":
            return cls.NORMAL
        # noinspection PyProtectedMember
        return super()._missing_(value)


@define
class TileAttributes:
    """The attributes of a single tile."""

    frame: tuple[int, int] | None = None
    sprite_name: str = "error"
    color: tuple[int, int] | tuple[int, int, int] | None = None
    palette: str | None = None
    compositing_mode: CompositingMode = CompositingMode.NORMAL
    displacement: tuple[int, int] = (0, 0)


@define
class Tile:
    """A single tile in a scene."""

    name: str
    variants: list[Variant] = Factory(list)
    data: TileData | None = None

    attrs: TileAttributes = Factory(TileAttributes)
    sprite: tuple[str, str] | tuple[Image, Image, Image] | None = None


class TileGrid:
    """A sparse grid of tiles where no two tiles can share the same position."""
    tiles: dict[Position, Tile]
    width: int
    height: int
    length: int
    spacing: int
    __slots__ = "tiles", "width", "height", "length", "spacing"

    def __init__(self):
        self.tiles = {}
        self.width = 0
        self.height = 0
        self.length = 1
        self.spacing = TILE_SPACING

    def __iter__(self):
        return self.tiles.items().__iter__()

    @staticmethod
    def _check_position(pos) -> Position:
        if not isinstance(pos, (tuple, Position)):
            raise TypeError(f"expected position for indexing, got {type(pos).__name__}")
        return Position(*pos)

    def __getitem__(self, item: Position):
        item = self._check_position(item)
        return self.tiles[item]

    def __setitem__(self, key, value):
        key = self._check_position(key)
        if not isinstance(value, Tile):
            raise TypeError("expected Tile for setting grid")
        self.tiles[key] = value


class ImageFormat(Enum):
    """An image format to use in a render."""
    GIF = "gif"
    # TODO: More image formats!


@define
class Scene:

    """A full scene."""
    tiles: TileGrid
    flags: dict[str, Any]

    tile_spacing: int = 24
    connect_borders: bool = False
    format: ImageFormat = ImageFormat.GIF
    image_size: int = 2


class ArgumentError(Exception):
    """Raised when an argument in a variant fails to parse."""
