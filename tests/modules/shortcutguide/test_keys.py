import pytest

from tuxtoys.modules.shortcutguide.keys import caps, key_name


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        ("<Primary>c", ["Ctrl", "C"]),
        ("<Shift><Super>slash", ["Super", "Shift", "/"]),
        ("<Primary><Shift><Super>m", ["Super", "Ctrl", "Shift", "M"]),
        ("<Control><Alt>Delete", ["Ctrl", "Alt", "Delete"]),
        ("<Primary>Page_Up", ["Ctrl", "Page Up"]),
        ("<Alt>Left", ["Alt", "←"]),
        ("<Alt>Return", ["Alt", "Enter"]),
        ("Super_L", ["Super"]),
        ("F11", ["F11"]),
        ("<Primary>plus", ["Ctrl", "+"]),
        ("Print", ["PrtScr"]),
        ("XF86AudioRaiseVolume", ["Audio Raise Volume"]),
        ("XF86Calculator", ["Calculator"]),
    ],
)
def test_keycaps_in_powertoys_order(keys: str, expected: list[str]) -> None:
    assert caps(keys) == expected


@pytest.mark.parametrize("keys", ["", "<Primary>", "<Nonsense>x", "disabled<"])
def test_what_is_not_a_shortcut_has_no_keycaps(keys: str) -> None:
    assert caps(keys) == []


def test_a_key_without_a_name_of_its_own_drops_its_underscores() -> None:
    assert key_name("Scroll_Lock") == "Scroll Lock"
    assert key_name("backslash") == "\\"
