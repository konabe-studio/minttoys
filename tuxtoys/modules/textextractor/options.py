"""Text Extractor's settings, read and checked without GTK or D-Bus: its keyboard shortcut
and the language it reads in, tesseract's code, "" for the desktop's own.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

SHORTCUT_KEYS = "<Shift><Super>t"
SHORTCUT_NAME = "TuxToys: Text Extractor"
SHORTCUT_COMMAND = "tuxtoys textextractor"


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    language: str = ""

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


def _shortcut(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"shortcut is true or false, not {value!r}")
    return value


def _language(value: object) -> str:
    # Tesseract's data file names: letters, digits and underscores, as chi_sim.
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError(f"language is a tesseract language code, not {value!r}")
    if value and not all(c.isascii() and (c.isalnum() or c == "_") for c in value):
        raise ValueError(f"language is a tesseract language code, not {value!r}")
    return value


_CHECKS = {"shortcut": _shortcut, "language": _language}
