"""Awake's modes and state, and the decisions that need no D-Bus: what a Start call asks
for, when a timed mode has ended, and when to look at the clock again.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from minttoys.modules.awake import timer


class Mode(StrEnum):
    OFF = "off"
    INDEFINITE = "indefinite"
    DURATION = "duration"
    UNTIL = "until"


@dataclass(frozen=True)
class State:
    mode: Mode = Mode.OFF
    # Off: only suspend is held off, and the screen may blank as usual.
    keep_screen: bool = False
    # When a timed mode ends, in UTC. None for off and indefinite.
    ends_at: datetime | None = None

    def describe(self) -> dict[str, str | bool | int]:
        """The state as the D-Bus API reports it, with the end as a unix time, 0 for none."""
        return {
            "mode": str(self.mode),
            "keep_screen": self.keep_screen,
            "ends_at": int(self.ends_at.timestamp()) if self.ends_at else 0,
        }


OFF = State()


# The longest default duration: the settings app's fields go to 99 h 59 min.
MAX_MINUTES = 99 * 60 + 59


@dataclass(frozen=True)
class Defaults:
    """Awake's settings: what Toggle starts, and whether the screen stays on.

    keep_screen is also what a client shows and starts with when it does not choose for
    itself, so the tray's check box and a plain `minttoys awake on` agree.

    In the config and over D-Bus they are default_mode, default_minutes, default_until
    and keep_screen.
    """

    mode: Mode = Mode.INDEFINITE
    minutes: int = 60
    until: str = "18:00"
    keep_screen: bool = False

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Defaults":
        """From Awake's section of the config. A value of the wrong kind falls back to its
        default, so a config edited by hand cannot keep Awake from starting.
        """
        defaults = cls()
        for key in _CHECKS:
            if key in settings:
                with suppress(ValueError):
                    defaults = defaults.update({key: settings[key]})
        return defaults

    def update(self, changes: Mapping[str, Any]) -> "Defaults":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take.
        """
        fields = {}
        for key, value in changes.items():
            if key not in _CHECKS:
                raise ValueError(f"unknown setting: {key!r}")
            field, check = _CHECKS[key]
            fields[field] = check(value)
        return replace(self, **fields)

    def settings(self) -> dict[str, str | int | bool]:
        """As the config and GetSettings have them."""
        return {
            "default_mode": str(self.mode),
            "default_minutes": self.minutes,
            "default_until": self.until,
            "keep_screen": self.keep_screen,
        }

    def start(self, now: datetime) -> State:
        """The state Toggle switches to."""
        return request(self.mode, self.minutes, self.until, self.keep_screen, now)


def _mode(value: object) -> Mode:
    if value not in ("indefinite", "duration", "until"):
        raise ValueError(f"default_mode is indefinite, duration or until, not {value!r}")
    return Mode(value)


def _minutes(value: object) -> int:
    if type(value) is not int or not 0 < value <= MAX_MINUTES:
        raise ValueError(f"default_minutes is 1 to {MAX_MINUTES}, not {value!r}")
    return value


def _until(value: object) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        return f"{timer.parse_clock_time(value):%H:%M}"
    except ValueError:
        raise ValueError(f"default_until is a time of day such as 18:00, not {value!r}") from None


def _keep_screen(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"keep_screen is true or false, not {value!r}")
    return value


# Each setting's key, the field it fills, and the check its value has to pass.
_CHECKS: dict[str, tuple[str, Callable[[object], Any]]] = {
    "default_mode": ("mode", _mode),
    "default_minutes": ("minutes", _minutes),
    "default_until": ("until", _until),
    "keep_screen": ("keep_screen", _keep_screen),
}


def request(mode: str, minutes: int, until: str, keep_screen: bool, now: datetime) -> State:
    """The state a Start call asks for, from the arguments as the D-Bus API takes them.

    A mode reads only the argument it needs: `minutes` for duration, `until` ("18:00") for
    until, neither for indefinite. Raises ValueError for an unknown mode or a value the
    mode cannot use.
    """
    try:
        chosen = Mode(mode)
    except ValueError:
        raise ValueError(f"unknown mode: {mode!r}") from None
    match chosen:
        case Mode.OFF:
            return OFF
        case Mode.INDEFINITE:
            return State(chosen, keep_screen)
        case Mode.DURATION:
            return State(chosen, keep_screen, timer.end_after(now, timedelta(minutes=minutes)))
        case Mode.UNTIL:
            target = timer.parse_clock_time(until)
            return State(chosen, keep_screen, timer.next_occurrence(now, target))


def expired(state: State, now: datetime) -> bool:
    return state.ends_at is not None and timer.remaining(now, state.ends_at) == timedelta(0)


def next_check(state: State, now: datetime, every: timedelta) -> timedelta | None:
    """How long a timed mode waits before it looks at the clock again: the time left, or
    `every` when that is sooner. None when nothing is timed.

    Looking at least every so often, rather than once at the end, is what keeps the end on
    time after a suspend or a change of the clock, which a single timer would miss.
    """
    if state.ends_at is None:
        return None
    return min(timer.remaining(now, state.ends_at), every)
