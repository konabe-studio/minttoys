"""New from template's window: the templates, a name for the new item, and Create."""

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.newplus import templates  # noqa: E402
from tuxtoys.modules.newplus.create import Naming, check, make, ordered  # noqa: E402
from tuxtoys.modules.newplus.names import split_extension  # noqa: E402
from tuxtoys.modules.newplus.templates import (  # noqa: E402
    BadName,
    EmptyName,
    TakenName,
    Template,
    TemplateNameError,
)


def file_icon(template: Template) -> str:
    if template.folder:
        return "folder-symbolic"
    content_type, _uncertain = Gio.content_type_guess(template.path.name, None)
    icon = Gio.content_type_get_symbolic_icon(content_type)
    names = icon.get_names() if isinstance(icon, Gio.ThemedIcon) else []
    return names[0] if names else "text-x-generic-symbolic"


class TemplateRow(Gtk.ListBoxRow):
    def __init__(self, template: Template, shown: str) -> None:
        super().__init__()
        self.template = template
        box = Gtk.Box(spacing=8, margin=6)
        icon = Gtk.Image.new_from_icon_name(file_icon(template), Gtk.IconSize.MENU)
        box.pack_start(icon, False, False, 0)
        box.pack_start(
            Gtk.Label(label=shown, xalign=0, ellipsize=Pango.EllipsizeMode.END), True, True, 0
        )
        self.add(box)


class NewItemWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        target: Path,
        folder: Path | None,
        naming: Naming,
        made: Callable[[Path], None] = lambda path: None,
    ) -> None:
        """`folder` is the templates folder, None when there is none; `made` hears of each
        item made, for the tests.
        """
        super().__init__(application=application, title=_("New from template"))
        self.set_icon_name(APP_ID)
        self.set_default_size(440, 420)
        self.connect("key-press-event", self._on_key)
        self.target = target
        self._naming = naming
        self._made = made

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        heading = Gtk.Label(xalign=0, wrap=True)
        heading.set_markup(
            "<b>{}</b>".format(
                GLib.markup_escape_text(_("New in {folder}").format(folder=target.name or "/"))
            )
        )
        box.pack_start(heading, False, False, 0)
        where = Gtk.Label(label=str(target), xalign=0, wrap=True, selectable=True)
        where.get_style_context().add_class("dim-label")
        box.pack_start(where, False, False, 0)

        found = ordered(templates.templates(folder)) if folder is not None else []
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        for template in found:
            self.list.add(TemplateRow(template, naming.shown(template)))
        self.list.connect("row-selected", self._on_row)
        self.list.connect("row-activated", lambda _list, _row: self.edit_name())
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.list)
        if folder is None:
            text = _("You have no templates folder. Set one up on New+'s page in TuxToys.")
        else:
            text = _(
                "No templates yet. Add some on New+'s page in TuxToys, or right-click a file"
                " in Nemo and choose Save as template."
            )
        self.nothing = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
        self.nothing.get_style_context().add_class("dim-label")
        stack = Gtk.Stack()
        stack.add_named(scroller, "list")
        stack.add_named(self.nothing, "nothing")
        box.pack_start(stack, True, True, 0)

        name_box = Gtk.Box(spacing=8)
        name_box.pack_start(Gtk.Label(label=_("Name")), False, False, 0)
        self.entry = Gtk.Entry(activates_default=True)
        self.entry.connect("changed", lambda _entry: self._check())
        name_box.pack_start(self.entry, True, True, 0)
        box.pack_start(name_box, False, False, 0)
        self.problem = Gtk.Label(xalign=0, wrap=True)
        self.problem.get_style_context().add_class("dim-label")
        box.pack_start(self.problem, False, False, 0)

        buttons = Gtk.Box(spacing=6)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _button: self.close())
        self.create = Gtk.Button(label=_("Create"), can_default=True)
        self.create.get_style_context().add_class("suggested-action")
        self.create.connect("clicked", lambda _button: self.make())
        buttons.pack_end(self.create, False, False, 0)
        buttons.pack_end(cancel, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        self.add(box)
        box.show_all()
        stack.set_visible_child_name("list" if found else "nothing")
        self.create.grab_default()
        first = self.list.get_row_at_index(0)
        if first is not None:
            self.list.select_row(first)
            self.edit_name()
        self._check()

    @property
    def template(self) -> Template | None:
        row = self.list.get_selected_row()
        return row.template if isinstance(row, TemplateRow) else None

    def _on_row(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if not isinstance(row, TemplateRow):
            return
        name = templates.free_name(self.target, self._naming.offered(row.template, self.target))
        self.entry.set_text(name)

    def edit_name(self) -> None:
        """The name ready to type over, its extension kept, as Nemo has it on renaming."""
        template = self.template
        name = self.entry.get_text()
        stem, _extension = (
            (name, "") if template is None or template.folder else split_extension(name)
        )
        self.entry.grab_focus()
        self.entry.select_region(0, len(stem))

    def _check(self) -> bool:
        """Says what is wrong with the name, if anything, and whether Create can be pressed."""
        problem = ""
        try:
            check(self.target, self.entry.get_text())
        except EmptyName:
            pass
        except BadName:
            problem = _("A name cannot hold a slash, or be . or ..")
        except TakenName as error:
            problem = _("There is something called {name} here already.").format(name=str(error))
        else:
            ready = self.template is not None
            self.problem.set_text("")
            self.create.set_sensitive(ready)
            return ready
        self.problem.set_text(problem)
        self.create.set_sensitive(False)
        return False

    def make(self) -> None:
        template = self.template
        if template is None or not self._check():
            return
        name = self.entry.get_text()
        try:
            made = make(template, self.target, name, self._naming)
        except TemplateNameError:
            self._check()
            return
        except OSError as error:
            self.problem.set_text(
                _("Could not make {name}: {error}").format(
                    name=name.strip(), error=error.strerror or error
                )
            )
            return
        self._made(made)
        self.close()

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
