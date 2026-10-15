"""Color Picker's page, as PowerToys has it: whether it is on, its keyboard shortcut,
what the shortcut opens first, what each mouse button does, the format a picked color is
copied in, whether the picker names the color, and the formats, each shown or not, to
add, edit, delete and reorder. The settings go through the daemon; the shortcut's keys
are read from Cinnamon, where the user may have changed them.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, SettingsWidget, Switch, Text  # noqa: E402

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


def activations() -> list[tuple[str, str]]:
    return [("pick", _("Pick a color first")), ("editor", _("Open the editor"))]


def actions() -> list[tuple[str, str]]:
    return [
        ("pick-editor", _("Pick a color and open the editor")),
        ("pick-close", _("Pick a color and close")),
        ("close", _("Close")),
    ]


class FormatRow(SettingsWidget):
    """A format: its name and how it writes the example color, a switch for whether the
    editor shows it, and Edit, Delete, Move up and Move down in a menu.
    """

    def __init__(self, page: "ColorPickerPage", index: int, entry: tuple[str, str, bool]) -> None:
        super().__init__()
        name, template, shown = entry
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        texts.pack_start(Gtk.Label(label=name, xalign=0), False, False, 0)
        example = Gtk.Label(label=format_color(EXAMPLE, template), xalign=0, selectable=True)
        example.get_style_context().add_class("dim-label")
        texts.pack_start(example, False, False, 0)
        self.pack_start(texts, True, True, 0)
        self.switch = Gtk.Switch(active=shown, valign=Gtk.Align.CENTER)
        self.switch.connect("notify::active", lambda s, _p: page.set_shown(index, s.get_active()))
        menu = Gtk.Menu()
        for label, action in (
            (_("Edit"), lambda: page.edit_format(index)),
            (_("Delete"), lambda: page.delete_format(index)),
            (_("Move up"), lambda: page.move_format(index, -1)),
            (_("Move down"), lambda: page.move_format(index, 1)),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item, act=action: act())
            menu.append(item)
        menu.show_all()
        button = Gtk.MenuButton(popup=menu, relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER)
        button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
        button.set_tooltip_text(_("More"))
        self.pack_end(button, False, False, 0)
        self.pack_end(self.switch, False, False, 0)


class FormatDialog(Gtk.Dialog):
    """A format's name and template, with the example color written in it as it is typed,
    and what a template can hold.
    """

    def __init__(
        self, parent: Gtk.Window | None, name: str, template: str, taken: set[str]
    ) -> None:
        super().__init__(title=_("Color format"), transient_for=parent, modal=True)
        self.set_default_size(460, -1)
        self._taken = taken
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.ok = self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.ok.get_style_context().add_class("suggested-action")
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=18)
        grid.attach(Gtk.Label(label=_("Name"), xalign=0), 0, 0, 1, 1)
        self.name = Gtk.Entry(text=name, hexpand=True)
        grid.attach(self.name, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=_("Format"), xalign=0), 0, 1, 1, 1)
        self.template = Gtk.Entry(text=template or "rgb(%Re, %Gr, %Bl)", hexpand=True)
        grid.attach(self.template, 1, 1, 1, 1)
        self.example = Gtk.Label(xalign=0, selectable=True)
        self.example.get_style_context().add_class("dim-label")
        grid.attach(self.example, 1, 2, 1, 1)
        help_text = Gtk.Label(
            label=_(
                "%Re, %Gr, %Bl: red, green, blue. %Hu: hue. %Sl, %Ll: HSL's saturation and"
                " lightness. %Sb, %Va: HSV's. %Cy, %Ma, %Ye, %Bk: CMYK. A letter after one"
                " changes how it is written: x or X two hex digits, f a fraction, i a whole"
                " number."
            ),
            xalign=0,
            wrap=True,
            max_width_chars=60,
        )
        help_text.get_style_context().add_class("dim-label")
        grid.attach(help_text, 1, 3, 1, 1)
        for field in (self.name, self.template):
            field.connect("changed", lambda _field: self.check())
        self.get_content_area().add(grid)
        self.get_content_area().show_all()
        self.check()

    @property
    def entry(self) -> tuple[str, str]:
        return self.name.get_text().strip(), self.template.get_text()

    def check(self) -> None:
        name, template = self.entry
        self.example.set_text(format_color(EXAMPLE, template))
        self.ok.set_sensitive(bool(name) and bool(template) and name not in self._taken)


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
        self.behaviour = self.add_section(_("Behavior"))
        # python3-xapp's ComboBox needs its choices from the start.
        self.activation = ComboBox(_("When the shortcut is pressed"), activations())
        self.activation.content_widget.connect("changed", self._on_choice, "activation")
        self.behaviour.add_row(self.activation)
        self.buttons = {}
        for key, label in (
            ("left", _("Left click")),
            ("middle", _("Middle click")),
            ("right", _("Right click")),
        ):
            combo = ComboBox(label, actions())
            combo.content_widget.connect("changed", self._on_choice, key)
            self.behaviour.add_row(combo)
            self.buttons[key] = combo
        self.picking = self.add_section(_("Picking"))
        self.format = ComboBox(_("Copy colors as"), format_choices(Options()))
        self.format.content_widget.connect("changed", self._on_format)
        self.picking.add_row(self.format)
        self.show_name = Switch(_("Show the color's name"))
        self.show_name.content_widget.connect("notify::active", self._on_show_name)
        self.picking.add_row(self.show_name)
        self.picking.add_row(Button(_("Pick a color now"), lambda *_a: self._opener(show_error)))
        self.formats_section = self.add_section(
            _("Color formats"), _("The ones switched on are shown in the editor.")
        )
        self.formats_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.formats_section.add_row(self.formats_list)
        self.formats_section.add_row(Button(_("Add a format"), lambda *_a: self.add_format()))
        self.options = Options()
        self.sections = (self.keys_section, self.behaviour, self.picking, self.formats_section)
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
        self.options = options
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.activation.content_widget.set_active_id(options.activation)
            for key, combo in self.buttons.items():
                combo.content_widget.set_active_id(getattr(options, key))
            self.format.set_options(format_choices(options))
            self.format.content_widget.set_active_id(options.default_format)
            self.show_name.content_widget.set_active(options.show_name)
            self.keys.set_text(self._keys_text(options.shortcut))
            for child in self.formats_list.get_children():
                self.formats_list.remove(child)
            for index, entry in enumerate(options.formats):
                self.formats_list.pack_start(FormatRow(self, index, entry), False, False, 0)
            self.formats_list.show_all()
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

    def _on_choice(self, combo: Gtk.ComboBox, key: str) -> None:
        if not self._loading and combo.get_active_id():
            self._save({key: combo.get_active_id()})

    def _on_show_name(self, switch: Gtk.Switch, _spec: object) -> None:
        if not self._loading:
            self._save({"show_name": switch.get_active()})

    def _save_formats(self, formats: list[tuple[str, str, bool]]) -> None:
        self._save({"formats": [list(entry) for entry in formats]})

    def set_shown(self, index: int, shown: bool) -> None:
        if self._loading:
            return
        formats = list(self.options.formats)
        name, template, _old = formats[index]
        formats[index] = (name, template, shown)
        GLib.idle_add(lambda: self._save_formats(formats) and False)

    def move_format(self, index: int, step: int) -> None:
        formats = list(self.options.formats)
        other = index + step
        if 0 <= other < len(formats):
            formats[index], formats[other] = formats[other], formats[index]
            self._save_formats(formats)

    def delete_format(self, index: int) -> None:
        formats = list(self.options.formats)
        if len(formats) > 1:
            del formats[index]
            self._save_formats(formats)

    def add_format(self) -> None:
        self._format_dialog(None)

    def edit_format(self, index: int) -> None:
        self._format_dialog(index)

    def _format_dialog(self, index: int | None) -> None:
        formats = list(self.options.formats)
        name, template, shown = formats[index] if index is not None else ("", "", True)
        taken = {entry[0] for i, entry in enumerate(formats) if i != index}
        parent = self.get_toplevel()
        dialog = FormatDialog(
            parent if isinstance(parent, Gtk.Window) else None, name, template, taken
        )
        if dialog.run() == Gtk.ResponseType.OK:
            new_name, new_template = dialog.entry
            if index is None:
                formats.append((new_name, new_template, True))
            else:
                formats[index] = (new_name, new_template, shown)
            self._save_formats(formats)
        dialog.destroy()

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
