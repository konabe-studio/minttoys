"""Screen Ruler's page, as PowerToys has it: whether it is on, its keyboard shortcut, the
tool it opens with, the edge detection (how different a pixel has to be, and whether each
color channel counts on its own), feet on the cross, a second unit beside the pixels, and
the line's color. The settings go through the daemon; the shortcut's keys are read from
Cinnamon, where the user may have changed them.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, SettingsWidget, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.shortcut import CustomShortcut  # noqa: E402
from tuxtoys.modules.screenruler.module import ruler_command  # noqa: E402
from tuxtoys.modules.screenruler.options import (  # noqa: E402
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.settings.alwaysontop_page import ColorRow, SliderRow  # noqa: E402
from tuxtoys.settings.colorpicker_page import keys_label  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402
from tuxtoys.settings.widgets import open_keyboard_settings  # noqa: E402

SAVE_AFTER_MS = 400


def open_ruler(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(ruler_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


def with_detail(row: SettingsWidget, detail: str) -> SettingsWidget:
    """The row with a dimmed line under its label that says what it does, as PowerToys'
    settings have.
    """
    row.remove(row.label)
    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    labels.pack_start(row.label, False, False, 0)
    small = Gtk.Label(label=detail, xalign=0, wrap=True, max_width_chars=60)
    small.get_style_context().add_class("dim-label")
    labels.pack_start(small, False, False, 0)
    row.pack_start(labels, True, True, 0)
    row.reorder_child(labels, 0)
    row.content_widget.set_valign(Gtk.Align.CENTER)
    return row


def modes() -> list[tuple[str, str]]:
    return [
        # TRANSLATORS: Screen Ruler opens with none of its tools chosen.
        ("none", _("None")),
        ("bounds", _("Bounds")),
        ("spacing", _("Spacing")),
        ("horizontal", _("Horizontal spacing")),
        ("vertical", _("Vertical spacing")),
    ]


def units() -> list[tuple[str, str]]:
    return [
        # TRANSLATORS: Screen Ruler shows pixels and no second unit.
        ("none", _("Show only pixels")),
        ("in", _("Inches")),
        ("cm", _("Centimeters")),
        ("mm", _("Millimeters")),
    ]


class ScreenRulerPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_ruler,
        shortcut: CustomShortcut | None = None,
    ) -> None:
        """The tests hand in an opener and a shortcut of their own."""
        self._opener = opener
        self._shortcut = shortcut or CustomShortcut(SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS)
        self._loading = False
        self._save_timer = 0
        super().__init__(
            client,
            show_error,
            "screenruler",
            _("Screen Ruler"),
            _("Measures distances and sizes on the screen."),
            _("Use Screen Ruler"),
            [
                _(
                    "Press the shortcut and choose a tool at the top of the screen: drag a"
                    " box to measure it, or point between two edges to measure the space"
                    " between them. A click copies the measurement. Escape or the close"
                    " button leaves the ruler."
                ),
            ],
        )
        self.keys_section = self.add_section(
            _("Activation"),
            _("Change its keys in the Keyboard settings, under TuxToys: Screen Ruler."),
        )
        self.shortcut = Switch(_("Open the ruler with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_flag, "shortcut")
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        # python3-xapp's ComboBox needs its choices from the start.
        self.mode = ComboBox(_("Default mode"), modes())
        with_detail(self.mode, _("The tool chosen when the ruler opens."))
        self.mode.content_widget.connect("changed", self._on_choice, "default_mode")
        self.keys_section.add_row(self.mode)
        self.behaviour = self.add_section(_("Behavior"))
        self.per_channel = Switch(_("Edge detection per color channel"))
        with_detail(
            self.per_channel,
            _(
                "When on, every color channel has to stay within the tolerance. When off,"
                " the differences of all channels added up have to."
            ),
        )
        self.per_channel.content_widget.connect("notify::active", self._on_flag, "per_channel")
        self.behaviour.add_row(self.per_channel)
        self.tolerance = SliderRow(_("Pixel tolerance for edge detection"), 0, 255, 1)
        self.tolerance.content_widget.connect("value-changed", self._on_tolerance)
        self.behaviour.add_row(self.tolerance)
        self.unit = ComboBox(_("Additional unit of measurement"), units())
        self.unit.content_widget.connect("changed", self._on_choice, "extra_unit")
        self.behaviour.add_row(self.unit)
        self.draw_feet = Switch(_("Draw feet on the cross"))
        with_detail(self.draw_feet, _("Adds feet to the ends of the cross's lines."))
        self.draw_feet.content_widget.connect("notify::active", self._on_flag, "draw_feet")
        self.behaviour.add_row(self.draw_feet)
        self.color = ColorRow(_("Line color"))
        self.color.content_widget.connect("color-set", self._on_color)
        self.behaviour.add_row(self.color)
        self.behaviour.add_row(
            Button(_("Measure something now"), lambda *_a: self._opener(show_error))
        )
        self.sections = (self.keys_section, self.behaviour)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("screenruler")
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
            self.keys.set_text(self._keys_text(options.shortcut))
            self.mode.content_widget.set_active_id(options.default_mode)
            self.tolerance.content_widget.set_value(options.tolerance)
            self.per_channel.content_widget.set_active(options.per_channel)
            self.unit.content_widget.set_active_id(options.extra_unit)
            self.draw_feet.content_widget.set_active(options.draw_feet)
            color = Gdk.RGBA()
            color.parse(options.line_color)
            self.color.content_widget.set_rgba(color)
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
            "{keys} is in use already. Give Screen Ruler other keys in the Keyboard settings."
        ).format(keys=keys_label(SHORTCUT_KEYS))

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        if not self._loading:
            self._save({key: switch.get_active()})

    def _on_choice(self, combo: Gtk.ComboBox, key: str) -> None:
        if not self._loading and combo.get_active_id():
            self._save({key: combo.get_active_id()})

    def _on_color(self, button: Gtk.ColorButton) -> None:
        rgba = button.get_rgba()
        red, green, blue = (round(part * 255) for part in (rgba.red, rgba.green, rgba.blue))
        self._save({"line_color": f"#{red:02x}{green:02x}{blue:02x}"})

    def _on_tolerance(self, _scale: Gtk.Scale) -> None:
        if self._loading:
            return
        # Saved once the slider has stopped, not at every step of a drag.
        if self._save_timer:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(SAVE_AFTER_MS, self._save_tolerance)

    def _save_tolerance(self) -> bool:
        self._save_timer = 0
        self._save({"tolerance": round(self.tolerance.content_widget.get_value())})
        return False

    def _save(self, changes: Mapping[str, object]) -> None:
        try:
            self._client.set_module_settings("screenruler", changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
