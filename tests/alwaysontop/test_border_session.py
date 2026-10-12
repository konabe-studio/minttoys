"""The frames with real GTK. Needs a display: xvfb in CI, the desktop otherwise. Which windows
are pinned comes from libwnck and the window manager, which xvfb has none of, so the frames
are handed their windows directly.
"""

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)
pytest.importorskip("cairo", reason="pycairo is not installed")

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from minttoys.alwaysontop.border import Borders, parse_color, theme_accent  # noqa: E402
from minttoys.modules.alwaysontop.frame import Rect  # noqa: E402


def test_a_frame_for_each_pinned_window_and_none_for_the_rest() -> None:
    borders = Borders((1.0, 0.5, 0.0), 4)
    borders.show({1: Rect(100, 100, 400, 300), 2: Rect(600, 100, 200, 200)})
    assert set(borders._frames) == {1, 2}
    first = borders._frames[1]
    assert first.get_visible()
    borders.show({2: Rect(600, 100, 200, 200)})
    assert set(borders._frames) == {2}
    borders.show({})
    assert borders._frames == {}


def test_parse_color() -> None:
    assert parse_color("#ff0000") == (1.0, 0.0, 0.0)
    assert parse_color("") is None


def test_the_theme_has_an_accent() -> None:
    red, green, blue = theme_accent()
    assert all(0 <= part <= 1 for part in (red, green, blue))
