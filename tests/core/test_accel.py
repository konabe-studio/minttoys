import pytest

from minttoys.core import accel


def test_parse() -> None:
    assert accel.parse("<Primary><Shift><Super>d") == (frozenset({"Ctrl", "Shift", "Super"}), "d")


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("<Primary><Shift><Super>d", "<Super><Control><Shift>D"),
        ("<Ctrl><Mod1>t", "<Control><Alt>t"),
        ("<Super>Left", "<Mod4>Left"),
    ],
)
def test_the_same_keys_however_written(first: str, second: str) -> None:
    assert accel.same(first, second)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("<Super>d", "<Super><Shift>d"),
        ("<Super>d", "<Super>e"),
        ("<Super>Left", "<Super>left"),
    ],
)
def test_different_keys(first: str, second: str) -> None:
    assert not accel.same(first, second)


@pytest.mark.parametrize("text", ["", "<Super>", "<Nonsense>d", "d<Super>", "<Super>d>"])
def test_what_is_not_a_shortcut(text: str) -> None:
    assert accel.parse(text) is None
    assert not accel.same(text, text)


def test_a_key_alone() -> None:
    assert accel.parse("XF86Display") == (frozenset(), "XF86Display")


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("<Primary><Shift><Super>d", "Shift+Ctrl+Super+D"),
        ("<Super>Left", "Super+Left"),
        ("<Alt>F4", "Alt+F4"),
        ("not <a> shortcut", "not <a> shortcut"),
    ],
)
def test_label(text: str, shown: str) -> None:
    assert accel.label(text) == shown
