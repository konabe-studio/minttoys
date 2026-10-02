"""Awake's state in words, the same in the command line and in the panel icon."""

from datetime import datetime, timedelta

from minttoys.core.i18n import _
from minttoys.modules.awake import timer


def headline(state: dict, now: datetime) -> str:
    """One sentence: off, on until turned off, or on for how long and until when."""
    if state["mode"] == "off":
        return _("Awake is off.")
    if state["mode"] == "indefinite":
        return _("Awake is on until you turn it off.")
    end = datetime.fromtimestamp(state["ends_at"], now.tzinfo)
    # TRANSLATORS: {left} is the time left, such as "1 h 25 min", and {end} the time Awake
    # ends, such as "18:00", with the date in front when that is more than a day away.
    return _("Awake is on for {left} more, until {end}.").format(
        left=format_minutes(timer.minutes_left(now, end)), end=format_end(end, now)
    )


def screen(state: dict) -> str:
    if state["keep_screen"]:
        return _("The screen stays on.")
    return _("The screen may turn off, but the computer will not sleep.")


def describe(state: dict, now: datetime) -> str:
    """The headline, and while Awake is on, a second line about the screen."""
    if state["mode"] == "off":
        return headline(state, now)
    return f"{headline(state, now)}\n{screen(state)}"


def format_minutes(minutes: int) -> str:
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return _("{minutes} min").format(minutes=minutes)
    if not minutes:
        return _("{hours} h").format(hours=hours)
    return _("{hours} h {minutes} min").format(hours=hours, minutes=minutes)


def format_end(end: datetime, now: datetime) -> str:
    """The time of day within the next 24 hours, which leaves no doubt which day it is; the
    date as well beyond that.
    """
    local = end.astimezone(now.tzinfo)
    # Not end - now: both carry the same zone, and Python would subtract clock times.
    if timer.remaining(now, end) < timedelta(hours=24):
        return f"{local:%H:%M}"
    return f"{local:%Y-%m-%d %H:%M}"
