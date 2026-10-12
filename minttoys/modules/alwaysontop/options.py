"""Always on Top's settings, read and checked without GTK or D-Bus.

In the config and over D-Bus they are shortcut, border, border_color and border_width.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

# Keys for Muffin's own toggle-above, as PowerToys' Win+Ctrl+T.
SHORTCUT_KEYS = "<Primary><Super>t"
MOST_WIDTH = 16
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Options:
    # Whether Always on Top gives Muffin's toggle-above its keys.
    shortcut: bool = True
    # Whether a pinned window gets a frame around it.
    border: bool = True
    # "#rrggbb", or "" for the theme's accent colour.
    border_color: str = ""
    border_width: int = 4

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From the config. A value of the wrong kind falls back to its default."""
        options = cls()
        for key in _CHECKS:
            if key in settings:
                with suppress(ValueError):
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
        return replace(self, **fields)

    def settings(self) -> dict[str, Any]:
        return {
            "shortcut": self.shortcut,
            "border": self.border,
            "border_color": self.border_color,
            "border_width": self.border_width,
        }


def _flag(key: str) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _color(value: object) -> str:
    if value == "" or (isinstance(value, str) and _COLOR.fullmatch(value)):
        return str(value).lower()
    raise ValueError(f"border_color is #rrggbb or empty, not {value!r}")


def _width(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MOST_WIDTH:
        raise ValueError(f"border_width is 1 to {MOST_WIDTH}, not {value!r}")
    return value


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag("shortcut"),
    "border": _flag("border"),
    "border_color": _color,
    "border_width": _width,
}
