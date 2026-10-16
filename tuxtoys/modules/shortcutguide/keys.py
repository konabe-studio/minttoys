"""A shortcut as the keycaps Shortcut Guide draws: "<Primary><Shift>Page_Up" is Ctrl, Shift,
Page Up. The modifiers come first in PowerToys' order, Super, Ctrl, Alt, Shift.

Keycaps carry the key's own name, as printed on keyboards, in every language.
"""

import re

from tuxtoys.core import accel

_ORDER = ("Super", "Ctrl", "Alt", "Shift", "Hyper", "Meta")
# Keys with a name of their own; the rest drop their underscores, "Page_Up" is "Page Up".
_NAMES = {
    "Return": "Enter",
    "KP_Enter": "Enter",
    "Escape": "Esc",
    "BackSpace": "Backspace",
    "space": "Space",
    "Left": "←",
    "Right": "→",
    "Up": "↑",
    "Down": "↓",
    "Print": "PrtScr",
    "Prior": "Page Up",
    "Next": "Page Down",
    "Super_L": "Super",
    "Super_R": "Super",
    "Control_L": "Ctrl",
    "Control_R": "Ctrl",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "slash": "/",
    "backslash": "\\",
    "question": "?",
    "plus": "+",
    "minus": "-",
    "equal": "=",
    "period": ".",
    "comma": ",",
    "semicolon": ";",
    "apostrophe": "'",
    "grave": "`",
    "bracketleft": "[",
    "bracketright": "]",
    "KP_Add": "+",
    "KP_Subtract": "-",
    "KP_Multiply": "*",
    "KP_Divide": "/",
}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z0-9])")


def key_name(key: str) -> str:
    if key in _NAMES:
        return _NAMES[key]
    if len(key) == 1:
        return key.upper()
    if key.startswith("XF86"):
        # Media keys: "XF86AudioRaiseVolume" is "Audio Raise Volume".
        return _CAMEL.sub(" ", key[4:])
    return key.replace("_", " ")


def caps(keys: str) -> list[str]:
    """The keycaps of one shortcut, or [] for one that is not a shortcut."""
    parsed = accel.parse(keys)
    if parsed is None:
        return []
    modifiers, key = parsed
    return [*(name for name in _ORDER if name in modifiers), key_name(key)]
