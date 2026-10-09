"""Conversions between what the settings widgets show and what the daemon stores, with no
GTK, so they can be tested anywhere.
"""

from minttoys.core.i18n import _
from minttoys.modules.awake.state import MAX_MINUTES


def modes() -> list[tuple[str, str]]:
    """What a click on the panel icon can start, as (default_mode, label)."""
    return [
        ("indefinite", _("Until turned off")),
        ("duration", _("For a set time")),
        ("until", _("Until a time of day")),
    ]


def day_modes() -> list[tuple[str, str]]:
    """Light Switch's modes for the day, with the Themes window's names, as (day_mode, label)."""
    return [
        # TRANSLATORS: the Themes window's mode with light windows and a dark panel.
        ("mixed", _("Mixed")),
        # TRANSLATORS: the Themes window's mode with light windows and a light panel.
        ("light", _("Light")),
    ]


def schedules() -> list[tuple[str, str]]:
    """What decides when Light Switch goes dark, as (schedule, label)."""
    return [
        ("night-light", _("With Night Light's schedule")),
        ("times", _("At set times")),
    ]


def split_minutes(total: int) -> tuple[int, int]:
    """A duration in minutes as the hours and minutes fields show it."""
    return divmod(total, 60)


def join_minutes(hours: int, minutes: int) -> int:
    """The hours and minutes fields as default_minutes: at least one minute, at most
    99 h 59 min, so whatever the fields hold, the daemon accepts it.
    """
    return max(1, min(hours * 60 + minutes, MAX_MINUTES))


def split_time(text: str) -> tuple[int, int]:
    """ "18:00" as the hour and minute fields show it."""
    hour, minute = text.split(":")
    return int(hour), int(minute)


def join_time(hour: int, minute: int) -> str:
    return f"{hour:02}:{minute:02}"
