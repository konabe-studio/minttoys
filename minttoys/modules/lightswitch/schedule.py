"""When it is dark, by Night Light's schedule or by set times. Free of GTK and D-Bus.

Night Light's own settings are read, not its state: Cinnamon works sunrise and sunset out
only while Night Light is on, and Light Switch should follow its schedule either way.
"""

from dataclasses import dataclass
from datetime import datetime

from minttoys.modules.awake import timer
from minttoys.modules.lightswitch import sun


@dataclass(frozen=True)
class NightLight:
    """Night Light's schedule settings (org.cinnamon.settings-daemon.plugins.color)."""

    mode: str  # "auto" (sunset to sunrise), "manual" or "always"
    start: float  # night-light-schedule-from, fractional hours
    end: float  # night-light-schedule-to
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Dark:
    """The dark hours of a day, as fractional hours; `end` may come before `start`."""

    start: float
    end: float
    # True when the hours are sunset and sunrise, False when set times.
    by_sun: bool


def by_night_light(night_light: NightLight, now: datetime) -> Dark:
    """Sunset to sunrise in "auto" mode once Night Light knows the location, as Night Light
    does; its set hours otherwise. "always" keeps Night Light on all day, which for a theme
    would mean never light, so it falls back to the set hours too.
    """
    if night_light.mode == "auto":
        times = sun.sunrise_sunset(now, night_light.latitude, night_light.longitude)
        if times is not None and times[0] > 0 and times[1] > 0:
            sunrise, sunset = times
            return Dark(sunset, sunrise, by_sun=True)
    return Dark(night_light.start, night_light.end, by_sun=False)


def by_times(start: str, end: str) -> Dark:
    """Set times, as "HH:MM"."""
    return Dark(_hours(start), _hours(end), by_sun=False)


def is_dark(dark: Dark, now: datetime) -> bool:
    return sun.is_between(sun.frac_day(now), dark.start, dark.end)


def clock(hours: float) -> str:
    """Fractional hours as "HH:MM", to the nearest minute."""
    minutes = round(hours * 60) % (24 * 60)
    return f"{minutes // 60:02}:{minutes % 60:02}"


def _hours(text: str) -> float:
    moment = timer.parse_clock_time(text)
    return moment.hour + moment.minute / 60
