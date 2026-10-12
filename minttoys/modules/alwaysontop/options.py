"""Always on Top's settings, read and checked without GTK or D-Bus.

In the config and over D-Bus they are shortcut, opacity_shortcuts, border, border_color,
border_width, border_opacity, border_radius, sound and excluded.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

# Keys for Muffin's own toggle-above, as PowerToys' Win+Ctrl+T.
SHORTCUT_KEYS = "<Primary><Super>t"
# Keys for a pinned window's opacity. PowerToys has Win+Ctrl+Plus and Minus; Plus needs
# Shift on a Hungarian keyboard, Page Up and Down are where they are on every layout.
MORE_OPAQUE_KEYS = "<Primary><Super>Page_Up"
LESS_OPAQUE_KEYS = "<Primary><Super>Page_Down"
MOST_WIDTH = 16
MOST_RADIUS = 24
LEAST_OPACITY = 10
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
# An application as X11 names it, its WM_CLASS: letters, digits and . _ -
_APP = re.compile(r"[\w.-]+")


@dataclass(frozen=True)
class Options:
    # Whether Always on Top gives Muffin's toggle-above its keys.
    shortcut: bool = True
    # Whether it adds the shortcuts that make a pinned window more or less opaque.
    opacity_shortcuts: bool = True
    # Whether a pinned window gets a frame around it.
    border: bool = True
    # "#rrggbb", or "" for the theme's accent colour.
    border_color: str = ""
    border_width: int = 4
    # Percent.
    border_opacity: int = 100
    # Pixels; 0 for square corners.
    border_radius: int = 8
    # Whether pinning and letting go play Cinnamon's maximize and unmaximize sounds. Off,
    # as Mint has its window sounds off.
    sound: bool = False
    # Applications that are never pinned, by WM_CLASS, one per line.
    excluded: str = ""

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
        return {key: getattr(self, key) for key in _CHECKS}

    @property
    def excluded_apps(self) -> list[str]:
        return [line for line in self.excluded.splitlines() if line]


def _flag(key: str) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _number(key: str, least: int, most: int) -> Callable[[object], int]:
    def check(value: object) -> int:
        if type(value) is not int or not least <= value <= most:
            raise ValueError(f"{key} is {least} to {most}, not {value!r}")
        return value

    return check


def _color(value: object) -> str:
    if value == "" or (isinstance(value, str) and _COLOR.fullmatch(value)):
        return str(value).lower()
    raise ValueError(f"border_color is #rrggbb or empty, not {value!r}")


def _excluded(value: object) -> str:
    """One application per line, blank lines and surrounding spaces dropped."""
    if not isinstance(value, str):
        raise ValueError(f"excluded is text, not {value!r}")
    apps = [line.strip() for line in value.splitlines() if line.strip()]
    for app in apps:
        if not _APP.fullmatch(app):
            raise ValueError(f"excluded holds application names such as firefox, not {app!r}")
    return "\n".join(apps)


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag("shortcut"),
    "opacity_shortcuts": _flag("opacity_shortcuts"),
    "border": _flag("border"),
    "border_color": _color,
    "border_width": _number("border_width", 1, MOST_WIDTH),
    "border_opacity": _number("border_opacity", LEAST_OPACITY, 100),
    "border_radius": _number("border_radius", 0, MOST_RADIUS),
    "sound": _flag("sound"),
    "excluded": _excluded,
}
