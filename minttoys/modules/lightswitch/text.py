"""Light Switch's state in words, for the command line and the settings app."""

from collections.abc import Mapping
from typing import Any

from minttoys.core import accel
from minttoys.core.i18n import _
from minttoys.modules.lightswitch.options import SHORTCUT_KEYS


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


def shortcut(state: Mapping[str, Any]) -> str:
    """Light Switch's keyboard shortcut, or why it has none; "" when it has none by choice."""
    if state.get("shortcut"):
        # TRANSLATORS: {keys} is a keyboard shortcut such as Shift+Ctrl+Super+D.
        return _("Keyboard shortcut: {keys}").format(keys=accel.label(state["shortcut"]))
    if state.get("shortcut_problem") == "taken":
        return _("Its keyboard shortcut, {keys}, is in use already, so it has none.").format(
            keys=accel.label(SHORTCUT_KEYS)
        )
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
    if keys := shortcut(state):
        lines.append(keys)
    return "\n".join(lines)
