"""Color Picker's page: whether it is on, its keyboard shortcut, the format a picked color
is copied in, and a button that picks one now. The settings go through the daemon; the
shortcut's keys are read from Cinnamon, where the user may have changed them.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.shortcut import CustomShortcut  # noqa: E402
from tuxtoys.modules.colorpicker.colors import Color, format_color  # noqa: E402
from tuxtoys.modules.colorpicker.module import picker_command  # noqa: E402
from tuxtoys.modules.colorpicker.options import (  # noqa: E402
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402
from tuxtoys.settings.widgets import open_keyboard_settings  # noqa: E402

# The color the format list shows its examples in.
EXAMPLE = Color(0x17, 0xC3, 0xA0)


def open_picker(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(picker_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


def format_choices(options: Options) -> list[tuple[str, str]]:
    """Each format, by name, with an example of how it writes a color."""
    return [
        (name, f"{name}: {format_color(EXAMPLE, template)}")
        for name, template, _shown in options.formats
    ]


def keys_label(keys: str) -> str:
    key, mods = Gtk.accelerator_parse(keys)
    return Gtk.accelerator_get_label(key, mods) if key else keys


class ColorPickerPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_picker,
        shortcut: CustomShortcut | None = None,
    ) -> None:
        """The tests hand in an opener and a shortcut of their own."""
        self._opener = opener
        self._shortcut = shortcut or CustomShortcut(SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS)
        super().__init__(
            client,
            show_error,
            "colorpicker",
            _("Color Picker"),
            _("Picks a color from anywhere on the screen, and copies it."),
            _("Use Color Picker"),
            [
                _(
                    "Press the shortcut, point at a color and click: it is copied in the"
                    " format below. Scroll to zoom in; right-click or Escape to leave."
                ),
            ],
        )
        self.keys_section = self.add_section(
            _("Keyboard shortcut"),
            _("Change its keys in the Keyboard settings, under TuxToys: Color Picker."),
        )
        self.shortcut = Switch(_("Pick a color with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_shortcut)
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        self.picking = self.add_section(_("Picking"))
        # python3-xapp's ComboBox needs its choices from the start.
        self.format = ComboBox(_("Copy colors as"), format_choices(Options()))
        self.format.content_widget.connect("changed", self._on_format)
        self.picking.add_row(self.format)
        self.picking.add_row(Button(_("Pick a color now"), lambda *_a: self._opener(show_error)))
        self.sections = (self.keys_section, self.picking)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("colorpicker")
        if settings is not None:
            self.show_settings(settings)
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = Options.read(settings)
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.format.set_options(format_choices(options))
            self.format.content_widget.set_active_id(options.default_format)
            self.keys.set_text(self._keys_text(options.shortcut))
        finally:
            self._loading = False

    def _keys_text(self, wanted: bool) -> str:
        """The keys as the Keyboard settings name them, or why there are none."""
        if not wanted or self._shown_enabled is not True:
            return ""
        try:
            keys = self._shortcut.current_keys()
        except Exception:  # Cinnamon's settings missing: nothing to show
            return ""
        if keys:
            return keys_label(keys)
        return _(
            "{keys} is in use already. Give Color Picker other keys in the Keyboard settings."
        ).format(keys=keys_label(SHORTCUT_KEYS))

    def _on_shortcut(self, switch: Gtk.Switch, _spec: object) -> None:
        if not self._loading:
            self._save({"shortcut": switch.get_active()})

    def _on_format(self, combo: Gtk.ComboBox) -> None:
        if not self._loading and combo.get_active_id():
            self._save({"default_format": combo.get_active_id()})

    def _save(self, changes: Mapping[str, object]) -> None:
        try:
            self._client.set_module_settings("colorpicker", changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
