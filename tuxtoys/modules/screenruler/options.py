"""Screen Ruler's settings, read and checked without GTK or D-Bus, with PowerToys' defaults:
its keyboard shortcut, the mode it opens in, the edge detection's tolerance and whether it
compares each color channel, the extra unit, feet on the cross, and the line's color.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.screenruler.measure import EXTRA_UNITS

MODES = ("none", "bounds", "spacing", "horizontal", "vertical")
SHORTCUT_KEYS = "<Primary><Shift><Super>m"
SHORTCUT_NAME = "TuxToys: Screen Ruler"
SHORTCUT_COMMAND = "tuxtoys screenruler"


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    default_mode: str = "none"
    tolerance: int = 30
    per_channel: bool = False
    extra_unit: str = "none"
    draw_feet: bool = True
    line_color: str = "#ff4500"

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From the tool's section of the config; a value of the wrong kind gives its
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
        return replace(self, **fields)

    def settings(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in _CHECKS}


def _flag(key: str):  # noqa: ANN202
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _one_of(key: str, choices: tuple[str, ...]):  # noqa: ANN202
    def check(value: object) -> str:
        if value not in choices:
            raise ValueError(f"{key} is one of {', '.join(map(repr, choices))}, not {value!r}")
        return value  # type: ignore[return-value]

    return check


def _tolerance(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError(f"tolerance is a whole number from 0 to 255, not {value!r}")
    return value


def _color(value: object) -> str:
    text = value if isinstance(value, str) else ""
    digits = text.removeprefix("#")
    if len(digits) != 6 or any(c not in "0123456789abcdefABCDEF" for c in digits):
        raise ValueError(f"line_color is #rrggbb, not {value!r}")
    return f"#{digits.lower()}"


_CHECKS = {
    "shortcut": _flag("shortcut"),
    "default_mode": _one_of("default_mode", MODES),
    "tolerance": _tolerance,
    "per_channel": _flag("per_channel"),
    "extra_unit": _one_of("extra_unit", EXTRA_UNITS),
    "draw_feet": _flag("draw_feet"),
    "line_color": _color,
}
