"""Always on Top's page: whether it is on, its shortcut, and the frame around a pinned
window.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, SettingsLabel, SettingsWidget, Switch, Text  # noqa: E402

from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core import accel  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.modules.alwaysontop.options import MOST_WIDTH, SHORTCUT_KEYS  # noqa: E402
from minttoys.settings.awake_page import SAVE_AFTER_MS  # noqa: E402
from minttoys.settings.simple_page import SimplePage  # noqa: E402
from minttoys.settings.widgets import open_keyboard_settings  # noqa: E402


class Client(Protocol):
    def modules(self) -> list[ModuleInfo]: ...
    def set_module_enabled(self, module_id: str, enabled: bool) -> None: ...
    def module_settings(self, module_id: str) -> dict: ...
    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None: ...
    def alwaysontop_state(self) -> dict: ...


class ColorRow(SettingsWidget):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.content_widget = Gtk.ColorButton(use_alpha=False)
        self.pack_start(self.label, False, False, 0)
        self.pack_end(self.content_widget, False, False, 0)


class WidthRow(SettingsWidget):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.content_widget = Gtk.SpinButton.new_with_range(1, MOST_WIDTH, 1)
        self.pack_start(self.label, False, False, 0)
        # TRANSLATORS: the unit after the frame's width.
        self.pack_end(Gtk.Label(label=_("px")), False, False, 0)
        self.pack_end(self.content_widget, False, False, 0)


class AlwaysOnTopPage(SimplePage):
    def __init__(self, client: Client, show_error: Callable[[str], None]) -> None:
        self._shown: dict[str, object] = {}
        self._save_timer = 0
        self._pending: dict[str, object] = {}
        super().__init__(
            client,
            show_error,
            "alwaysontop",
            _("Always on Top"),
            _("Keeps a window above the others, framed so you can tell which."),
            _("Use Always on Top"),
            [
                _(
                    "Press Super+Ctrl+T on a window to keep it above the others, and again to"
                    " let it go. Its window menu (Alt+Space) can do it too."
                ),
            ],
        )
        self.shortcut_section = self.add_section(
            _("Keyboard shortcut"),
            _("Change its keys in the Keyboard settings, under Windows."),
        )
        self.shortcut = Switch(_("Pin a window with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_flag, "shortcut")
        self.shortcut_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.shortcut_section.add_row(keys)
        self.shortcut_section.add_row(
            Button(_("Open the Keyboard settings"), lambda _b: open_keyboard_settings(show_error))
        )

        self.frame_section = self.add_section(_("Frame"))
        self.border = Switch(_("Frame a pinned window"))
        self.border.content_widget.connect("notify::active", self._on_flag, "border")
        self.frame_section.add_row(self.border)
        self.accent = Switch(_("In the theme's accent color"))
        self.accent.content_widget.connect("notify::active", self._on_accent)
        self.frame_section.add_row(self.accent)
        self.color = ColorRow(_("Color"))
        self.color.content_widget.connect("color-set", self._on_color)
        self.color_revealer = self.frame_section.add_reveal_row(self.color)
        self.width = WidthRow(_("Width"))
        self.width.content_widget.connect("value-changed", self._on_width)
        self.frame_section.add_row(self.width)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        on = self._shown_enabled is True
        settings, state = None, None
        try:
            settings = self._client.module_settings("alwaysontop")
            if on:
                state = self._client.alwaysontop_state()
        except (NotRunning, ModuleOff, Refused):
            pass
        if hasattr(self, "frame_section"):
            if settings is not None:
                self.show_settings(settings)
            self.shortcut_section.set_sensitive(on)
            self.frame_section.set_sensitive(on)
            self.show_state(state)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        self._shown = dict(settings)
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(bool(settings["shortcut"]))
            self.border.content_widget.set_active(bool(settings["border"]))
            color = str(settings["border_color"])
            self.accent.content_widget.set_active(not color)
            if color:
                rgba = Gdk.RGBA()
                rgba.parse(color)
                self.color.content_widget.set_rgba(rgba)
            self.color_revealer.set_reveal_child(bool(color))
            self.width.content_widget.set_value(int(settings["border_width"]))
        finally:
            self._loading = False

    def show_state(self, state: Mapping[str, object] | None) -> None:
        if state is None:
            self.keys.set_text("")
            return
        keys = str(state.get("shortcut", ""))
        if keys:
            key, mods = Gtk.accelerator_parse(keys)
            self.keys.set_text(Gtk.accelerator_get_label(key, mods) if key else keys)
        elif state.get("shortcut_problem") == "taken":
            self.keys.set_text(
                _("Its keyboard shortcut, {keys}, is in use already, so it has none.").format(
                    keys=accel.label(SHORTCUT_KEYS)
                )
            )
        else:
            self.keys.set_text("")

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        self._save({key: switch.get_active()})

    def _on_accent(self, switch: Gtk.Switch, _spec: object) -> None:
        if self._loading:
            return
        self.color_revealer.set_reveal_child(not switch.get_active())
        if switch.get_active():
            self._save({"border_color": ""})
        else:
            self._on_color(self.color.content_widget)

    def _on_color(self, button: Gtk.ColorButton) -> None:
        rgba = button.get_rgba()
        red, green, blue = (round(part * 255) for part in (rgba.red, rgba.green, rgba.blue))
        self._save({"border_color": f"#{red:02x}{green:02x}{blue:02x}"})

    def _on_width(self, field: Gtk.SpinButton) -> None:
        self._save({"border_width": field.get_value_as_int()}, later=True)

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
        try:
            self._client.set_module_settings("alwaysontop", changes)
            self._shown.update(changes)
        except NotRunning:
            pass
        except (ModuleOff, Refused) as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
        self.refresh()
        return GLib.SOURCE_REMOVE
