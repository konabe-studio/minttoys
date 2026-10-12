"""New+'s page: whether it is on, how to use it, the templates themselves, to add, rename
and remove, and how New from template names what it makes. The templates are plain files,
so the page handles them itself and needs no daemon for them; the two naming settings go
through the daemon.
"""

import os
import subprocess
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402
from xapp.SettingsWidgets import Button, SettingsWidget, Switch, Text  # noqa: E402

from minttoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.modules.newplus import templates  # noqa: E402
from minttoys.modules.newplus.templates import (  # noqa: E402
    BadName,
    EmptyName,
    TakenName,
    Template,
    TemplateNameError,
)
from minttoys.newplus.main import config_home  # noqa: E402
from minttoys.settings.lightswitch_page import Client  # noqa: E402
from minttoys.settings.simple_page import SimplePage  # noqa: E402


def users_folder() -> Path | None:
    return templates.templates_dir(Path.home(), config_home())


def trash(path: Path) -> None:
    Gio.File.new_for_path(str(path)).trash(None)


class TemplateRow(SettingsWidget):
    """A template: its icon and name, and buttons to rename and remove it."""

    def __init__(self, template: Template) -> None:
        super().__init__()
        self.template = template
        icon = "folder-symbolic" if template.folder else _file_icon(template.path)
        self.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
        self.name = Gtk.Label(label=template.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.pack_start(self.name, True, True, 0)
        self.rename = _icon_button("document-edit-symbolic", _("Rename"))
        self.remove = _icon_button("user-trash-symbolic", _("Move to the trash"))
        self.pack_end(self.remove, False, False, 0)
        self.pack_end(self.rename, False, False, 0)


class NewPlusPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        folder: Callable[[], Path | None] = users_folder,
        to_trash: Callable[[Path], None] = trash,
    ) -> None:
        """The tests hand in a folder of their own, and a trash that only deletes."""
        self._folder = folder
        self._trash = to_trash
        self._monitor: Gio.FileMonitor | None = None
        super().__init__(
            client,
            show_error,
            "newplus",
            _("New+"),
            _("Your own templates for Nemo's Create New Document."),
            _("Use New+"),
            [
                _(
                    "Right-click inside a folder in Nemo and choose New from template… to make a"
                    " file or a folder from one of your templates."
                ),
                _("Nemo's own Create New Document offers your file templates too."),
                _("Right-click a file and choose Save as template to add it."),
            ],
        )
        self.templates = self.add_section(
            _("Templates"),
            _(
                "A new item starts as a copy of one of these. A folder is copied whole; Create"
                " New Document shows it as a submenu of its files instead."
            ),
        )
        self.where = Text("")
        self.templates.add_row(self.where)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.templates.add_row(self.list)
        self.add_button = Button(_("Add a template…"), self._on_add)
        self.templates.add_row(self.add_button)
        self.open_button = Button(_("Open the templates folder"), self._on_open)
        self.templates.add_row(self.open_button)
        self.make_button = Button(_("Make a templates folder"), self._on_make)
        self.templates.add_row(self.make_button)
        self.names = self.add_section(
            _("Names"), _("Of the files and folders New from template makes.")
        )
        self.variables = Switch(_("Replace variables in names"))
        self.variables.content_widget.connect("notify::active", self._on_flag, "replace_variables")
        self.names.add_row(self.variables)
        variables = Text(
            _(
                "$YYYY, $MM, $DD, $hh, $mm, $ss and more for the date and time,"
                " $PARENT_FOLDER_NAME for the folder an item lands in, and %VARIABLE% from the"
                " environment, such as %USER%."
            )
        )
        variables.content_widget.get_style_context().add_class("dim-label")
        self.names.add_row(variables)
        self.digits = Switch(_("Leave out the number a template's name starts with"))
        self.digits.content_widget.connect("notify::active", self._on_flag, "hide_digits")
        self.names.add_row(self.digits)
        digits = Text(_("Number your templates to set their order, as in 1. Letter.odt."))
        digits.content_widget.get_style_context().add_class("dim-label")
        self.names.add_row(digits)
        self.show_templates()
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "names"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("newplus")
        if settings is not None:
            self.show_settings(settings)
        self.names.set_sensitive(self._shown_enabled is True)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        self._loading = True
        try:
            self.variables.content_widget.set_active(bool(settings.get("replace_variables")))
            self.digits.content_widget.set_active(bool(settings.get("hide_digits")))
        finally:
            self._loading = False

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        if self._loading:
            return
        try:
            self._client.set_module_settings("newplus", {key: switch.get_active()})
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
        self.refresh()

    @property
    def folder(self) -> Path | None:
        return self._folder()

    def show_templates(self) -> None:
        """Lists the templates as the folder has them now."""
        folder = self.folder
        for child in self.list.get_children():
            self.list.remove(child)
        has_folder = folder is not None
        _show_row(self.add_button, has_folder)
        _show_row(self.open_button, has_folder)
        _show_row(self.make_button, not has_folder)
        if folder is None:
            self.where.content_widget.set_text(_("You have no templates folder."))
            return
        self.where.content_widget.set_text(str(folder))
        self._watch(folder)
        found = templates.templates(folder)
        if not found:
            empty = Text(_("No templates yet."))
            empty.content_widget.get_style_context().add_class("dim-label")
            self.list.pack_start(empty, False, False, 0)
        for template in found:
            row = TemplateRow(template)
            row.rename.connect("clicked", lambda _b, t=template: self._ask_rename(t))
            row.remove.connect("clicked", lambda _b, t=template: self.remove(t))
            self.list.pack_start(row, False, False, 0)
        self.list.show_all()

    def add_files(self, paths: list[Path]) -> None:
        folder = self.folder
        if folder is None:
            return
        for path in paths:
            try:
                templates.add(folder, path)
            except OSError as error:
                self._show_error(
                    _("Could not add {name}: {error}").format(name=path.name, error=error.strerror)
                )
        self.show_templates()

    def rename(self, template: Template, name: str) -> bool:
        """Renames a template; says why not, and returns False, when the name cannot be."""
        folder = self.folder
        if folder is None:
            return False
        try:
            name = templates.check_name(folder, template, name)
            if name != template.name:
                os.rename(template.path, folder / name)
        except TemplateNameError as error:
            self._show_error(_name_problem(error))
            return False
        except OSError as error:
            self._show_error(error.strerror or str(error))
            return False
        self.show_templates()
        return True

    def remove(self, template: Template) -> None:
        try:
            self._trash(template.path)
        except (GLib.Error, OSError) as error:
            self._show_error(getattr(error, "message", None) or str(error))
        self.show_templates()

    def _watch(self, folder: Path) -> None:
        if self._monitor is not None:
            return
        try:
            self._monitor = Gio.File.new_for_path(str(folder)).monitor_directory(
                Gio.FileMonitorFlags.WATCH_MOVES, None
            )
            self._monitor.connect("changed", lambda *_: self.show_templates())
        except GLib.Error:
            self._monitor = None

    def _ask_rename(self, template: Template) -> None:
        dialog = Gtk.Dialog(title=_("Rename"), transient_for=self.get_toplevel(), modal=True)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Rename"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        entry = Gtk.Entry(text=template.name, activates_default=True, margin=12)
        dialog.get_content_area().add(entry)
        dialog.show_all()
        stem = template.name.rpartition(".")[0]
        entry.select_region(0, len(stem) if stem and not template.folder else -1)
        if dialog.run() == Gtk.ResponseType.OK:
            self.rename(template, entry.get_text())
        dialog.destroy()

    def _on_add(self, _button: object) -> None:
        dialog = Gtk.FileChooserNative(
            title=_("Add a template"),
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
            select_multiple=True,
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.add_files([Path(name) for name in dialog.get_filenames()])
        dialog.destroy()

    def _on_open(self, _button: object) -> None:
        if self.folder is not None:
            Gio.AppInfo.launch_default_for_uri(self.folder.as_uri(), None)

    def _on_make(self, _button: object) -> None:
        """Makes ~/Templates and sets it as the templates folder, as xdg-user-dirs does."""
        folder = Path.home() / "Templates"
        try:
            folder.mkdir(exist_ok=True)
            subprocess.run(["xdg-user-dirs-update", "--set", "TEMPLATES", str(folder)], check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            self._show_error(str(error))
        self.show_templates()


def _show_row(widget: Gtk.Widget, visible: bool) -> None:
    """Shows or hides the section row that holds `widget`, and keeps the window's show_all()
    from showing it again.
    """
    row = widget.get_parent() or widget
    row.set_no_show_all(True)
    row.set_visible(visible)
    if visible:
        widget.show_all()


def _name_problem(error: TemplateNameError) -> str:
    if isinstance(error, EmptyName):
        return _("A template needs a name.")
    if isinstance(error, BadName):
        return _("A name cannot hold a slash, or be . or ..")
    if isinstance(error, TakenName):
        return _("There is a template called {name} already.").format(name=str(error))
    return str(error)


def _file_icon(path: Path) -> str:
    content_type, _uncertain = Gio.content_type_guess(path.name, None)
    icon = Gio.content_type_get_symbolic_icon(content_type)
    names = icon.get_names() if isinstance(icon, Gio.ThemedIcon) else []
    return names[0] if names else "text-x-generic-symbolic"


def _icon_button(icon: str, tooltip: str) -> Gtk.Button:
    button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    button.set_relief(Gtk.ReliefStyle.NONE)
    return button
