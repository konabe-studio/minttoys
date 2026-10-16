"""The shared overlay knows where the pointer is from the start, before the mouse moves.
Needs a display; CI gives it one.
"""

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

from tuxtoys.overlay.window import Overlay  # noqa: E402


def test_the_pointer_is_known_before_the_mouse_moves() -> None:
    screen = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 64, 64)
    screen.fill(0xFFFFFFFF)
    _screen, x, y = Gdk.Display.get_default().get_default_seat().get_pointer().get_position()
    overlay = Overlay(screen)
    assert overlay.pointer == (x, y)
    overlay.destroy()
