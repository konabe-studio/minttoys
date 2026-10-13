"""Image Resizer's page: whether it is on, how to use it, the sizes the resize window
offers, the JPEG quality, and how a resized picture is named.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk, Pango  # noqa: E402
from xapp.SettingsWidgets import Button, SettingsLabel, SettingsWidget, Switch, Text  # noqa: E402

from minttoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.modules.imageresizer.options import (  # noqa: E402
    FITS,
    MOST_SIZES,
    UNITS,
    Options,
    Size,
    check_size,
)
from minttoys.modules.imageresizer.text import describe, fit_name, unit_name  # noqa: E402
from minttoys.settings.alwaysontop_page import SliderRow  # noqa: E402
from minttoys.settings.awake_page import SAVE_AFTER_MS  # noqa: E402
from minttoys.settings.lightswitch_page import Client  # noqa: E402
from minttoys.settings.simple_page import SimplePage  # noqa: E402


class SizeRow(SettingsWidget):
    """A size: its name and what it is, and buttons to change and remove it."""

    def __init__(self, size: Size) -> None:
        super().__init__()
        self.size = size
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text.pack_start(
            Gtk.Label(label=size.shown_name, xalign=0, ellipsize=Pango.EllipsizeMode.END),
            False,
            False,
            0,
        )
        detail = Gtk.Label(label=describe(size), xalign=0)
        detail.get_style_context().add_class("dim-label")
        text.pack_start(detail, False, False, 0)
        self.pack_start(text, True, True, 0)
        self.edit = _icon_button("document-edit-symbolic", _("Change"))
        self.remove = _icon_button("user-trash-symbolic", _("Remove"))
        self.pack_end(self.remove, False, False, 0)
        self.pack_end(self.edit, False, False, 0)


class FileNameRow(SettingsWidget):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = SettingsLabel(label)
        self.content_widget = Gtk.Entry(width_chars=16)
        self.pack_start(self.label, False, False, 0)
        self.pack_end(self.content_widget, False, False, 0)


class ImageResizerPage(SimplePage):
    def __init__(self, client: Client, show_error: Callable[[str], None]) -> None:
        self._shown = Options()
        self._save_timer = 0
        self._pending: dict[str, object] = {}
        super().__init__(
            client,
            show_error,
            "imageresizer",
            _("Image Resizer"),
            _("Resizes pictures from Nemo's right-click menu."),
            _("Use Image Resizer"),
            [
                _(
                    "Choose one or more pictures in Nemo, right-click them and choose Resize"
                    " with Image Resizer."
                ),
            ],
        )
        self.sizes_section = self.add_section(
            _("Image sizes"), _("The sizes the resize window offers.")
        )
        self.sizes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sizes_section.add_row(self.sizes)
        self.add_button = Button(_("Add a size…"), lambda _b: self._ask_size(None))
        self.sizes_section.add_row(self.add_button)

        self.encoding = self.add_section(_("Encoding"))
        self.quality = SliderRow(_("JPEG quality level (%)"), 1, 100, 1)
        self.quality.content_widget.connect("value-changed", self._on_quality)
        self.encoding.add_row(self.quality)

        self.file = self.add_section(_("File"))
        self.file_name = FileNameRow(_("File name format"))
        self.file_name.content_widget.connect("changed", self._on_file_name)
        self.file.add_row(self.file_name)
        parameters = Text(
            _(
                "%1 the original name, %2 the size's name, %3 and %4 the width and the height"
                " chosen, %5 and %6 the height and the width it comes out at. A slash makes a"
                " folder: %2/%1."
            )
        )
        parameters.content_widget.get_style_context().add_class("dim-label")
        self.file.add_row(parameters)
        self.keep_date = Switch(_("Keep the original's modification date"))
        self.keep_date.content_widget.connect("notify::active", self._on_keep_date)
        self.file.add_row(self.keep_date)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "file"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("imageresizer")
        if settings is not None:
            self.show_settings(settings)
        on = self._shown_enabled is True
        for section in (self.sizes_section, self.encoding, self.file):
            section.set_sensitive(on)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        self._shown = Options.read(settings)
        self._loading = True
        try:
            for child in self.sizes.get_children():
                self.sizes.remove(child)
            for index, size in enumerate(self._shown.sizes):
                row = SizeRow(size)
                row.edit.connect("clicked", lambda _b, i=index: self._ask_size(i))
                row.remove.connect("clicked", lambda _b, i=index: self.remove_size(i))
                self.sizes.pack_start(row, False, False, 0)
            self.sizes.show_all()
            self.add_button.set_sensitive(len(self._shown.sizes) < MOST_SIZES)
            self.quality.content_widget.set_value(self._shown.jpeg_quality)
            entry = self.file_name.content_widget
            if not entry.has_focus() and entry.get_text() != self._shown.file_name:
                entry.set_text(self._shown.file_name)
            self.keep_date.content_widget.set_active(self._shown.keep_date)
        finally:
            self._loading = False

    # The sizes.

    def set_size(self, index: int | None, size: Size) -> None:
        """Puts `size` in place of the one at `index`, or adds it."""
        sizes = list(self._shown.sizes)
        if index is None:
            sizes.append(size)
        else:
            sizes[index] = size
        self._save({"sizes": [s.row() for s in sizes]})

    def remove_size(self, index: int) -> None:
        sizes = [s.row() for i, s in enumerate(self._shown.sizes) if i != index]
        changes: dict[str, object] = {"sizes": sizes}
        if self._shown.selected >= len(sizes):
            changes["selected"] = 0
        self._save(changes)

    def _ask_size(self, index: int | None) -> None:
        size = (
            self._shown.sizes[index] if index is not None else Size(_("New size"), "fit", 1024, 0)
        )
        dialog = Gtk.Dialog(
            title=_("Change the size") if index is not None else _("Add a size"),
            transient_for=self.get_toplevel(),
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        grid = Gtk.Grid(row_spacing=8, column_spacing=12, margin=12)
        name = Gtk.Entry(text=size.shown_name, activates_default=True)
        fit = Gtk.ComboBoxText()
        for value in FITS:
            fit.append(value, fit_name(value))
        fit.set_active_id(size.fit)
        width = Gtk.SpinButton.new_with_range(0, 100_000, 1)
        height = Gtk.SpinButton.new_with_range(0, 100_000, 1)
        unit = Gtk.ComboBoxText()
        for value in UNITS:
            unit.append(value, unit_name(value))
        unit.set_active_id(size.unit)
        for field, value in ((width, size.width), (height, size.height)):
            field.set_digits(2)
            field.set_value(value)
            field.set_tooltip_text(_("Leave it at 0 to keep the proportions."))
            field.set_activates_default(True)
        rows = (
            (_("Name"), name),
            (_("Fit"), fit),
            (_("Width"), width),
            (_("Height"), height),
            (_("Unit"), unit),
        )
        for row, (label, widget) in enumerate(rows):
            grid.attach(Gtk.Label(label=label, xalign=1), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
        dialog.get_content_area().add(grid)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            # A built-in size keeps its name, and with it its translations, unless renamed.
            new_name = name.get_text().strip()
            if index is not None and new_name == size.shown_name:
                new_name = size.name
            try:
                checked = check_size(
                    [
                        new_name,
                        fit.get_active_id(),
                        width.get_value(),
                        height.get_value(),
                        unit.get_active_id(),
                    ]
                )
            except ValueError:
                self._show_error(_("A size needs a name, and a width, a height, or both."))
                continue
            self.set_size(index, checked)
            break
        dialog.destroy()

    # The rest.

    def _on_quality(self, scale: Gtk.Scale) -> None:
        self._save({"jpeg_quality": round(scale.get_value())}, later=True)

    def _on_file_name(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if text:
            self._save({"file_name": text}, later=True)

    def _on_keep_date(self, switch: Gtk.Switch, _spec: object) -> None:
        self._save({"keep_date": switch.get_active()})

    def _save(self, changes: Mapping[str, object], *, later: bool = False) -> None:
        if self._loading:
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
            self._client.set_module_settings("imageresizer", changes)
        except NotRunning:
            pass
        except (ModuleOff, Refused) as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
        self.refresh()
        return GLib.SOURCE_REMOVE


def _icon_button(icon: str, tooltip: str) -> Gtk.Button:
    button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    button.set_relief(Gtk.ReliefStyle.NONE)
    return button
