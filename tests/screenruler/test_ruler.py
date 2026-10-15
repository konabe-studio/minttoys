"""Screen Ruler's window on a made-up screen: the tools, what a click copies, and the
tolerance on the scroll wheel. Needs a display; CI gives it one.
"""

from types import SimpleNamespace

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.modules.screenruler.measure import Monitor, Rect  # noqa: E402
from tuxtoys.modules.screenruler.options import Options  # noqa: E402
from tuxtoys.screenruler.ruler import Ruler  # noqa: E402


def white_with_a_grey_box() -> GdkPixbuf.Pixbuf:
    """100 by 80, white, with a grey box from (10, 20) to (39, 29)."""
    width, height = 100, 80
    data = bytearray([255] * width * height * 3)
    for y in range(20, 30):
        for x in range(10, 40):
            start = (y * width + x) * 3
            data[start : start + 3] = bytes([200, 200, 200])
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB, False, 8, width, height, width * 3
    )


def make(options: Options = Options()) -> tuple[Ruler, list[str]]:  # noqa: B008
    copied: list[str] = []
    ruler = Ruler(white_with_a_grey_box(), [Monitor(0, 0, 100, 80)], (5, 5), options, copied.append)
    return ruler, copied


def button(number: int, x: int, y: int, state: int = 0) -> SimpleNamespace:
    return SimpleNamespace(button=number, x=x, y=y, state=Gdk.ModifierType(state))


def test_it_opens_with_the_tool_set() -> None:
    ruler, _copied = make()
    assert ruler.tool == ""
    assert not any(b.get_active() for b in ruler.buttons.values())
    ruler, _copied = make(Options(default_mode="spacing"))
    assert ruler.tool == "spacing"
    assert ruler.buttons["spacing"].get_active()


def test_the_buttons_and_the_keys_choose_a_tool() -> None:
    ruler, _copied = make()
    ruler.buttons["vertical"].set_active(True)
    assert ruler.tool == "vertical"
    ruler.buttons["vertical"].set_active(False)
    assert ruler.tool == ""
    key = SimpleNamespace(keyval=Gdk.KEY_2, state=Gdk.ModifierType.CONTROL_MASK)
    assert ruler.key_pressed(key)
    assert ruler.tool == "spacing"
    assert ruler.buttons["spacing"].get_active()
    assert not ruler.buttons["vertical"].get_active()


def test_a_click_copies_the_spacing_and_puts_the_tool_away() -> None:
    closed: list[bool] = []
    ruler, copied = make(Options(default_mode="horizontal"))
    ruler.connect("destroy", lambda _window: closed.append(True))
    ruler._on_press(ruler, button(1, 15, 25))
    assert ruler._measured[1] == Rect(10, 20, 39, 29)
    assert copied == ["30"]
    assert closed == []
    assert ruler.tool == ""
    assert not ruler.buttons["horizontal"].get_active()
    ruler._on_press(ruler, button(3, 15, 25))
    assert closed == []


def test_a_box_goes_when_let_go_unless_shift_keeps_it() -> None:
    ruler, copied = make(Options(default_mode="bounds"))
    ruler._on_press(ruler, button(1, 10, 10))
    ruler._on_release(ruler, button(1, 19, 14))
    assert ruler.kept == []
    assert copied == ["10 \N{MULTIPLICATION SIGN} 5"]
    ruler._on_press(ruler, button(1, 50, 50))
    ruler._on_release(ruler, button(1, 40, 45, Gdk.ModifierType.SHIFT_MASK))
    assert ruler.kept == [Rect(40, 45, 50, 50)]
    ruler._on_press(ruler, button(1, 0, 0))
    ruler._on_release(ruler, button(1, 1, 1))
    assert copied[-1] == "11 \N{MULTIPLICATION SIGN} 6\n2 \N{MULTIPLICATION SIGN} 2"
    assert ruler.kept == []


def test_scrolling_changes_the_tolerance() -> None:
    ruler, _copied = make()
    up = SimpleNamespace(direction=Gdk.ScrollDirection.UP)
    down = SimpleNamespace(direction=Gdk.ScrollDirection.DOWN)
    ruler._on_scroll(ruler, up)
    assert ruler.tolerance == 45
    for _step in range(5):
        ruler._on_scroll(ruler, down)
    assert ruler.tolerance == 0


def test_it_draws_every_tool() -> None:
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 100, 80)
    ruler, _copied = make()
    ruler.pointer = (15, 25)
    for tool in ("bounds", "spacing", "horizontal", "vertical"):
        ruler.choose(tool)
        ruler.dragging = (5, 5)
        ruler.draw_over(cairo.Context(surface))
