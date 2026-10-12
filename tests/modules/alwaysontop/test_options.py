import pytest

from minttoys.modules.alwaysontop.frame import OPAQUE, Rect, around, hex_to_rgb, step_opacity
from minttoys.modules.alwaysontop.options import Options

DEFAULTS = {
    "shortcut": True,
    "opacity_shortcuts": True,
    "border": True,
    "border_color": "",
    "border_width": 4,
    "border_opacity": 100,
    "border_radius": 8,
    "sound": False,
    "excluded": "",
}


def test_defaults() -> None:
    assert Options().settings() == DEFAULTS


def test_read_keeps_good_values_and_drops_bad_ones() -> None:
    options = Options.read({"border_color": "#3DAEE9", "border_width": 99, "border": "no"})
    assert options.settings() == {**DEFAULTS, "border_color": "#3daee9"}


def test_excluded_drops_blank_lines_and_spaces() -> None:
    options = Options().update({"excluded": " firefox \n\nvlc\n"})
    assert options.excluded == "firefox\nvlc"
    assert options.excluded_apps == ["firefox", "vlc"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"border_color": "blue"}, "border_color is #rrggbb"),
        ({"border_width": 0}, "border_width is 1 to 16"),
        ({"border_width": True}, "border_width is 1 to 16"),
        ({"border_opacity": 5}, "border_opacity is 10 to 100"),
        ({"border_radius": 30}, "border_radius is 0 to 24"),
        ({"shortcut": 1}, "shortcut is true or false"),
        ({"excluded": "my app"}, "excluded holds application names"),
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


def test_opacity_steps_down_from_opaque() -> None:
    assert step_opacity(None, up=False) == round(0.9 * OPAQUE)


def test_opacity_stops_at_the_ends() -> None:
    assert step_opacity(OPAQUE, up=True) == OPAQUE
    assert step_opacity(round(0.2 * OPAQUE), up=False) == round(0.2 * OPAQUE)


def test_opacity_steps_back_up_to_opaque() -> None:
    assert step_opacity(round(0.9 * OPAQUE), up=True) == OPAQUE
