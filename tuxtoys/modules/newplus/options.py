"""New+'s settings, read and checked without GTK or D-Bus.

In the config and over D-Bus they are replace_variables and hide_digits, both off by
default, as in PowerToys.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class Options:
    # Replace $YYYY, %USER% and the like in the names of what is made from a template.
    replace_variables: bool = False
    # Leave out the digits, spaces and dots a template's name starts with.
    hide_digits: bool = False

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From New+'s section of the config; a value of the wrong kind gives its default."""
        options = cls()
        for key in _KEYS:
            if key in settings:
                with suppress(ValueError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value that is not true or false.
        """
        fields = {}
        for key, value in changes.items():
            if key not in _KEYS:
                raise ValueError(f"unknown setting: {key!r}")
            if not isinstance(value, bool):
                raise ValueError(f"{key} is true or false, not {value!r}")
            fields[key] = value
        return replace(self, **fields)

    def settings(self) -> dict[str, bool]:
        return {key: getattr(self, key) for key in _KEYS}

    def arguments(self) -> list[str]:
        """How the New from template window is told about them."""
        flags = []
        if self.replace_variables:
            flags.append("--variables")
        if self.hide_digits:
            flags.append("--hide-digits")
        return flags


_KEYS = ("replace_variables", "hide_digits")
