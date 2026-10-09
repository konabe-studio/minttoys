"""What the panel icon shows for a state, decided without GTK so it can be tested anywhere."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from minttoys import APP_ID
from minttoys.core.i18n import ngettext
from minttoys.modules.awake import text, timer

ICON_ON = f"{APP_ID}-awake-on-symbolic"
ICON_OFF = f"{APP_ID}-awake-off-symbolic"
# A timed mode keeps one plume of steam and shows what it waits for in its place: an
# hourglass for a set time, a clock for a time of day.
ICON_DURATION = f"{APP_ID}-awake-duration-symbolic"
ICON_UNTIL = f"{APP_ID}-awake-until-symbolic"
ICONS = {"indefinite": ICON_ON, "duration": ICON_DURATION, "until": ICON_UNTIL}

# The durations the menu offers with one click.
QUICK_MINUTES = (30, 60, 120)


@dataclass(frozen=True)
class View:
    icon: str
    # The tooltip, which is also the menu's first line.
    status: str
    # False while the daemon is not there or Awake is switched off in it: then the menu
    # can only say so.
    available: bool
    on: bool
    keep_screen: bool


def present(state: dict | None, now: datetime, problem: str = "") -> View:
    """The view of Awake's `state` as GetState reports it, or of `problem` when there is no
    state to show.
    """
    if state is None:
        return View(ICON_OFF, problem, available=False, on=False, keep_screen=False)
    on = state["mode"] != "off"
    return View(
        ICONS.get(state["mode"], ICON_OFF),
        text.headline(state, now),
        available=True,
        on=on,
        keep_screen=state["keep_screen"],
    )


def quick_label(minutes: int) -> str:
    if minutes % 60:
        # TRANSLATORS: items of the panel icon's menu, each keeping the computer awake for
        # that long.
        return ngettext("For {count} minute", "For {count} minutes", minutes).format(count=minutes)
    hours = minutes // 60
    return ngettext("For {count} hour", "For {count} hours", hours).format(count=hours)


def refresh_in(state: dict | None, now: datetime) -> int | None:
    """Seconds until the minutes left, as the status shows them, go down by one; None when
    nothing counts down. Waking then, not on a fixed tick, keeps the status exact.
    """
    if state is None or not state["ends_at"]:
        return None
    end = datetime.fromtimestamp(state["ends_at"], now.tzinfo)
    seconds = timer.remaining(now, end) / timedelta(seconds=1)
    if seconds <= 0:
        return None
    return int(seconds % 60) + 1 if seconds % 60 else 60


def next_full_hour(now: datetime) -> tuple[int, int]:
    """The time the "until" dialog offers first: the next full hour, at least 30 minutes on."""
    later = now + timedelta(minutes=90)
    return later.hour, 0
