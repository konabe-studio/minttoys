"""Always on Top's page: whether it is on, its shortcuts, the frame around a pinned window,
its sound, and the applications it leaves alone.
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
from minttoys.modules.alwaysontop.options import (  # noqa: E402
    LEAST_OPACITY,
    LESS_OPAQUE_KEYS,
    MORE_OPAQUE_KEYS,
    MOST_RADIUS,
    MOST_WIDTH,
    SHORTCUT_KEYS,
)
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


class SliderRow(SettingsWidget):
    """A label, and a slider of whole numbers with its value, and the unit after it if any."""

    def __init__(self, label: str, least: int, most: int, step: int, unit: str = "") -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.content_widget = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, least, most, step
        )
        self.content_widget.set_digits(0)
        self.content_widget.set_round_digits(0)
        if unit:
            self.content_widget.connect(
                "format-value", lambda _scale, value: f"{round(value)} {unit}"
            )
        # The value before the slider: after it, it would stick out past the rows above.
        self.content_widget.set_value_pos(Gtk.PositionType.LEFT)
        self.content_widget.set_size_request(200, -1)
        self.pack_start(self.label, False, False, 0)
        self.pack_end(self.content_widget, False, False, 0)


class AppsRow(SettingsWidget):
    """Application names, one on each line."""

    def __init__(self) -> None:
        super().__init__()
        self.content_widget = Gtk.TextView(accepts_tab=False)
        self.content_widget.set_monospace(True)
        self.content_widget.set_left_margin(6)
        self.content_widget.set_top_margin(4)
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scroller.set_size_request(-1, 90)
        scroller.add(self.content_widget)
        self.pack_start(scroller, True, True, 0)

    @property
    def text(self) -> str:
        buffer = self.content_widget.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    @text.setter
    def text(self, value: str) -> None:
        self.content_widget.get_buffer().set_text(value)


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
            _("Keyboard shortcuts"),
            _("Change their keys in the Keyboard settings."),
        )
        self.shortcut = Switch(_("Pin a window with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_flag, "shortcut")
        self.shortcut_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.shortcut_section.add_row(keys)
        self.opacity_shortcuts = Switch(_("Change a pinned window's opacity with the keyboard"))
        self.opacity_shortcuts.content_widget.connect(
            "notify::active", self._on_flag, "opacity_shortcuts"
        )
        self.shortcut_section.add_row(self.opacity_shortcuts)
        opacity_keys = Text("")
        self.opacity_keys = opacity_keys.content_widget
        self.shortcut_section.add_row(opacity_keys)
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
        # TRANSLATORS: the unit after the frame's width and its corners' radius.
        pixels = _("px")
        self.width = SliderRow(_("Width"), 1, MOST_WIDTH, 1, pixels)
        self.width.content_widget.connect("value-changed", self._on_slider, "border_width")
        self.frame_section.add_row(self.width)
        self.opacity = SliderRow(_("Opacity (%)"), LEAST_OPACITY, 100, 5)
        self.opacity.content_widget.connect("value-changed", self._on_slider, "border_opacity")
        self.frame_section.add_row(self.opacity)
        self.radius = SliderRow(_("Rounded corners"), 0, MOST_RADIUS, 1, pixels)
        self.radius.set_tooltip_text(_("0 for square corners."))
        self.radius.content_widget.connect("value-changed", self._on_slider, "border_radius")
        self.frame_section.add_row(self.radius)

        self.sound_section = self.add_section(_("Sound"))
        self.sound = Switch(_("Play a sound on pinning and letting go"))
        self.sound.set_tooltip_text(
            _("The Sound settings' sounds for maximizing and unmaximizing windows.")
        )
        self.sound.content_widget.connect("notify::active", self._on_flag, "sound")
        self.sound_section.add_row(self.sound)

        self.excluded_section = self.add_section(
            _("Excluded applications"),
            _(
                "Never kept on top. One on each line, by the name X11 knows it by"
                " (its WM_CLASS), for example firefox."
            ),
        )
        self.excluded = AppsRow()
        self.excluded.content_widget.get_buffer().connect("changed", self._on_excluded)
        self.excluded_section.add_row(self.excluded)
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
        if hasattr(self, "excluded_section"):
            if settings is not None:
                self.show_settings(settings)
            for section in (
                self.shortcut_section,
                self.frame_section,
                self.sound_section,
                self.excluded_section,
            ):
                section.set_sensitive(on)
            self.show_state(state)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        self._shown = dict(settings)
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(bool(settings["shortcut"]))
            self.opacity_shortcuts.content_widget.set_active(bool(settings["opacity_shortcuts"]))
            self.border.content_widget.set_active(bool(settings["border"]))
            color = str(settings["border_color"])
            self.accent.content_widget.set_active(not color)
            if color:
                rgba = Gdk.RGBA()
                rgba.parse(color)
                self.color.content_widget.set_rgba(rgba)
            self.color_revealer.set_reveal_child(bool(color))
            self.width.content_widget.set_value(int(settings["border_width"]))
            self.opacity.content_widget.set_value(int(settings["border_opacity"]))
            self.radius.content_widget.set_value(int(settings["border_radius"]))
            self.sound.content_widget.set_active(bool(settings["sound"]))
            excluded = str(settings["excluded"])
            # Not while it is being typed in: the cursor would jump.
            if not self.excluded.content_widget.has_focus() and self.excluded.text != excluded:
                self.excluded.text = excluded
        finally:
            self._loading = False

    def show_state(self, state: Mapping[str, object] | None) -> None:
        if state is None:
            self.keys.set_text("")
            self.opacity_keys.set_text("")
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
        if state.get("opacity_problem") == "taken":
            self.opacity_keys.set_text(
                _("{more} or {less} is in use already, so that shortcut is missing.").format(
                    more=accel.label(MORE_OPAQUE_KEYS), less=accel.label(LESS_OPAQUE_KEYS)
                )
            )
        elif self._shown.get("opacity_shortcuts"):
            self.opacity_keys.set_text(
                _("{more} more opaque, {less} less").format(
                    more=accel.label(MORE_OPAQUE_KEYS), less=accel.label(LESS_OPAQUE_KEYS)
                )
            )
        else:
            self.opacity_keys.set_text("")

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

    def _on_slider(self, scale: Gtk.Scale, key: str) -> None:
        self._save({key: round(scale.get_value())}, later=True)

    def _on_excluded(self, _buffer: Gtk.TextBuffer) -> None:
        self._save({"excluded": self.excluded.text}, later=True)

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
