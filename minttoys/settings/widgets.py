"""Rows and helpers shared by the tools' pages, in the style of python3-xapp's SettingsWidgets."""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import SettingsLabel, SettingsWidget  # noqa: E402

from minttoys.core.i18n import _  # noqa: E402


class TimeRow(SettingsWidget):
    """A label and two spin buttons: the hours and minutes of a duration, or a time of day,
    which goes round and shows two digits.
    """

    def __init__(self, label: str, most_hours: int, *, time_of_day: bool) -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.hours = Gtk.SpinButton.new_with_range(0, most_hours, 1)
        self.minutes = Gtk.SpinButton.new_with_range(0, 59, 1 if time_of_day else 5)
        box = Gtk.Box(spacing=6)
        if time_of_day:
            for field in (self.hours, self.minutes):
                field.set_wrap(True)
                field.connect("output", two_digits)
            parts = [self.hours, Gtk.Label(label=":"), self.minutes]
        else:
            # TRANSLATORS: the units after the hours field and after the minutes field.
            parts = [self.hours, Gtk.Label(label=_("h")), self.minutes, Gtk.Label(label=_("min"))]
        for part in parts:
            box.pack_start(part, False, False, 0)
        self.content_widget = box
        self.pack_start(self.label, False, False, 0)
        self.pack_end(box, False, False, 0)

    def set(self, hours: int, minutes: int) -> None:
        self.hours.set_value(hours)
        self.minutes.set_value(minutes)

    def get(self) -> tuple[int, int]:
        return self.hours.get_value_as_int(), self.minutes.get_value_as_int()


class CommandRow(SettingsWidget):
    """A label, and a command shown so that it can be selected and copied."""

    def __init__(self, label: str, command: str) -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.content_widget = Gtk.Label(selectable=True)
        self.content_widget.set_markup(f"<tt>{GLib.markup_escape_text(command)}</tt>")
        self.pack_start(self.label, False, False, 0)
        self.pack_end(self.content_widget, False, False, 0)


def two_digits(field: Gtk.SpinButton) -> bool:
    field.set_text(f"{field.get_value_as_int():02}")
    return True


def open_keyboard_settings(show_error: Callable[[str], None]) -> None:
    """Opens Cinnamon's Keyboard settings, where a custom shortcut is added."""
    try:
        Gio.Subprocess.new(["cinnamon-settings", "keyboard"], Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)
