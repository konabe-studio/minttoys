"""Hosts File Editor's settings, read and checked without GTK or D-Bus, as PowerToys has
them: the warning at the start, whether loopback addresses count as duplicates, and the
backups, made before the first save of a session and deleted never, by count, or by age
and count.
"""

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.core.backups import KEEPS

MOST_COUNT = 1000
MOST_DAYS = 3650


@dataclass(frozen=True)
class Options:
    show_warning: bool = True
    loopback_duplicates: bool = False
    backup: bool = True
    keep: str = "age"
    count: int = 5
    days: int = 15

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


def _whole(key: str, most: int):  # noqa: ANN202
    def check(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= most:
            raise ValueError(f"{key} is a whole number from 0 to {most}, not {value!r}")
        return value

    return check


def _keep(value: object) -> str:
    if value not in KEEPS:
        raise ValueError(f"keep is never, count or age, not {value!r}")
    return value  # type: ignore[return-value]


_CHECKS = {
    "show_warning": _flag("show_warning"),
    "loopback_duplicates": _flag("loopback_duplicates"),
    "backup": _flag("backup"),
    "keep": _keep,
    "count": _whole("count", MOST_COUNT),
    "days": _whole("days", MOST_DAYS),
}
