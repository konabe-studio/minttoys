"""Shortcut Guide's settings, read and checked without GTK or D-Bus: its keyboard shortcut,
where its window opens, the apps it does not open over, and the pinned shortcuts.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

# PowerToys' Win+Shift+/. On a Hungarian keyboard "/" is Shift+6, which Muffin then takes.
SHORTCUT_KEYS = "<Shift><Super>slash"
SHORTCUT_NAME = "TuxToys: Shortcut Guide"
SHORTCUT_COMMAND = "tuxtoys shortcutguide"
POSITIONS = ("left", "right", "center")
MOST_PINS = 100
# An application as X11 names it, its WM_CLASS: letters, digits and . _ -
_APP = re.compile(r"[\w.-]+")


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    position: str = "left"
    # Applications it does not open over, by WM_CLASS, one per line.
    excluded: str = ""
    # The pinned shortcuts, "sheet/item", in the order they were pinned.
    pinned: tuple[str, ...] = ()

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
        values = {key: getattr(self, key) for key in _CHECKS}
        values["pinned"] = list(self.pinned)
        return values

    @property
    def excluded_apps(self) -> list[str]:
        return [line.lower() for line in self.excluded.splitlines() if line]


def _flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"shortcut is true or false, not {value!r}")
    return value


def _position(value: object) -> str:
    if value not in POSITIONS:
        raise ValueError(f"position is one of {', '.join(POSITIONS)}, not {value!r}")
    return str(value)


def _excluded(value: object) -> str:
    """One application per line, blank lines and surrounding spaces dropped."""
    if not isinstance(value, str):
        raise ValueError(f"excluded is text, not {value!r}")
    apps = [line.strip() for line in value.splitlines() if line.strip()]
    for app in apps:
        if not _APP.fullmatch(app):
            raise ValueError(f"excluded holds application names such as firefox, not {app!r}")
    return "\n".join(apps)


def _pinned(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not all(
        isinstance(pin, str) and "/" in pin and len(pin) <= 200 for pin in value
    ):
        raise ValueError(f"pinned is a list of sheet/item names, not {value!r}")
    if len(value) > MOST_PINS:
        raise ValueError(f"pinned holds at most {MOST_PINS}, not {len(value)}")
    return tuple(dict.fromkeys(value))


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag,
    "position": _position,
    "excluded": _excluded,
    "pinned": _pinned,
}
