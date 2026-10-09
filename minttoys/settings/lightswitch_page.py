"""Light Switch's page: whether it is on, the day's mode, when it is dark, and switching now.

Built like Awake's page from python3-xapp's SettingsWidgets, wired to the daemon.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, SettingsPage, Switch, Text  # noqa: E402

from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.modules.lightswitch import text  # noqa: E402
from minttoys.settings import values  # noqa: E402
from minttoys.settings.awake_page import SAVE_AFTER_MS  # noqa: E402
from minttoys.settings.widgets import TimeRow, open_keyboard_settings  # noqa: E402


class Client(Protocol):
    """What the page needs from minttoys.client.Client, which is the real one."""

    def modules(self) -> list[ModuleInfo]: ...
    def set_module_enabled(self, module_id: str, enabled: bool) -> None: ...
    def module_settings(self, module_id: str) -> dict: ...
    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None: ...
    def lightswitch_state(self) -> dict: ...
    def lightswitch_toggle(self) -> None: ...


class LightSwitchPage(SettingsPage):
    def __init__(self, client: Client, show_error: Callable[[str], None]) -> None:
        super().__init__()
        self._client = client
        self._show_error = show_error
        # What the daemon last said, as shown; see AwakePage.
        self._shown: dict[str, object] = {}
        self._shown_enabled: bool | None = None
        self._loading = False
        self._pending: dict[str, object] = {}
        self._save_timer = 0

        self.problem = Gtk.Label(wrap=True, xalign=0)
        self.problem.get_style_context().add_class("dim-label")
        self.problem.set_no_show_all(True)
        self.pack_start(self.problem, False, False, 0)

        section = self.add_section(
            _("Light Switch"),
            _("Switches between light and dark by the time of day, keeping your color."),
        )
        self.enabled = Switch(_("Use Light Switch"))
        self.enabled.content_widget.connect("notify::active", self._on_enabled)
        section.add_row(self.enabled)

        self.modes = self.add_section(_("Light and dark"))
        # TRANSLATORS: the label of the choice between the Themes window's Mixed and Light.
        self.day = ComboBox(_("During the day"), values.day_modes())
        self.day.content_widget.connect("changed", self._on_day)
        self.modes.add_row(self.day)
        self.schedule = ComboBox(_("Dark"), values.schedules())
        self.schedule.content_widget.connect("changed", self._on_schedule)
        self.modes.add_row(self.schedule)
        # TRANSLATORS: the labels in front of the times dark starts and ends.
        self.dark_from = TimeRow(_("From"), 23, time_of_day=True)
        self.dark_to = TimeRow(_("To"), 23, time_of_day=True)
        self.from_revealer = self.modes.add_reveal_row(self.dark_from)
        self.to_revealer = self.modes.add_reveal_row(self.dark_to)
        for row in (self.dark_from, self.dark_to):
            for field in (row.hours, row.minutes):
                field.connect("value-changed", self._on_times)
        self.night_light = Button(_("Open the Night Light settings"), self._open_night_light)
        self.night_light_revealer = self.modes.add_reveal_row(self.night_light)

        self.now = self.add_section(_("Right now"))
        hours = Text("")
        self.hours = hours.content_widget
        self.now.add_row(hours)
        self.switch_now = Button(_("Switch now"), self._on_switch_now)
        self.now.add_row(self.switch_now)

        self.shortcut_section = self.add_section(
            _("Keyboard shortcut"),
            _("Change its keys in the Keyboard settings, under MintToys: Light Switch."),
        )
        self.shortcut = Switch(_("Switch now with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_shortcut)
        self.shortcut_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.shortcut_section.add_row(keys)
        self.shortcut_section.add_row(Button(_("Open the Keyboard settings"), self._open_keyboard))

        self.refresh()

    def refresh(self) -> None:
        """Reads from the daemon whether Light Switch is on, its settings and its state."""
        info, settings, state, problem = None, None, None, ""
        try:
            info = next((i for i in self._client.modules() if i.id == "lightswitch"), None)
            if info is None:
                problem = _("This version of MintToys has no Light Switch.")
            else:
                settings = self._client.module_settings("lightswitch")
                if info.state == "on":
                    state = self._client.lightswitch_state()
        except NotRunning:
            info, problem = None, _("MintToys is not running.")
        except (ModuleOff, Refused) as error:
            problem = _("Could not read Light Switch's settings: {error}").format(error=error)
        if info and info.state == "failed":
            problem = _("Light Switch could not be switched on: {error}").format(error=info.error)
        self._show(info, settings, state, problem)

    def show_settings(self, settings: Mapping[str, object]) -> None:
        """Shows settings changed elsewhere."""
        self._shown = dict(settings)
        self._loading = True
        try:
            self.day.content_widget.set_active_id(str(settings["day_mode"]) or "mixed")
            schedule = str(settings["schedule"])
            self.schedule.content_widget.set_active_id(schedule)
            self.dark_from.set(*values.split_time(str(settings["dark_from"])))
            self.dark_to.set(*values.split_time(str(settings["dark_to"])))
            self.shortcut.content_widget.set_active(bool(settings["shortcut"]))
            self._reveal(schedule)
        finally:
            self._loading = False

    def show_state(self, state: Mapping[str, object] | None) -> None:
        """Shows the dark hours and why Light Switch cannot switch, if it cannot."""
        self.keys.set_text("" if state is None else self._keys_text(state))
        if state is None:
            self.hours.set_text("")
            return
        lines = [text.hours(state)]
        if reason := text.problem(state):
            lines.append(reason)
        self.hours.set_text("\n".join(lines))

    def _show(
        self,
        info: ModuleInfo | None,
        settings: Mapping[str, object] | None,
        state: Mapping[str, object] | None,
        problem: str,
    ) -> None:
        self._shown_enabled = info.state == "on" if info else None
        self._loading = True
        try:
            self.enabled.set_sensitive(info is not None)
            self.enabled.content_widget.set_active(bool(self._shown_enabled))
        finally:
            self._loading = False
        if settings is not None:
            self.show_settings(settings)
        on = state is not None
        self.modes.set_sensitive(on)
        self.now.set_sensitive(on)
        self.shortcut_section.set_sensitive(on)
        self.show_state(state)
        self.problem.set_text(problem)
        self.problem.set_visible(bool(problem))

    def _reveal(self, schedule: str) -> None:
        times = schedule == "times"
        self.from_revealer.set_reveal_child(times)
        self.to_revealer.set_reveal_child(times)
        self.night_light_revealer.set_reveal_child(not times)

    def _on_enabled(self, switch: Gtk.Switch, _spec: object) -> None:
        enabled = switch.get_active()
        if self._loading or self._shown_enabled is None or enabled == self._shown_enabled:
            return
        self._call(lambda: self._client.set_module_enabled("lightswitch", enabled))
        self.refresh()

    def _on_day(self, combo: Gtk.ComboBox) -> None:
        self._save({"day_mode": combo.get_active_id()})

    def _on_schedule(self, combo: Gtk.ComboBox) -> None:
        schedule = combo.get_active_id()
        self._reveal(schedule)
        self._save({"schedule": schedule})

    def _on_times(self, _field: Gtk.SpinButton) -> None:
        self._save(
            {
                "dark_from": values.join_time(*self.dark_from.get()),
                "dark_to": values.join_time(*self.dark_to.get()),
            },
            later=True,
        )

    def _save(self, changes: Mapping[str, object], *, later: bool = False) -> None:
        if self._loading:
            return
        changes = {key: value for key, value in changes.items() if self._shown.get(key) != value}
        if not changes:
            return
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
        if not changes:
            return GLib.SOURCE_REMOVE
        if self._call(lambda: self._client.set_module_settings("lightswitch", changes)):
            self._shown.update(changes)
        else:
            self.refresh()  # puts back what the daemon has
        return GLib.SOURCE_REMOVE

    def _on_shortcut(self, switch: Gtk.Switch, _spec: object) -> None:
        if self._loading:
            return
        self._save({"shortcut": switch.get_active()})
        self.refresh()

    @staticmethod
    def _keys_text(state: Mapping[str, object]) -> str:
        """The keys as Cinnamon's Keyboard settings name them, or why there are none."""
        keys = str(state.get("shortcut", ""))
        if keys:
            key, mods = Gtk.accelerator_parse(keys)
            if key:
                return Gtk.accelerator_get_label(key, mods)
        return text.shortcut(state)

    def _on_switch_now(self, _button: object) -> None:
        if self._call(self._client.lightswitch_toggle):
            self.refresh()

    def _call(self, action: Callable[[], None]) -> bool:
        try:
            action()
        except NotRunning:
            self.refresh()
            return False
        except (ModuleOff, Refused) as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
            return False
        return True

    def _open_night_light(self, _button: object) -> None:
        try:
            Gio.Subprocess.new(["cinnamon-settings", "nightlight"], Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            self._show_error(error.message)

    def _open_keyboard(self, _button: object) -> None:
        open_keyboard_settings(self._show_error)
