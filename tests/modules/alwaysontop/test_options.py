import pytest

from minttoys.modules.alwaysontop.frame import Rect, around, hex_to_rgb
from minttoys.modules.alwaysontop.options import Options

DEFAULTS = {"shortcut": True, "border": True, "border_color": "", "border_width": 4}


def test_defaults() -> None:
    assert Options().settings() == DEFAULTS


def test_read_keeps_good_values_and_drops_bad_ones() -> None:
    options = Options.read({"border_color": "#3DAEE9", "border_width": 99, "border": "no"})
    assert options.settings() == {**DEFAULTS, "border_color": "#3daee9"}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"border_color": "blue"}, "border_color is #rrggbb"),
        ({"border_width": 0}, "border_width is 1 to 16"),
        ({"border_width": True}, "border_width is 1 to 16"),
        ({"shortcut": 1}, "shortcut is true or false"),
        ({"colour": "x"}, "unknown setting"),
    ],
)
def test_update_refuses(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Options().update(changes)


def test_the_frame_sits_outside_the_window() -> None:
    assert around(Rect(100, 50, 800, 600), 4) == Rect(96, 46, 808, 608)


def test_hex_to_rgb() -> None:
    assert hex_to_rgb("#ff8000") == pytest.approx((1.0, 128 / 255, 0.0))
