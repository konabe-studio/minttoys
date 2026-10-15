"""Color Picker's settings, read and checked without GTK or D-Bus, as PowerToys has them:
whether it keeps its keyboard shortcut, the format a picked color is copied in, the
formats the editor shows, each with whether it is shown, and the last colors picked.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.colorpicker.colors import DEFAULT_FORMATS, Color

MOST_HISTORY = 20
MOST_FORMATS = 50
MOST_TEMPLATE = 200
# The formats shown at first; the rest can be switched on.
SHOWN_AT_FIRST = frozenset({"HEX", "RGB", "HSL", "HSV", "CMYK"})

SHORTCUT_KEYS = "<Shift><Super>c"
SHORTCUT_NAME = "TuxToys: Color Picker"
SHORTCUT_COMMAND = "tuxtoys colorpicker"

type Format = tuple[str, str, bool]  # name, template, shown


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    default_format: str = "HEX"
    formats: tuple[Format, ...] = tuple(
        (name, template, name in SHOWN_AT_FIRST) for name, template in DEFAULT_FORMATS
    )
    history: tuple[str, ...] = ()  # "#rrggbb", the newest first

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From the tool's section of the config; a value of the wrong kind gives its
        default, so a config edited by hand cannot keep the tool from working.
        """
        options = cls()
        for key in ("shortcut", "formats", "default_format", "history"):
            if key in settings:
                with suppress(ValueError, TypeError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take.
        """
        fields: dict[str, Any] = {}
        for key, value in changes.items():
            if key == "shortcut":
                if not isinstance(value, bool):
                    raise ValueError(f"shortcut is true or false, not {value!r}")
                fields[key] = value
            elif key == "default_format":
                if not isinstance(value, str):
                    raise ValueError(f"default_format is a format's name, not {value!r}")
                fields[key] = value
            elif key == "formats":
                fields[key] = _formats(value)
            elif key == "history":
                fields[key] = _history(value)
            else:
                raise ValueError(f"unknown setting: {key!r}")
        options = replace(self, **fields)
        if options.default_format not in {name for name, _t, _s in options.formats}:
            if "default_format" in changes:
                raise ValueError(f"there is no format {options.default_format!r}")
            options = replace(options, default_format=options.formats[0][0])
        return options

    def settings(self) -> dict[str, Any]:
        return {
            "shortcut": self.shortcut,
            "default_format": self.default_format,
            "formats": [list(entry) for entry in self.formats],
            "history": list(self.history),
        }

    def template(self, name: str) -> str:
        for entry_name, template, _shown in self.formats:
            if entry_name == name:
                return template
        return DEFAULT_FORMATS[0][1]

    def picked(self, color: Color) -> "Options":
        """These settings with `color` first in the history, once."""
        history = [color.hex, *(old for old in self.history if old != color.hex)]
        return replace(self, history=tuple(history[:MOST_HISTORY]))


def _formats(value: object) -> tuple[Format, ...]:
    if not isinstance(value, list | tuple) or not 0 < len(value) <= MOST_FORMATS:
        raise ValueError(f"formats is a list of 1 to {MOST_FORMATS}")
    formats = []
    for entry in value:
        if not isinstance(entry, list | tuple) or len(entry) != 3:
            raise ValueError(f"a format is a name, a template and shown, not {entry!r}")
        name, template, shown = entry
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"a format needs a name, not {name!r}")
        if not isinstance(template, str) or not template or len(template) > MOST_TEMPLATE:
            raise ValueError(f"a format's template is text, not {template!r}")
        if not isinstance(shown, bool):
            raise ValueError(f"shown is true or false, not {shown!r}")
        formats.append((name.strip(), template, shown))
    if len({name for name, _t, _s in formats}) != len(formats):
        raise ValueError("two formats have the same name")
    return tuple(formats)


def _history(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or len(value) > MOST_HISTORY:
        raise ValueError(f"history is a list of at most {MOST_HISTORY} colors")
    return tuple(Color.from_hex(text).hex for text in value)
