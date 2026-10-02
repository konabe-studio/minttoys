"""Awake's page: whether Awake is on in MintToys, and what a click on the panel icon starts.

Built from python3-xapp's SettingsWidgets, the rows Linux Mint's own settings windows use.
Those widgets normally bind to GSettings; here their GTK widgets are wired to the daemon
instead, and every change goes there to be checked and saved.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import (  # noqa: E402
    Button,
    ComboBox,
    SettingsLabel,
    SettingsPage,
    SettingsWidget,
    Switch,
)

from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.settings import values  # noqa: E402

# How long the spin buttons wait for the next change before saving, so that holding an
# arrow down saves once, not on every step.
SAVE_AFTER_MS = 400


class Client(Protocol):
    """What the page needs from minttoys.client.Client, which is the real one."""

    def modules(self) -> list[ModuleInfo]: ...
    def set_module_enabled(self, module_id: str, enabled: bool) -> None: ...
    def awake_settings(self) -> dict: ...
    def awake_set_settings(self, changes: Mapping[str, object]) -> None: ...


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
                field.connect("output", _two_digits)
            parts = [self.hours, Gtk.Label(label=":"), self.minutes]
        else:
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


class AwakePage(SettingsPage):
    def __init__(self, client: Client, show_error: Callable[[str], None]) -> None:
        super().__init__()
        self._client = client
        self._show_error = show_error
        self._loading = False
        self._pending: dict[str, object] = {}
        self._save_timer = 0

        self.problem = Gtk.Label(wrap=True, xalign=0)
        self.problem.get_style_context().add_class("dim-label")
        self.problem.set_no_show_all(True)
        self.pack_start(self.problem, False, False, 0)

        awake = self.add_section(
            _("Awake"), _("Keeps the computer awake, without changing your power settings.")
        )
        self.enabled = Switch(_("Use Awake"))
        self.enabled.content_widget.connect("notify::active", self._on_enabled)
        awake.add_row(self.enabled)

        self.click = self.add_section(
            _("When you click the panel icon"),
            _("The same goes for minttoys awake toggle, on a keyboard shortcut or in a script."),
        )
        self.mode = ComboBox(_("Keep the computer awake"), values.modes())
        self.mode.content_widget.connect("changed", self._on_mode)
        self.click.add_row(self.mode)
        self.duration = TimeRow(_("For"), 99, time_of_day=False)
        self.duration_revealer = self.click.add_reveal_row(self.duration)
        self.until = TimeRow(_("Until"), 23, time_of_day=True)
        self.until_revealer = self.click.add_reveal_row(self.until)
        for field in (self.duration.hours, self.duration.minutes):
            field.connect("value-changed", self._on_duration)
        for field in (self.until.hours, self.until.minutes):
            field.connect("value-changed", self._on_until)
        self.keep_screen = Switch(_("Keep the screen on"))
        self.keep_screen.set_tooltip_text(
            _("Otherwise the screen may turn off, but the computer will not sleep.")
        )
        self.keep_screen.content_widget.connect("notify::active", self._on_keep_screen)
        self.click.add_row(self.keep_screen)

        shortcut = self.add_section(
            _("Keyboard shortcut"),
            _("Add a custom shortcut in the Keyboard settings with this command."),
        )
        shortcut.add_row(CommandRow(_("Command"), "minttoys awake toggle"))
        shortcut.add_row(Button(_("Open the Keyboard settings"), self._open_keyboard))

        self.refresh()

    def refresh(self) -> None:
        """Reads from the daemon whether Awake is on, and its settings, and shows them."""
        try:
            info = next((info for info in self._client.modules() if info.id == "awake"), None)
            settings = self._client.awake_settings() if info and info.state == "on" else None
        except NotRunning:
            self._show(None, None, _("MintToys is not running."))
            return
        except ModuleOff:
            info, settings = None, None
        problem = ""
        if info and info.state == "failed":
            problem = _("Awake could not be switched on: {error}").format(error=info.error)
        self._show(info, settings, problem)

    def show_settings(self, settings: Mapping[str, object]) -> None:
        """Shows settings changed elsewhere, the panel icon's check box for one."""
        self._loading = True
        try:
            mode = str(settings["default_mode"])
            self.mode.content_widget.set_active_id(mode)
            self.duration.set(*values.split_minutes(int(settings["default_minutes"])))
            self.until.set(*values.split_time(str(settings["default_until"])))
            self.keep_screen.content_widget.set_active(bool(settings["keep_screen"]))
            self._reveal(mode)
        finally:
            self._loading = False

    def _show(
        self, info: ModuleInfo | None, settings: Mapping[str, object] | None, problem: str
    ) -> None:
        self._loading = True
        try:
            self.enabled.set_sensitive(info is not None)
            self.enabled.content_widget.set_active(bool(info and info.state == "on"))
        finally:
            self._loading = False
        if settings is not None:
            self.show_settings(settings)
        self.click.set_sensitive(settings is not None)
        self.problem.set_text(problem)
        self.problem.set_visible(bool(problem))

    def _reveal(self, mode: str) -> None:
        self.duration_revealer.set_reveal_child(mode == "duration")
        self.until_revealer.set_reveal_child(mode == "until")

    def _on_enabled(self, switch: Gtk.Switch, _spec: object) -> None:
        if self._loading:
            return
        self._call(lambda: self._client.set_module_enabled("awake", switch.get_active()))
        self.refresh()

    def _on_mode(self, combo: Gtk.ComboBox) -> None:
        mode = combo.get_active_id()
        if mode is None:
            return
        self._reveal(mode)
        if not self._loading:
            self._save({"default_mode": mode})

    def _on_duration(self, _field: Gtk.SpinButton) -> None:
        if not self._loading:
            self._save({"default_minutes": values.join_minutes(*self.duration.get())}, later=True)

    def _on_until(self, _field: Gtk.SpinButton) -> None:
        if not self._loading:
            self._save({"default_until": values.join_time(*self.until.get())}, later=True)

    def _on_keep_screen(self, switch: Gtk.Switch, _spec: object) -> None:
        if not self._loading:
            self._save({"keep_screen": switch.get_active()})

    def _save(self, changes: Mapping[str, object], *, later: bool = False) -> None:
        self._pending.update(changes)
        if self._save_timer:
            GLib.source_remove(self._save_timer)
            self._save_timer = 0
        if later:
            self._save_timer = GLib.timeout_add(SAVE_AFTER_MS, self._save_now)
        else:
            self._save_now()

    def _save_now(self) -> bool:
        self._save_timer = 0
        changes, self._pending = self._pending, {}
        if changes and not self._call(lambda: self._client.awake_set_settings(changes)):
            self.refresh()  # puts back what the daemon has
        return GLib.SOURCE_REMOVE

    def _call(self, action: Callable[[], None]) -> bool:
        try:
            action()
        except NotRunning:
            self._show(None, None, _("MintToys is not running."))
            return False
        except (ModuleOff, Refused) as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
            return False
        return True

    def _open_keyboard(self, _button: object) -> None:
        try:
            Gio.Subprocess.new(["cinnamon-settings", "keyboard"], Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            self._show_error(error.message)


def _two_digits(field: Gtk.SpinButton) -> bool:
    field.set_text(f"{field.get_value_as_int():02}")
    return True
