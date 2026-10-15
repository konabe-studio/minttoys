"""A color's everyday name, "Light Green" or "Dark Blue", as PowerToys' ColorNameHelper
gives it, for Color Picker's "Show color name". Free of GTK.

From HSL on a 0-255 scale: very light is white and very dark black; little saturation is
a gray; otherwise the saturation picks a table of hue limits that sorts the hue into one
of 23 buckets, and the lightness picks the light, mid or dark name of that bucket.
"""

from tuxtoys.core.i18n import _
from tuxtoys.modules.colorpicker.colors import Color, hsl

# For each saturation band, the hue each of the 23 buckets ends below; 0 where a bucket
# is not used at that saturation.
_HUE_LIMITS = (
    (20, 75, (8, 0, 0, 44, 0, 0, 0, 63, 0, 0, 122, 0, 134, 0, 0, 0, 0, 166, 176, 241, 0, 256, 0)),
    (
        75,
        115,
        (0, 10, 0, 32, 46, 0, 0, 0, 61, 0, 106, 0, 136, 144, 0, 0, 0, 158, 166, 241, 0, 0, 256),
    ),
    (
        115,
        150,
        (0, 8, 0, 0, 39, 46, 0, 0, 0, 71, 120, 0, 131, 144, 0, 0, 163, 0, 177, 211, 249, 0, 256),
    ),
    (
        150,
        240,
        (0, 11, 26, 0, 0, 38, 45, 0, 0, 56, 100, 121, 129, 0, 140, 0, 180, 0, 0, 224, 241, 0, 256),
    ),
    (
        240,
        256,
        (0, 13, 27, 0, 0, 36, 45, 0, 0, 59, 118, 0, 127, 136, 142, 0, 185, 0, 0, 216, 239, 0, 256),
    ),
)
_LUM_LOW = (
    130,
    100,
    115,
    100,
    100,
    100,
    110,
    75,
    100,
    90,
    100,
    100,
    100,
    100,
    80,
    100,
    100,
    100,
    100,
    100,
    100,
    100,
    100,
)
_LUM_HIGH = (
    170,
    170,
    170,
    155,
    170,
    170,
    170,
    170,
    170,
    115,
    170,
    170,
    170,
    170,
    170,
    170,
    170,
    170,
    150,
    150,
    170,
    140,
    165,
)
_LIGHT = (
    "coral", "rose", "light-orange", "tan", "tan", "light-yellow", "light-yellow", "tan",
    "light-green", "lime", "light-green", "light-green", "aqua", "sky-blue", "light-turquoise",
    "pale-blue", "light-blue", "ice-blue", "periwinkle", "lavender", "pink", "tan", "rose",
)  # fmt: skip
_MID = (
    "coral", "red", "orange", "brown", "tan", "gold", "yellow", "olive-green", "olive-green",
    "green", "green", "bright-green", "teal", "aqua", "turquoise", "pale-blue", "blue",
    "blue-gray", "indigo", "purple", "pink", "brown", "red",
)  # fmt: skip
_DARK = (
    "brown", "dark-red", "brown", "brown", "brown", "dark-yellow", "dark-yellow", "brown",
    "dark-green", "dark-green", "dark-green", "dark-green", "dark-teal", "dark-teal",
    "dark-teal", "dark-blue", "dark-blue", "blue-gray", "indigo", "dark-purple", "plum",
    "brown", "dark-red",
)  # fmt: skip


def name_id(color: Color) -> str:
    """Which name, as an id such as "light-green"."""
    hue, saturation, lightness = hsl(color)
    hue = hue / 360 * 255
    saturation *= 255
    lightness *= 255
    if lightness > 240:
        return "white"
    if lightness < 20:
        return "black"
    if saturation <= 20:
        if lightness > 170:
            return "light-gray"
        return "gray" if lightness > 100 else "dark-gray"
    limits = next(table for low, high, table in _HUE_LIMITS if low < saturation <= high)
    index = next(i for i, limit in enumerate(limits) if hue < limit)
    if lightness > _LUM_HIGH[index]:
        return _LIGHT[index]
    if lightness < _LUM_LOW[index]:
        return _DARK[index]
    return _MID[index]


def name(color: Color) -> str:
    """The color's name in the user's language."""
    return names()[name_id(color)]


def names() -> dict[str, str]:
    # TRANSLATORS: color names Color Picker shows beside a color, as PowerToys does.
    return {
        "white": _("White"),
        "black": _("Black"),
        "light-gray": _("Light Gray"),
        "gray": _("Gray"),
        "dark-gray": _("Dark Gray"),
        "coral": _("Coral"),
        "rose": _("Rose"),
        "light-orange": _("Light Orange"),
        "tan": _("Tan"),
        "light-yellow": _("Light Yellow"),
        "light-green": _("Light Green"),
        "lime": _("Lime"),
        "aqua": _("Aqua"),
        "sky-blue": _("Sky Blue"),
        "light-turquoise": _("Light Turquoise"),
        "pale-blue": _("Pale Blue"),
        "light-blue": _("Light Blue"),
        "ice-blue": _("Ice Blue"),
        "periwinkle": _("Periwinkle"),
        "lavender": _("Lavender"),
        "pink": _("Pink"),
        "red": _("Red"),
        "orange": _("Orange"),
        "brown": _("Brown"),
        "gold": _("Gold"),
        "yellow": _("Yellow"),
        "olive-green": _("Olive Green"),
        "green": _("Green"),
        "bright-green": _("Bright Green"),
        "teal": _("Teal"),
        "turquoise": _("Turquoise"),
        "blue": _("Blue"),
        "blue-gray": _("Blue Gray"),
        "indigo": _("Indigo"),
        "purple": _("Purple"),
        "dark-red": _("Dark Red"),
        "dark-yellow": _("Dark Yellow"),
        "dark-green": _("Dark Green"),
        "dark-teal": _("Dark Teal"),
        "dark-blue": _("Dark Blue"),
        "dark-purple": _("Dark Purple"),
        "plum": _("Plum"),
    }
