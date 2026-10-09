"""Light Switch's settings, read and checked without GTK or D-Bus.

In the config and over D-Bus they are day_mode, schedule, dark_from and dark_to.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from minttoys.modules.awake import timer

# The modes the day can have. The night is always dark.
DAY_MODES = ("mixed", "light")
# What decides when it is dark: Night Light's schedule, or the two set times.
SCHEDULES = ("night-light", "times")


@dataclass(frozen=True)
class Options:
    # Empty until Light Switch first comes on, which then keeps the mode in use: whoever
    # uses Light keeps Light. Mixed, Mint's default, when that is not known.
    day_mode: str = ""
    schedule: str = "night-light"
    dark_from: str = "20:00"
    dark_to: str = "06:00"

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From Light Switch's section of the config. A value of the wrong kind falls back
        to its default, so a config edited by hand cannot keep the module from starting.
        """
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

    def settings(self) -> dict[str, str]:
        return {
            "day_mode": self.day_mode,
            "schedule": self.schedule,
            "dark_from": self.dark_from,
            "dark_to": self.dark_to,
        }

    @property
    def day(self) -> str:
        """The mode the day switches to."""
        return self.day_mode or "mixed"


def _day_mode(value: object) -> str:
    if value not in DAY_MODES:
        raise ValueError(f"day_mode is mixed or light, not {value!r}")
    return str(value)


def _schedule(value: object) -> str:
    if value not in SCHEDULES:
        raise ValueError(f"schedule is night-light or times, not {value!r}")
    return str(value)


def _clock(key: str) -> Callable[[object], str]:
    def check(value: object) -> str:
        try:
            if not isinstance(value, str):
                raise ValueError
            return f"{timer.parse_clock_time(value):%H:%M}"
        except ValueError:
            raise ValueError(f"{key} is a time of day such as 20:00, not {value!r}") from None

    return check


_CHECKS: dict[str, Callable[[object], str]] = {
    "day_mode": _day_mode,
    "schedule": _schedule,
    "dark_from": _clock("dark_from"),
    "dark_to": _clock("dark_to"),
}
