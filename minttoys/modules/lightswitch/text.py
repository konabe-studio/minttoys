"""Light Switch's state in words, for the command line and the settings app."""

from collections.abc import Mapping
from typing import Any

from minttoys.core.i18n import _


def hours(state: Mapping[str, Any]) -> str:
    """When it is dark, as GetState reports it."""
    if state["by_sun"]:
        # TRANSLATORS: Light Switch's dark hours by the sun; {start} and {end} are times of
        # day such as 18:09 and 06:53.
        return _("Dark from {start} to {end}, sunset to sunrise.").format(
            start=state["dark_from"], end=state["dark_to"]
        )
    # TRANSLATORS: Light Switch's dark hours at set times, such as 20:00 and 06:00.
    return _("Dark from {start} to {end}.").format(start=state["dark_from"], end=state["dark_to"])


def problem(state: Mapping[str, Any]) -> str:
    """Why Light Switch cannot switch the desktop, or "" when it can."""
    if state["problem"] == "custom":
        return _("Your themes are not one of Mint's styles, so Light Switch leaves them alone.")
    if state["problem"] == "no-mode":
        return _("Your style has no mode to switch to.")
    return ""


def describe(state: Mapping[str, Any]) -> str:
    """The lines `minttoys lightswitch` prints."""
    if state["dark"]:
        lines = [_("The desktop is dark now.")]
    else:
        lines = [_("The desktop is in its day mode now.")]
    lines.append(hours(state))
    if reason := problem(state):
        lines.append(reason)
    return "\n".join(lines)
