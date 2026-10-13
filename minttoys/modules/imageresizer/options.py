"""Image Resizer's settings, read and checked without GTK or D-Bus.

As PowerToys has them: the sizes to pick from, what the resize window last used, the JPEG
quality, the name of a resized picture, and whether it keeps the original's date.

A size is (name, fit, width, height, unit) in the config and as D-Bus a(ssdds). A width
or a height of 0 is left empty: it follows from the other and the picture's proportions.
The four sizes PowerToys starts with are named "$small$" and the like, and shown in the
user's language; a size the user names is shown as named.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
from typing import Any

from minttoys.core.i18n import _

FITS = ("fill", "fit", "stretch")
UNITS = ("px", "percent", "cm", "in")
# The names the first four sizes have, as PowerToys keeps them.
BUILT_IN = ("$small$", "$medium$", "$large$", "$phone$")


def built_in_name(name: str) -> str | None:
    """What a built-in size's name means in the user's language; None for any other."""
    return {
        # TRANSLATORS: one of Image Resizer's sizes, 854 by 480 pixels.
        "$small$": _("Small"),
        # TRANSLATORS: one of Image Resizer's sizes, 1366 by 768 pixels.
        "$medium$": _("Medium"),
        # TRANSLATORS: one of Image Resizer's sizes, 1920 by 1080 pixels.
        "$large$": _("Large"),
        # TRANSLATORS: one of Image Resizer's sizes, 320 by 568 pixels.
        "$phone$": _("Phone"),
    }.get(name)


MOST_SIZES = 50
MOST_VALUE = 100_000.0


@dataclass(frozen=True)
class Size:
    name: str
    fit: str = "fit"
    width: float = 0.0
    height: float = 0.0
    unit: str = "px"

    @property
    def shown_name(self) -> str:
        return built_in_name(self.name) or self.name

    def row(self) -> tuple[str, str, float, float, str]:
        return (self.name, self.fit, self.width, self.height, self.unit)


DEFAULT_SIZES = (
    Size("$small$", "fit", 854, 480),
    Size("$medium$", "fit", 1366, 768),
    Size("$large$", "fit", 1920, 1080),
    Size("$phone$", "fit", 320, 568),
)


@dataclass(frozen=True)
class Options:
    sizes: tuple[Size, ...] = DEFAULT_SIZES
    # What the resize window last used: an index into sizes, or len(sizes) for its own.
    selected: int = 0
    custom: Size = field(default_factory=lambda: Size("", "fit", 1024, 640))
    shrink_only: bool = False
    replace_original: bool = False
    ignore_orientation: bool = True
    remove_metadata: bool = False
    jpeg_quality: int = 90
    # %1 the original name, %2 the size's name, %3 and %4 the width and the height asked
    # for, %5 and %6 the height and the width made; a slash makes a folder.
    file_name: str = "%1 (%2)"
    keep_date: bool = False

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From Image Resizer's section of the config; a value of the wrong kind gives its
        default, so a config edited by hand cannot keep the tool from working.
        """
        options = cls()
        for key in _CHECKS:
            if key in settings:
                with suppress(ValueError, TypeError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take.
        """
        fields = {}
        for key, value in changes.items():
            if key not in _CHECKS:
                raise ValueError(f"unknown setting: {key!r}")
            fields[key] = _CHECKS[key](value)
        options = replace(self, **fields)
        if options.selected > len(options.sizes):
            options = replace(options, selected=0)
        return options

    def settings(self) -> dict[str, Any]:
        return {
            "sizes": [size.row() for size in self.sizes],
            "selected": self.selected,
            "custom": (self.custom.fit, self.custom.width, self.custom.height, self.custom.unit),
            "shrink_only": self.shrink_only,
            "replace_original": self.replace_original,
            "ignore_orientation": self.ignore_orientation,
            "remove_metadata": self.remove_metadata,
            "jpeg_quality": self.jpeg_quality,
            "file_name": self.file_name,
            "keep_date": self.keep_date,
        }

    @property
    def chosen(self) -> Size:
        """The size the resize window starts on."""
        if self.selected < len(self.sizes):
            return self.sizes[self.selected]
        return self.custom


def check_size(value: object, named: bool = True) -> Size:
    """A size from its row; ValueError when it is not one."""
    if not isinstance(value, list | tuple):
        raise ValueError(f"a size is a list, not {value!r}")
    if named:
        if len(value) != 5:
            raise ValueError(f"a size has five parts, not {value!r}")
        name, fit, width, height, unit = value
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"a size needs a name, not {name!r}")
    else:
        if len(value) != 4:
            raise ValueError(f"the size of one's own has four parts, not {value!r}")
        name = ""
        fit, width, height, unit = value
    if fit not in FITS:
        raise ValueError(f"fit is fill, fit or stretch, not {fit!r}")
    if unit not in UNITS:
        raise ValueError(f"unit is px, percent, cm or in, not {unit!r}")
    numbers = []
    for number in (width, height):
        if isinstance(number, bool) or not isinstance(number, int | float):
            raise ValueError(f"a width or a height is a number, not {number!r}")
        if not 0 <= number <= MOST_VALUE:
            raise ValueError(f"a width or a height is 0 to {MOST_VALUE:g}, not {number!r}")
        numbers.append(float(number))
    if not any(numbers):
        raise ValueError("a size needs a width, a height, or both")
    return Size(name.strip(), fit, numbers[0], numbers[1], unit)


def _sizes(value: object) -> tuple[Size, ...]:
    if not isinstance(value, list | tuple) or len(value) > MOST_SIZES:
        raise ValueError(f"sizes is a list of at most {MOST_SIZES}, not {value!r}")
    return tuple(check_size(row) for row in value)


def _flag(key: str):  # noqa: ANN202
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _whole(key: str, least: int, most: int):  # noqa: ANN202
    def check(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not least <= value <= most:
            raise ValueError(f"{key} is a whole number from {least} to {most}, not {value!r}")
        return value

    return check


def _file_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"file_name is a name such as %1 (%2), not {value!r}")
    parts = value.strip().split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"file_name cannot hold an empty, . or .. folder: {value!r}")
    return value.strip()


_CHECKS = {
    "sizes": _sizes,
    "selected": _whole("selected", 0, MOST_SIZES),
    "custom": lambda value: check_size(value, named=False),
    "shrink_only": _flag("shrink_only"),
    "replace_original": _flag("replace_original"),
    "ignore_orientation": _flag("ignore_orientation"),
    "remove_metadata": _flag("remove_metadata"),
    "jpeg_quality": _whole("jpeg_quality", 1, 100),
    "file_name": _file_name,
    "keep_date": _flag("keep_date"),
}
