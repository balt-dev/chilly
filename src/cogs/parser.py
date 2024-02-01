"""Parsing stuff."""
# pylint: disable=import-error, too-few-public-methods
import re
from typing import TYPE_CHECKING

from discord.ext import commands

from src.classes import Scene, Tile, Variant, Position, TileGrid, Tiling, Color
from src.constants import TILING_VARIANTS

if TYPE_CHECKING:
    from main import Bot
else:

    class Bot:
        """Dummy"""


class ParserCog(commands.Cog, name="Parsing"):
    """Holds methods relating to parsing tilemaps."""
    bot: Bot

    FLAG_PATTERN: re.Pattern = re.compile(r"--(?P<key>\w+)(?:=(?P<value>\S+))? ?")
    SPACE_PATTERN: re.Pattern = re.compile(r"(?<!(?<!\\)\\) ")
    STACK_PATTERN: re.Pattern = re.compile(r"(?<!(?<!\\)\\)&")
    STEP_PATTERN: re.Pattern = re.compile(r"(?<!(?<!\\)\\)>")

    def __init__(self, bot: Bot):
        self.bot = bot

    def parse(self, raw_scene: str) -> Scene:
        """Parses a whole scene from a raw string, including flags."""
        # Parse flags
        flags = {}
        while (
            match := re.match(ParserCog.FLAG_PATTERN, raw_scene)
        ) is not None:
            raw_scene = raw_scene[match.end():]  # Strip the flag
            key, value = match.group("key", "value")
            if value is None:
                value = True
            flags[key] = value
        tiles = TileGrid()
        # Parse grid
        for y, row in enumerate(raw_scene.split('\n')):
            tiles.height = max(tiles.height, y)
            for x, stack in enumerate(re.split(ParserCog.SPACE_PATTERN, row)):
                tiles.width = max(tiles.width, x)
                for z, cell in enumerate(
                        re.split(ParserCog.STACK_PATTERN, stack)):
                    last_tile = None
                    for t, raw_tile in enumerate(
                            re.split(ParserCog.STEP_PATTERN, cell)):
                        # Parse a single tile
                        tiles.length = max(tiles.length, t + 1)
                        tile, position = self.parse_tile(
                            tiles, raw_tile, (x, y, z, t)
                        )
                        if tile.name == ".":
                            # Empty tile, continue
                            last_tile = None
                            continue
                        if not tile.name:
                            # Tile name is empty, use last tile
                            if last_tile is None:
                                continue
                            tile.name = last_tile.name
                        last_tile = tile
                        tiles[position] = tile
        return Scene(tiles, flags)

    def parse_tile(
            self,
            grid: TileGrid,
            raw_tile: str,
            position: tuple[int, int, int, int]
    ) -> (Tile, Position):
        """Parses a single tile, applying tile variants."""
        tile_name, *raw_variants = raw_tile.split(":")
        variants = []
        for raw_variant in raw_variants:
            var_name, *arguments = raw_variant.split("/")
            variant = Variant(var_name, arguments)
            self.bot.variant_registry.parse(variant)
            variants.append(variant)
        tile = Tile(tile_name, variants)
        tile.data = self.bot.data.database.sprites.get(tile.name, None)
        pos = Position(
            float(position[0]), float(position[1]), float(position[2]), float(position[3])
        )
        pos = ParserCog.build_attributes(grid, tile, pos)
        return tile, pos

    @staticmethod
    def build_attributes(grid: TileGrid, tile: Tile, pos: Position) -> Position:
        """Build the attributes of a tile."""
        variants = []
        x, y, z, t = pos
        attrs = tile.attrs
        # Apply tile-level variants
        for variant in tile.variants:
            if variant.name == "right":
                attrs.frame = 0, 0
            elif variant.name == "up":
                attrs.frame = 8, 8
            elif variant.name == "left":
                attrs.frame = 16, 16
            elif variant.name == "down":
                attrs.frame = 24, 24
            elif variant.name == "sleep":
                sleep_frame = (attrs.frame[0] - 1) % 32
                attrs.frame = sleep_frame, sleep_frame
            elif variant.name == "displace":
                # Turn grid-space values to pixel-space values
                dx, dy = variant.arguments
                dx /= grid.spacing
                dy /= grid.spacing
                x += dx
                y += dy
            elif variant.name == "tiling":
                bitfield = 0
                for arg in variant.arguments:
                    # Construct a bitfield of the tile's neighbors
                    # Right, up, left, down, up-right, up-left, down-left, down-right
                    bitfield |= (
                        (arg in ("r", "dr", "ur")) << 7 |
                        (arg in ("u", "ul", "ur")) << 6 |
                        (arg in ("l", "ul", "dl")) << 5 |
                        (arg in ("d", "dl", "dr")) << 4 |
                        (arg == "ur") << 3 |
                        (arg == "ul") << 2 |
                        (arg == "dl") << 1 |
                        (arg == "dr")
                    )
                attrs.frame = TILING_VARIANTS.get(bitfield), \
                    TILING_VARIANTS[bitfield & 0b11110000]
            elif variant.name == "color":
                # Set the color to white so color isn't applied twice
                tile.attrs.color = Color.from_tuple((255, 255, 255))
                # Put this back for later
                variants.append(variant)
            else:
                variants.append(variant)
        tile.attrs = attrs
        tile.variants = variants
        return Position(x, y, z, t)

    @staticmethod
    def is_adjacent(pos: Position, tile: Tile, grid: TileGrid, tile_borders=False) -> bool:
        """Check if a tile is next to a joining tile."""
        joining_tiles = (tile.name, "level", "border")
        if (
            pos.x < 0 or
            pos.y < 0 or
            pos.x >= grid.width or
            pos.y >= grid.width
        ):
            return tile_borders
        return grid[pos].name in joining_tiles

    @staticmethod
    def connect_autotiled(scene: Scene):
        """Connects all autotiled tiles in a scene."""
        for pos, tile in scene.tiles:
            if tile.attrs.frame is not None or tile.data is None:
                continue
            if tile.data.tiling != Tiling.AUTOTILED:
                tile.attrs.frame = 0, 0
                continue
            # Check all 8 directions
            r, u, l, d = Position(*pos), Position(*pos), Position(*pos), Position(*pos)
            r.x += 1
            u.y -= 1
            l.x -= 1
            d.y += 1
            ur, ul, dl, dr = Position(*u), Position(*l), Position(*d), Position(*r)
            ur.x    += 1
            ul.y    -= 1
            dl.x    -= 1
            dr.y    += 1
            r = ParserCog.is_adjacent(r, tile, scene.tiles, scene.connect_borders)
            u = ParserCog.is_adjacent(u, tile, scene.tiles, scene.connect_borders)
            l = ParserCog.is_adjacent(l, tile, scene.tiles, scene.connect_borders)
            d = ParserCog.is_adjacent(d, tile, scene.tiles, scene.connect_borders)
            ur = u and r and ParserCog.is_adjacent(ur, tile, scene.tiles, scene.connect_borders)
            ul = u and l and ParserCog.is_adjacent(ul, tile, scene.tiles, scene.connect_borders)
            dl = d and l and ParserCog.is_adjacent(dl, tile, scene.tiles, scene.connect_borders)
            dr = d and r and ParserCog.is_adjacent(dr, tile, scene.tiles, scene.connect_borders)
            bitfield = (
                r << 7 |
                u << 6 |
                l << 5 |
                d << 4 |
                ur << 3 |
                ul << 2 |
                dl << 1 |
                dr
            )
            # This is always guaranteed to exist
            fallback = TILING_VARIANTS[bitfield & 0b11110000]
            tile.attrs.frame = (
                TILING_VARIANTS.get(bitfield, fallback),
                fallback
            )


async def setup(bot: Bot):
    """Cog setup"""
    cog = ParserCog(bot)
    bot.parser = cog
