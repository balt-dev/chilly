# pylint: disable=import-error, too-few-public-methods
"""Variant registry."""

from src.classes import ArgumentError, Color, CustomError, Variant, VariantData


class VariantRegistry:
    """A registry of variants."""

    variants: set[VariantData]
    __slots__ = ("variants",)

    @staticmethod
    def parse_type(ty: type, string: str):
        if False:
            ...
        else:
            return ty(string)

    def parse(self, variant: Variant):
        """Parse a variant."""
        this_data: VariantData
        for data in self.variants:
            if variant.name in data.names:
                variant.name = data.names[0]
                this_data = data
                break
        else:
            raise CustomError(
                f"Couldn't find a variant called `{variant.name}`."
            )
        args = list(this_data.defaults)
        var = repr(variant)
        last_ty = None
        for i, (ty, arg) in enumerate(zip(
                this_data.arguments,
                variant.arguments,
                strict=False
        )):
            try:
                if ty is ...:
                    ty = last_ty
                    del args[-1]
                    for vararg in variant.arguments[i:]:
                        arg = vararg
                        i += 1
                        args.append(VariantRegistry.parse_type(last_ty, arg))
                    break
                parsed_arg = VariantRegistry.parse_type(ty, arg)
                last_ty = ty
            except ValueError as e:
                raise ArgumentError(ty, arg, repr(self)) from e
            args[i] = parsed_arg
        for i, arg in enumerate(args):
            if arg is None:
                raise CustomError(
                    f"Only `{i}` arguments were provided to "
                    f"the variant `{var}`, but it requires "
                    f"at least `{len(variant.arguments)}`."
                )
        variant.arguments = args


async def setup(bot):
    """Set up the bot's variant registry."""
    reg = VariantRegistry()
    reg.variants = {
        VariantData(
            ("meta", "m"),
            "Adds an outline to the tile's sprite.\n"
            "You can optionally specify how many times to outline, "
            "a kernel, and an outline size.",
            "baba:meta",
            (int, str, int),
            (1, "full", 1)
        ),
        VariantData(
            ("left", "l"),
            "Makes the tile face left.",
            "arrow:l"
        ),
        VariantData(
            ("up", "u"),
            "Makes the tile face up.",
            "arrow:u"
        ),
        VariantData(
            ("right", "r"),
            "Makes the tile face right.",
            "arrow:r"
        ),
        VariantData(
            ("down", "d"),
            "Makes the tile face down.",
            "arrow:d"
        ),
        VariantData(
            ("sleep", "s"),
            "Makes the tile fall asleep.",
            "baba:s"
        ),
        VariantData(
            ("displace", "disp"),
            "Displaces the tile's position by a pixel amount.",
            "cog:disp/4/4",
            (int, int),
            (None, None)
        ),
        VariantData(
            ("color", "c"),
            "Changes the color of a tile. May be a palette index or a hex RGB.",
            "pixel:c/#7289DA pixel:c/4,1",
            (Color,),
            (None,)
        ),
        VariantData(
            ("tiling", "t"),
            "Manually sets the state of an autotiling tile.",
            "wall:t/u/l/ul",
            (str, ...),
            (None, None)
        )
    }
    bot.variant_registry = reg
