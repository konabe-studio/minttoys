"""Text Extractor's window on a made-up screen: the formats, the keys, the language, and
what a drag or a click asks to read. Needs a display; CI gives it one.
"""

from types import SimpleNamespace

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.overlay.monitors import Monitor  # noqa: E402
from tuxtoys.textextractor.reading import Region, Request  # noqa: E402
from tuxtoys.textextractor.window import Extractor, spanned  # noqa: E402


def make() -> tuple[Extractor, list[Request | None], list[bool]]:
    screen = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 200, 100)
    screen.fill(0xFFFFFFFF)
    asked: list[Request | None] = []
    settings: list[bool] = []
    window = Extractor(
        screen,
        [Monitor(0, 0, 200, 100)],
        (5, 5),
        ["eng", "hun"],
        "hun",
        asked.append,
        lambda: settings.append(True),
    )
    return window, asked, settings


def button(number: int, x: int, y: int) -> SimpleNamespace:
    return SimpleNamespace(button=number, x=x, y=y, state=Gdk.ModifierType(0))


def motion(x: int, y: int, state: int = 0) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y, state=Gdk.ModifierType(state))


def key(keyval: int) -> SimpleNamespace:
    return SimpleNamespace(keyval=keyval, state=Gdk.ModifierType(0))


def test_single_line_and_table_exclude_each_other() -> None:
    window, _asked, _settings = make()
    assert window.mode == "text"
    assert window.key_pressed(key(Gdk.KEY_s))
    assert window.mode == "single"
    assert window.single.get_active()
    window.table.set_active(True)
    assert window.mode == "table"
    assert not window.single.get_active()
    assert window.key_pressed(key(Gdk.KEY_t))
    assert window.mode == "text"
    assert not window.table.get_active()


def test_a_drag_asks_for_its_region() -> None:
    window, asked, _settings = make()
    window.set_mode("single")
    window._on_press(window, button(1, 10, 20))
    window._on_motion(window, motion(50, 40))
    window._on_release(window, button(1, 50, 40))
    assert asked == [Request(Region(10, 20, 41, 21), "single", "hun")]


def test_shift_moves_the_region() -> None:
    window, _asked, _settings = make()
    window._on_press(window, button(1, 10, 10))
    window._on_motion(window, motion(30, 30))
    window._on_motion(window, motion(40, 35, Gdk.ModifierType.SHIFT_MASK))
    assert window.region == Region(20, 15, 21, 21)


def test_a_click_asks_for_the_word_under_it() -> None:
    window, asked, _settings = make()
    window._on_press(window, button(1, 100, 50))
    window._on_release(window, button(1, 101, 50))
    assert asked == [Request(Region(0, 0, 200, 100), "word", "hun", (101, 50))]


def test_another_language_can_be_chosen() -> None:
    window, _asked, _settings = make()
    assert window.language_button.get_label() == "Magyar"
    window._on_language(SimpleNamespace(get_active=lambda: True), "eng")
    assert window.language == "eng"
    assert window.language_button.get_label() == "English"


def test_closing_asks_for_nothing() -> None:
    window, asked, _settings = make()
    window.close_overlay()
    assert asked == [None]


def test_the_region_between_two_corners() -> None:
    assert spanned((50, 40), (10, 20)) == Region(10, 20, 41, 21)
