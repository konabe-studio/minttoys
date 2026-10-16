"""The mouse wheel scrolls a settings page instead of turning the fields it passes over.
Needs a display: xvfb in CI, the desktop otherwise.
"""

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)
pytest.importorskip("xapp.SettingsWidgets", reason="python3-xapp is not installed")

from gi.repository import Gdk, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.settings.widgets import scroll_passes_through  # noqa: E402


def wheel_down(widget: Gtk.Widget) -> None:
    event = Gdk.Event.new(Gdk.EventType.SCROLL)
    event.scroll.direction = Gdk.ScrollDirection.DOWN
    event.scroll.window = widget.get_window()
    widget.emit("scroll-event", event)


def page() -> tuple[Gtk.Window, Gtk.ComboBoxText, Gtk.SpinButton]:
    combo = Gtk.ComboBoxText()
    for choice in ("first", "second", "third"):
        combo.append(choice, choice)
    combo.set_active_id("first")
    spin = Gtk.SpinButton.new_with_range(0, 10, 1)
    spin.set_value(5)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.add(combo)
    window = Gtk.Window()
    window.add(box)
    window.show_all()
    return window, combo, spin


def test_the_wheel_leaves_the_fields_alone() -> None:
    window, combo, spin = page()
    window.get_child().add(spin)
    scroll_passes_through(window)
    scroll_passes_through(window)  # again, as rows come: one handler each
    wheel_down(combo)
    wheel_down(spin)
    assert combo.get_active_id() == "first"
    assert spin.get_value() == 5
    window.destroy()


def test_without_it_the_wheel_turns_a_combo_box() -> None:
    """What it guards against, so the test above means something."""
    window, combo, _spin = page()
    wheel_down(combo)
    assert combo.get_active_id() != "first"
    window.destroy()
