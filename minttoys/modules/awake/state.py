"""Awake's modes and state, and the decisions that need no D-Bus: what a Start call asks
for, when a timed mode has ended, and when to look at the clock again.
"""

from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Defaults:
    """Awake's settings: what Toggle starts, and whether the screen stays on.

    keep_screen is also what a client shows and starts with when it does not choose for
    itself, so the tray's check box and a plain `minttoys awake on` agree.
    """

    mode: Mode = Mode.INDEFINITE
    minutes: int = 60
    until: str = "18:00"
    keep_screen: bool = False

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Defaults":
        """From Awake's section of the config, under default_mode, default_minutes,
        default_until and keep_screen. A value of the wrong kind falls back to its
        default, so a config edited by hand cannot keep Awake from starting.
        """
        fallback = cls()
        mode = settings.get("default_mode")
        minutes = settings.get("default_minutes")
        until = settings.get("default_until")
        keep_screen = settings.get("keep_screen")
        return cls(
            Mode(mode) if mode in ("indefinite", "duration", "until") else fallback.mode,
            minutes if type(minutes) is int and minutes > 0 else fallback.minutes,
            _time_of_day(until) or fallback.until,
            keep_screen if isinstance(keep_screen, bool) else fallback.keep_screen,
        )

    def start(self, now: datetime) -> State:
        """The state Toggle switches to."""
        return request(self.mode, self.minutes, self.until, self.keep_screen, now)


def _time_of_day(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return f"{timer.parse_clock_time(value):%H:%M}"
    except ValueError:
        return None


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
