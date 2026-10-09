"""Keyboard shortcuts as GSettings stores them ("<Primary><Shift><Super>d"), read without GTK
so that the daemon can compare them and the command line can print them.

Close enough to Gtk.accelerator_parse for comparing shortcuts and naming them; the settings
app, which has GTK, names them with Gtk.accelerator_get_label instead.
"""

import re

_MODIFIERS = {
    "shift": "Shift",
    "shft": "Shift",
    "primary": "Ctrl",
    "control": "Ctrl",
    "ctrl": "Ctrl",
    "ctl": "Ctrl",
    "alt": "Alt",
    "mod1": "Alt",
    "super": "Super",
    "mod4": "Super",
    "hyper": "Hyper",
    "meta": "Meta",
}
# The order GTK names modifiers in.
_ORDER = ("Shift", "Ctrl", "Alt", "Super", "Hyper", "Meta")
_PART = re.compile(r"<([^<>]+)>")


def parse(accel: str) -> tuple[frozenset[str], str] | None:
    """The modifiers and the key of a shortcut, or None for one that is not a shortcut. A
    letter's case does not matter, as it does not to GTK.
    """
    modifiers = set()
    position = 0
    for match in _PART.finditer(accel):
        if match.start() != position:
            return None
        modifier = _MODIFIERS.get(match[1].lower())
        if modifier is None:
            return None
        modifiers.add(modifier)
        position = match.end()
    key = accel[position:]
    if not key or "<" in key or ">" in key:
        return None
    return frozenset(modifiers), key.lower() if len(key) == 1 else key


def same(first: str, second: str) -> bool:
    """Whether two shortcuts are the same keys, however they are written."""
    parsed = parse(first)
    return parsed is not None and parsed == parse(second)


def label(accel: str) -> str:
    """A shortcut as people write it: "Shift+Ctrl+Super+D". The text itself for one that
    does not parse.
    """
    parsed = parse(accel)
    if parsed is None:
        return accel
    modifiers, key = parsed
    named = [modifier for modifier in _ORDER if modifier in modifiers]
    return "+".join([*named, key.upper() if len(key) == 1 else key])
