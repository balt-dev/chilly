"""Parsing stuff."""
import asyncio
import random
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
# pylint: disable=import-error, too-few-public-methods
from typing import TYPE_CHECKING, BinaryIO

import discord
import numpy as np
from PIL import Image
from discord.ext import commands

from src.classes import (
    Scene,
    Tile,
    TileGrid,
    Tiling,
    CustomError,
    Color,
    CompositingMode,
    Position,
    ImageFormat, Context, TileData
)

if TYPE_CHECKING:
    from main import Bot
else:
    class Bot:
        """Dummy"""

# Hold this here, so it doesn't get reloaded when the cog does
image_cache: dict[Path, Image] = {}


class RendererCog(commands.Cog, name="RendererCog"):
    """Holds logic behind rendering a scene."""
    bot: Bot
    cache_dirty: bool

    def __init__(self, bot: Bot):
        self.bot = bot
        self.cache_dirty = False

    def open_image(self, path: Path) -> Image.Image:
        """Open an image, using the cache if possible."""
        if path not in image_cache:
            self.cache_dirty = True
            with Image.open(path) as im:
                image_cache[path] = im.copy().convert("RGBA")
        return image_cache[path].copy()

    async def assign_sprites(self, grid: TileGrid):
        """Assign sprites to the tiles in a grid."""
        for _, tile in grid:
            tile: Tile
            await asyncio.sleep(0)  # Give the GIL some room to breathe
            if tile.attrs.frame is None:
                tile.attrs.frame = 0, 0
            if tile.name == "2":
                # Easter egg! Pick a random character tile
                tiles = [
                    (data.world, data.sprite)
                    for data in self.bot.data.database.sprites.values()
                    if data.tiling == Tiling.CHARACTER
                ]
                tile.sprite = random.choice(tiles)
                if tile.sprite is None:
                    raise CustomError("No character tiles are loaded!")
                if tile.attrs.color is None:
                    tile.attrs.color = Color("rosy")
            else:
                # Load the tile's sprite filename
                if tile.data is not None:
                    tile.sprite = tile.data.world, tile.data.sprite
            if tile.sprite is not None:
                # Construct paths for both the normal and fallback sprites
                image_path = Path("data", tile.sprite[0], "sprites", "_").with_suffix(".png")
                images = []
                for wobble_frame in range(1, 4):  # From 1 to 3
                    # Fall back to fallback animation frame, and if that doesn't exist,
                    # fall back to wobble frame 1
                    fallbacks = (
                        f"{tile.sprite[1]}_{tile.attrs.frame[0]}_{wobble_frame}",
                        f"{tile.sprite[1]}_{tile.attrs.frame[1]}_{wobble_frame}",
                        f"{tile.sprite[1]}_{tile.attrs.frame[0]}_1",
                        f"{tile.sprite[1]}_{tile.attrs.frame[1]}_1"
                    )
                    print(fallbacks)
                    for stem in fallbacks:
                        path = image_path.with_stem(stem)
                        if path.exists():
                            break
                    else:  # No fallback matched
                        raise CustomError(
                            f"Failed to find any sprites for `{tile.name}` "
                            f"at animation frame `{tile.attrs.frame[0]}`."
                        )
                    image = self.open_image(path)
                    images.append(image)
                tile.sprite = tuple(images)
            else:
                if not await self.generate_sprite(tile):
                    raise CustomError(f"There's no tile with the name `{tile.name}`.")
            # Apply sprite color
            color = tile.attrs.color or tile.data.color  # Fallback
            self.fix_color(tile.attrs.palette, color)
            tile.sprite = tuple(
                self.recolor(frame, tuple(color))
                for frame in tile.sprite
            )
            await self.apply_sprite_variants(tile)

    async def generate_sprite(self, tile):
        # TODO: Sprite generation
        return False

    async def apply_sprite_variants(self, tile: Tile):
        """Apply all sprite variants to a tile, removing them from its list."""
        variants = []
        for variant in tile.variants:
            # Apply variant to all 3 frames of sprite
            sprite_frames = []
            for frame in tile.sprite:
                await asyncio.sleep(0)  # Give the GIL some room to breathe
                # Get the colors and array of the sprite, only when needed
                if variant.name == "meta":
                    raise NotImplementedError("TODO: Meta")
                elif variant.name == "color":
                    # Apply a color to the tile
                    color = variant.arguments[0]
                    # If the color is a palette index, we need to grab from that index
                    self.fix_color(tile.attrs.palette, color)
                    color = (color.r, color.g, color.b)
                    frame = self.recolor(frame, color)
                else:
                    variants.append(variant)
                sprite_frames.append(frame)
            tile.sprite = tuple(sprite_frames)
        tile.variants = variants

    async def render(self, scene: Scene, buffer: BinaryIO):
        """Render a scene to a buffer."""
        self.cache_dirty = False

        frames = []
        tiles_by_time: dict[float, dict[Position, Tile]] = {}
        for pos, tile in scene.tiles.tiles.items():
            if pos.t not in tiles_by_time:
                tiles_by_time[pos.t] = {}
            tiles_by_time[pos.t][pos] = tile
        # Sort the tiles by depth
        for t, tiles in tiles_by_time.items():
            tiles_by_time[t] = dict(sorted(tiles.items()))
        current_frame = -1  # Start at -1 so that it's 0 in the inner loop
        for frame in range(scene.tiles.length):
            outer_cont = False
            current_frame += 1
            # Go through each wobble frame
            for wobble in (1, 2, 3):  # TODO: This needs to be dynamic eventually
                await asyncio.sleep(0)  # Give the GIL some room to breathe
                image = Image.new(
                    "RGBA",
                    # TODO: More intelligently precompute the scene size
                    (
                        (scene.tiles.width + 1) * scene.tile_spacing,
                        (scene.tiles.height + 1) * scene.tile_spacing
                    ),
                    (0, 0, 0, 0)  # TODO: Scene background
                )
                tiles = tiles_by_time.get(current_frame)
                if tiles is None:
                    # No tiles on this frame
                    outer_cont = True
                    break
                # Composite each tile onto the render
                for pos, tile in tiles.items():
                    RendererCog.composite(scene, image, pos, tile, wobble)
                frames.append(image)
            if outer_cont:
                continue
        if len(frames) == 0:
            raise CustomError(
                "No frames were generated in the render! "
                "Something probably went wrong internally, contact the bot developer."
            )
        self.encode_frames(scene, frames, buffer)

    @staticmethod
    def composite(scene: Scene, image: Image.Image, pos: Position, tile: Tile, wobble: int):
        """Composites a tile onto an image."""
        # match is just a prettier if/elif/else chain when used like this,
        # but I don't care because it's prettier
        sprite: Image.Image = tile.sprite[wobble - 1]
        x = int(pos.x * scene.tile_spacing)
        y = int(pos.y * scene.tile_spacing)
        x -= (sprite.width - scene.tile_spacing) // 2
        y -= (sprite.height - scene.tile_spacing) // 2
        match tile.attrs.compositing_mode:
            case CompositingMode.NORMAL:
                image.alpha_composite(
                    sprite,
                    (x, y)
                )
            case _:
                raise NotImplementedError(
                    f"Compositing mode {tile.attrs.compositing_mode} not implemented"
                )

    @staticmethod
    def encode_frames(scene: Scene, frames: list[Image], buffer: BinaryIO):
        if scene.format == ImageFormat.GIF:
            encoded_frames = []
            for frame in frames:
                array = np.array(frame)
                # Save fully transparent pixels of alpha
                empty_pixels = array[..., 3] == 0
                empty_pixels = np.dstack((empty_pixels, empty_pixels, empty_pixels))  # Stack to RGB
                # Multiply alpha into RGB
                alpha = array[..., 3].astype(float) / 255
                np.multiply(
                    array[..., :3], np.dstack((alpha, alpha, alpha)), out=array[..., :3],
                    casting="unsafe"  # Cast u8s to floats...
                )
                array = array[..., :3].astype(np.uint8)  # ...and back
                # Clip low color values to make way for the transparent color
                array[array < 8] = 8
                # Add back the transparent pixels
                array[empty_pixels] = 0
                # Create a 256-color palette
                palette = [0, 0, 0]  # Transparent color
                sorted_colors = RendererCog.sort_colors(array)
                # Limit to 255 colors, we're using the 256th for the transparent color
                palette_cols = sorted_colors[:255].flatten()
                palette.extend(palette_cols)
                # Create a dummy image to put our palette on
                dummy = Image.new("P", (16, 16))
                dummy.putpalette(palette)
                # Quantize our image to the palette
                frame = Image.fromarray(array)
                frame = frame.quantize(palette=dummy, dither=Image.Dither.NONE)
                # Resize as needed
                frame = frame.resize(
                    (frame.width * scene.image_size, frame.height * scene.image_size),
                    Image.Resampling.NEAREST
                )

                encoded_frames.append(frame)
            # Some keyword arguments have no default except when not specified at all,
            # so we add them with a dict
            extra_kwargs = {}
            if True:  # TODO: Loop config
                extra_kwargs["loop"] = 0
            # Save the first frames with the other frames appended to it
            encoded_frames[0].save(
                buffer,
                format="GIF",
                interlace=False,
                save_all=True,
                append_images=encoded_frames[1:],  # These get appended to the first frame
                duration=200,  # TODO: Dynamic frame durations
                background=0,
                disposal=2,
                transparency=0,  # Use color 0 (full black) as the transparent color
                optimize=False,  # Optimization breaks low-color renders like these
                **extra_kwargs
            )

    @commands.command(aliases=["t"])
    async def tile(self, ctx: Context, *, raw_scene: str):
        """Renders a scene from text."""
        async with ctx.typing():
            render_start = time.perf_counter()
            # Collect some profiling data while rendering
            parsing_start = time.perf_counter()
            scene = self.bot.parser.parse(raw_scene)
            parsing_end = time.perf_counter()
            parsing_time = parsing_end - parsing_start

            await self.assign_sprites(scene.tiles)
            sprite_end = time.perf_counter()
            sprite_time = sprite_end - parsing_end

            buf = BytesIO()
            await self.render(scene, buf)
            composite_time = time.perf_counter() - sprite_end
        render_time = time.perf_counter() - render_start
        message = f"Rendered in {render_time*1000:.4f}ms"
        if "verbose" in scene.flags:
            message = message + (
                f"\n- Parsing: {parsing_time * 1000:.4f}ms"
                f"\n- Filters: {sprite_time * 1000:.4f}ms"
                f"\n- Compositing: {composite_time * 1000:.4f}ms"
            )
        buf.seek(0)
        filename = f"{datetime.now().isoformat().replace(':', '_')}.{scene.format.value}"
        return await ctx.reply(
            message,
            file=discord.File(buf, filename=filename)
        )

    @staticmethod
    def sort_colors(array):
        colors, counts = np.unique(array.reshape(-1, 4), axis=0, return_counts=True)
        sorted_indices = np.argsort(counts)
        return colors[sorted_indices]

    @staticmethod
    def recolor(sprite: Image.Image | np.ndarray, rgb: tuple[int, int, int]) -> Image.Image | np.ndarray:
        """Apply RGB color multiplication."""
        arr = np.array(sprite)
        col = np.array(rgb)
        print(col)
        arr[..., :3] = np.multiply(arr[..., :3], col / 255, casting="unsafe").astype(np.uint8)
        if isinstance(sprite, np.ndarray):
            return arr
        return Image.fromarray(arr)

    def fix_color(self, palette: str | None, color: Color):
        """Convert a color from a palette index to RGB."""
        if color.b is None:
            palette = palette or "default"
            c = Color.from_tuple(self.open_image(
                Path("data", self.bot.database.palettes[palette], "palettes", palette).with_suffix(".png")
            ).getpixel((color.r, color.g))[:3])
            color.r, color.g, color.b = c.r, c.g, c.b


async def setup(bot: Bot):
    """Cog setup"""
    cog = RendererCog(bot)
    bot.renderer = cog
    await bot.add_cog(cog)
