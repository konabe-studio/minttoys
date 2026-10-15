"""Environment Variables' window, laid out as PowerToys' is: the profiles and the default
variables, the user's and the system's, on the left; the variables that apply on the
right, the search path first.

The user's variables and the profiles are TuxToys settings, saved through the daemon as
soon as they change; the daemon writes the file the session loads. The system's are
/etc/environment, saved through pkexec on Save, as Hosts File Editor saves /etc/hosts.
A change made to it elsewhere is picked up when nothing is unsaved, reported otherwise.
"""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core import pkexec  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.envvars import saving, variables  # noqa: E402
from tuxtoys.modules.envvars.options import Options, Profile  # noqa: E402
from tuxtoys.modules.envvars.save import ENVIRONMENT  # noqa: E402
from tuxtoys.modules.envvars.systemfile import SystemFile  # noqa: E402

type Runner = Callable[[list[str], bytes, pkexec.Done], None]
type Pairs = Sequence[tuple[str, str]]

WARNING_ICON = "dialog-warning-symbolic"
CSS = b"""
entry image.right { color: @warning_color; }
image.tuxtoys-warning { color: @warning_color; }
"""
ORIGIN_ICONS = {
    "system": "computer-symbolic",
    "user": "avatar-default-symbolic",
    "profile": "view-list-symbolic",
    "login": "system-run-symbolic",
}
LOGIN_DEFS = Path("/etc/login.defs")


def bold(text: str) -> str:
    """Markup for a heading. The message is passed in, never written inside an f-string,
    where xgettext would not find it.
    """
    return f"<b>{GLib.markup_escape_text(text)}</b>"


def heading(text: str) -> Gtk.Label:
    label = Gtk.Label(xalign=0, margin_top=6)
    label.set_markup(bold(text))
    return label


def dim(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0, wrap=True)
    label.get_style_context().add_class("dim-label")
    return label


def _warn(field: Gtk.Entry, problem: str | None) -> None:
    field.set_icon_from_icon_name(
        Gtk.EntryIconPosition.SECONDARY, WARNING_ICON if problem else None
    )
    field.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, problem)


def login_base(login_defs: Path = LOGIN_DEFS) -> dict[str, str]:
    """What a login has before any variable is set: the home folder and the search path."""
    try:
        text = login_defs.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return {"HOME": str(Path.home()), "PATH": variables.login_path(text)}


class Client(Protocol):
    def module_settings(self, module_id: str) -> dict: ...
    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None: ...


class VariableDialog(Gtk.Dialog):
    """A variable's name and value; a list, such as PATH, one item a line."""

    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        name: str = "",
        value: str = "",
        taken: frozenset[str] = frozenset(),
        system: bool = False,
    ) -> None:
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(480, -1)
        self._taken = taken
        self._system = system
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.ok = self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=18)
        grid.attach(Gtk.Label(label=_("Name"), xalign=0), 0, 0, 1, 1)
        self.name = Gtk.Entry(text=name, hexpand=True, activates_default=True)
        self.name.connect("changed", lambda _entry: self.check())
        grid.attach(self.name, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=_("Value"), xalign=0, yalign=0), 0, 1, 1, 1)
        self.stack = Gtk.Stack()
        self.value = Gtk.Entry(text=value, hexpand=True, activates_default=True)
        self.value.connect("changed", lambda _entry: self.check())
        self.stack.add_named(self.value, "line")
        self.items = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
        self.items.get_buffer().connect("changed", lambda _buffer: self.check())
        scrolled = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, min_content_height=160)
        scrolled.add(self.items)
        self.stack.add_named(scrolled, "list")
        grid.attach(self.stack, 1, 1, 1, 1)
        self.as_list = Gtk.CheckButton(label=_("Edit as a list, one folder a line"))
        self.as_list.connect("toggled", self._on_as_list)
        grid.attach(self.as_list, 1, 2, 1, 1)
        if not system:
            grid.attach(dim(_("$HOME and $PATH stand for those variables' values.")), 1, 3, 1, 1)
        self.get_content_area().add(grid)
        self.get_content_area().show_all()
        self.as_list.set_active(variables.is_list(name, value))
        self.check()

    def _on_as_list(self, check: Gtk.CheckButton) -> None:
        if check.get_active():
            self.items.get_buffer().set_text("\n".join(variables.split_list(self.value.get_text())))
            self.stack.set_visible_child_name("list")
        else:
            self.value.set_text(self._joined())
            self.stack.set_visible_child_name("line")
        self.check()

    def _lines(self) -> list[str]:
        buffer = self.items.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        return [line.strip() for line in text.splitlines()]

    def _joined(self) -> str:
        return variables.join_list(self._lines())

    @property
    def variable(self) -> tuple[str, str]:
        value = self._joined() if self.as_list.get_active() else self.value.get_text()
        return self.name.get_text().strip(), value

    def check(self) -> None:
        """Marks a name or a value that cannot be, and allows Save only when neither is."""
        name, value = self.variable
        if not name:
            name_problem = None
        elif not variables.is_name(name):
            name_problem = _("Letters, digits and _, not starting with a digit.")
        elif name in self._taken:
            name_problem = _("There is a variable of this name already.")
        else:
            name_problem = None
        value_problem = None
        if self.as_list.get_active() and any(":" in line for line in self._lines()):
            value_problem = _("A folder in the list cannot hold a colon.")
        elif not variables.is_value(value):
            value_problem = _("The value has to be one line.")
        elif self._system and '"' in value and "'" in value:
            value_problem = _("A system variable cannot hold both kinds of quotes.")
        _warn(self.name, name_problem)
        _warn(self.value, value_problem)
        self.ok.set_sensitive(bool(name) and not name_problem and not value_problem)


class ProfileDialog(Gtk.Dialog):
    """A profile's name and variables. Its variables can be new, or copies of the user's
    or the system's to change.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        profile: Profile | None,
        taken: frozenset[str],
        existing: Pairs,
    ) -> None:
        title = _("New profile") if profile is None else _("Edit the profile")
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(520, 420)
        self._taken = taken
        self._existing = existing
        self.pairs: list[tuple[str, str]] = list(profile.variables if profile else ())
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.ok = self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.ok.get_style_context().add_class("suggested-action")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=18)
        names = Gtk.Box(spacing=12)
        names.pack_start(Gtk.Label(label=_("Name")), False, False, 0)
        self.name = Gtk.Entry(text=profile.name if profile else "", hexpand=True)
        self.name.connect("changed", lambda _entry: self.check())
        names.pack_start(self.name, True, True, 0)
        box.pack_start(names, False, False, 0)
        buttons = Gtk.Box(spacing=6)
        add = Gtk.Button(label=_("Add a variable"))
        add.connect("clicked", lambda _button: self.add())
        buttons.pack_start(add, False, False, 0)
        copy = Gtk.MenuButton(label=_("Add an existing variable"), sensitive=bool(existing))
        menu = Gtk.Menu()
        for name, value in existing:
            item = Gtk.MenuItem(label=name)
            item.connect("activate", lambda _item, n=name, v=value: self.add(n, v))
            menu.append(item)
        menu.show_all()
        copy.set_popup(menu)
        buttons.pack_start(copy, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        placeholder = dim(_("No variables in this profile yet."))
        placeholder.set_margin_top(12)
        placeholder.set_margin_bottom(12)
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.show()
        self.list.set_placeholder(placeholder)
        scrolled = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, vexpand=True)
        scrolled.add(self.list)
        box.pack_start(scrolled, True, True, 0)
        self.get_content_area().add(box)
        self.get_content_area().show_all()
        self.show_pairs()

    @property
    def profile(self) -> Profile:
        return Profile(self.name.get_text().strip(), tuple(self.pairs))

    def check(self) -> None:
        name = self.name.get_text().strip()
        problem = _("There is a profile of this name already.") if name in self._taken else None
        _warn(self.name, problem)
        self.ok.set_sensitive(bool(name) and not problem)

    def show_pairs(self) -> None:
        for row in self.list.get_children():
            self.list.remove(row)
        for index, (name, value) in enumerate(self.pairs):
            self.list.add(
                VariableRow(
                    name, value, None, lambda i=index: self.edit(i), lambda i=index: self.remove(i)
                )
            )
        self.list.show_all()
        self.check()

    def add(self, name: str = "", value: str = "") -> None:
        taken = frozenset(n for n, _v in self.pairs)
        dialog = VariableDialog(self, _("Add a variable"), name, value, taken)
        if dialog.run() == Gtk.ResponseType.OK:
            self.pairs.append(dialog.variable)
            self.show_pairs()
        dialog.destroy()

    def edit(self, index: int) -> None:
        name, value = self.pairs[index]
        taken = frozenset(n for n, _v in self.pairs if n != name)
        dialog = VariableDialog(self, _("Edit the variable"), name, value, taken)
        if dialog.run() == Gtk.ResponseType.OK:
            self.pairs[index] = dialog.variable
            self.show_pairs()
        dialog.destroy()

    def remove(self, index: int) -> None:
        del self.pairs[index]
        self.show_pairs()


class VariableRow(Gtk.ListBoxRow):
    """A variable: its name and value, and Edit and Delete in a menu. An origin icon in
    the list of what applies, where it cannot be changed.
    """

    def __init__(
        self,
        name: str,
        value: str,
        origin: str | None,
        edit: Callable[[], None] | None = None,
        delete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.value = value
        box = Gtk.Box(spacing=12, margin_start=12, margin_end=6, margin_top=4, margin_bottom=4)
        if origin:
            icon = Gtk.Image.new_from_icon_name(ORIGIN_ICONS[origin], Gtk.IconSize.MENU)
            icon.set_tooltip_text(origin_name(origin))
            box.pack_start(icon, False, False, 0)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        texts.pack_start(Gtk.Label(label=name, xalign=0), False, False, 0)
        shown = dim(value)
        shown.set_line_wrap(False)
        shown.set_ellipsize(Pango.EllipsizeMode.END)
        shown.set_tooltip_text(value or None)
        texts.pack_start(shown, False, False, 0)
        box.pack_start(texts, True, True, 0)
        if edit and delete:
            menu = Gtk.Menu()
            for label, action in ((_("Edit"), edit), (_("Delete"), delete)):
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda _item, act=action: act())
                menu.append(item)
            menu.show_all()
            button = Gtk.MenuButton(
                popup=menu, relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER
            )
            button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
            button.set_tooltip_text(_("More"))
            box.pack_end(button, False, False, 0)
        self.add(box)


def origin_name(origin: str) -> str:
    return {
        # TRANSLATORS: where a variable that applies comes from: /etc/environment.
        "system": _("System"),
        # TRANSLATORS: where a variable that applies comes from: the user's own.
        "user": _("User"),
        # TRANSLATORS: where a variable that applies comes from: the profile applied.
        "profile": _("Profile"),
        # TRANSLATORS: where the search path comes from when nothing sets it: the login.
        "login": _("Login"),
    }[origin]


class EnvironmentWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        client: Client | None,
        path: Path = ENVIRONMENT,
        runner: Runner = pkexec.run,
        base: Mapping[str, str] | None = None,
    ) -> None:
        """Without the daemon, or with the tool switched off, the user's part is greyed
        and says why; the system's still works. The tests hand in a file, a saver and
        a login of their own.
        """
        super().__init__(application=application, title=_("Environment Variables"))
        self.set_icon_name(APP_ID)
        self.set_default_size(980, 640)
        self._client = client
        self._path = path
        self._runner = runner
        self._base = dict(base) if base is not None else login_base()
        self.options: Options | None = None
        self.system = SystemFile("")
        self.expect = ""
        self.dirty = False
        self.saving = False
        self.backed_up = False

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        layout.pack_start(self._bar(), False, False, 0)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        toolbar = Gtk.Box(spacing=6)
        self.new_profile = Gtk.Button(label=_("New profile"), always_show_image=True)
        self.new_profile.set_image(
            Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        )
        self.new_profile.connect("clicked", lambda _button: self.add_profile())
        toolbar.pack_start(self.new_profile, False, False, 0)
        page.pack_start(toolbar, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.pack1(self._left(), True, False)
        panes.pack2(self._right(), True, False)
        panes.set_position(560)
        page.pack_start(panes, True, True, 0)
        page.pack_start(
            dim(
                _(
                    "Your variables and the profile's reach new terminals at once, and"
                    " everything else once you log out and back in. The system's apply at"
                    " the next login."
                )
            ),
            False,
            False,
            0,
        )
        layout.pack_start(page, True, True, 0)
        self.add(layout)
        layout.show_all()
        self.bar.hide()
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key)
        self.load_user()
        self.reload()
        self._monitor = Gio.File.new_for_path(str(path)).monitor_file(
            Gio.FileMonitorFlags.NONE, None
        )
        self._monitor.connect("changed", lambda *_args: self._changed_outside())

    # Building.

    def _bar(self) -> Gtk.Widget:
        self.bar = Gtk.InfoBar(message_type=Gtk.MessageType.WARNING)
        self.bar_text = Gtk.Label(xalign=0, wrap=True)
        self.bar.get_content_area().add(self.bar_text)
        self.reload_button = self.bar.add_button(_("Reload"), Gtk.ResponseType.ACCEPT)
        self.bar.connect("response", lambda _bar, _response: self.reload())
        return self.bar

    def _list(self, empty: str) -> Gtk.ListBox:
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        placeholder = dim(empty)
        placeholder.set_margin_top(12)
        placeholder.set_margin_bottom(12)
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.show()
        box.set_placeholder(placeholder)
        box.get_style_context().add_class("frame")
        return box

    def _left(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_end=12)
        box.pack_start(heading(_("Profiles")), False, False, 0)
        box.pack_start(
            dim(_("A set of variables to switch on and off together; one at a time.")),
            False,
            False,
            0,
        )
        self.profiles = self._list(_("No profiles yet."))
        box.pack_start(self.profiles, False, False, 0)
        box.pack_start(heading(_("Default variables")), False, False, 0)

        self.user_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.user_problem = dim("")
        self.user_problem.set_no_show_all(True)
        self.user_section.pack_start(self.user_problem, False, False, 0)
        user_head = Gtk.Box(spacing=6)
        self.add_user = Gtk.Button(label=_("Add a variable"))
        self.add_user.connect("clicked", lambda _button: self.add_user_variable())
        user_head.pack_end(self.add_user, False, False, 0)
        self.user_section.pack_start(user_head, False, False, 0)
        self.user = self._list(_("No variables of your own yet."))
        self.user_section.pack_start(self.user, False, False, 0)
        expander = Gtk.Expander(expanded=True)
        expander.set_label_widget(self._expander_label("avatar-default-symbolic", _("User")))
        expander.add(self.user_section)
        box.pack_start(expander, False, False, 0)

        system = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        system_head = Gtk.Box(spacing=6)
        system_head.pack_start(dim(_("In /etc/environment, for every user.")), True, True, 0)
        self.add_system = Gtk.Button(label=_("Add a variable"))
        self.add_system.connect("clicked", lambda _button: self.add_system_variable())
        system_head.pack_end(self.add_system, False, False, 0)
        system.pack_start(system_head, False, False, 0)
        self.system_list = self._list(_("No system variables."))
        system.pack_start(self.system_list, False, False, 0)
        save_row = Gtk.Box(spacing=6)
        self.status = dim("")
        save_row.pack_start(self.status, True, True, 0)
        self.save_button = Gtk.Button(label=_("Save"))
        self.save_button.set_tooltip_text(_("Save (Ctrl+S)"))
        self.save_button.get_style_context().add_class("suggested-action")
        self.save_button.connect("clicked", lambda _button: self.save())
        save_row.pack_end(self.save_button, False, False, 0)
        system.pack_start(save_row, False, False, 0)
        system_expander = Gtk.Expander(expanded=True)
        system_expander.set_label_widget(self._expander_label("computer-symbolic", _("System")))
        system_expander.add(system)
        box.pack_start(system_expander, False, False, 0)

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.add(box)
        return scrolled

    def _expander_label(self, icon: str, text: str) -> Gtk.Widget:
        box = Gtk.Box(spacing=6)
        box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
        box.pack_start(Gtk.Label(label=text), False, False, 0)
        box.show_all()
        return box

    def _right(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12)
        box.pack_start(heading(_("Applied variables")), False, False, 0)
        box.pack_start(
            dim(
                _(
                    "As they will be at the next login: the profile's over yours, yours over"
                    " the system's."
                )
            ),
            False,
            False,
            0,
        )
        self.applied_list = self._list(_("No variables are set."))
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scrolled.add(self.applied_list)
        box.pack_start(scrolled, True, True, 0)
        return box

    # The user's variables and the profiles, through the daemon.

    def load_user(self) -> None:
        problem = ""
        self.options = None
        if self._client is None:
            problem = _("TuxToys is not running.")
        else:
            try:
                self.options = Options.read(self._client.module_settings("envvars"))
            except NotRunning:
                problem = _("TuxToys is not running.")
            except (ModuleOff, Refused):
                problem = _("Switch Environment Variables on in TuxToys to set your own.")
        self.user_problem.set_text(problem)
        self.user_problem.set_visible(bool(problem))
        for widget in (self.user, self.add_user, self.profiles, self.new_profile):
            widget.set_sensitive(self.options is not None)
        self.show_all_lists()

    def _store(self, options: Options) -> bool:
        """Saves the user's side through the daemon; False, and says why, if it cannot."""
        if self._client is None or self.options is None:
            return False
        try:
            self._client.set_module_settings("envvars", options.settings())
        except (NotRunning, ModuleOff, Refused) as error:
            self._tell(_("Could not be saved: {reason}").format(reason=error), error=True)
            return False
        self.options = options
        self.show_all_lists()
        return True

    def add_user_variable(self) -> None:
        if self.options is None:
            return
        taken = frozenset(name for name, _value in self.options.variables)
        dialog = VariableDialog(self, _("Add a variable"), taken=taken)
        if dialog.run() == Gtk.ResponseType.OK:
            self._store(
                self.options.update({"variables": [*self.options.variables, dialog.variable]})
            )
        dialog.destroy()

    def edit_user_variable(self, index: int) -> None:
        if self.options is None:
            return
        pairs = list(self.options.variables)
        name, value = pairs[index]
        taken = frozenset(n for n, _v in pairs if n != name)
        dialog = VariableDialog(self, _("Edit the variable"), name, value, taken)
        if dialog.run() == Gtk.ResponseType.OK:
            pairs[index] = dialog.variable
            self._store(self.options.update({"variables": pairs}))
        dialog.destroy()

    def delete_user_variable(self, index: int) -> None:
        if self.options is None or not self._confirm(self.options.variables[index][0]):
            return
        pairs = [pair for i, pair in enumerate(self.options.variables) if i != index]
        self._store(self.options.update({"variables": pairs}))

    def _profile_settings(self, profiles: Sequence[Profile]) -> list:
        return [[p.name, [list(pair) for pair in p.variables]] for p in profiles]

    def _existing(self) -> list[tuple[str, str]]:
        """The user's and the system's variables, to copy into a profile."""
        user = list(self.options.variables) if self.options else []
        names = {name for name, _value in user}
        return user + [(n, v) for _i, n, v in self.system.variables() if n not in names]

    def add_profile(self) -> None:
        if self.options is None:
            return
        taken = frozenset(p.name for p in self.options.profiles)
        dialog = ProfileDialog(self, None, taken, self._existing())
        if dialog.run() == Gtk.ResponseType.OK:
            profiles = [*self.options.profiles, dialog.profile]
            self._store(self.options.update({"profiles": self._profile_settings(profiles)}))
        dialog.destroy()

    def edit_profile(self, index: int) -> None:
        if self.options is None:
            return
        profiles = list(self.options.profiles)
        old = profiles[index]
        taken = frozenset(p.name for p in profiles if p.name != old.name)
        dialog = ProfileDialog(self, old, taken, self._existing())
        if dialog.run() == Gtk.ResponseType.OK:
            profiles[index] = dialog.profile
            changes: dict[str, object] = {"profiles": self._profile_settings(profiles)}
            if self.options.active_profile == old.name:
                changes["active_profile"] = dialog.profile.name
            self._store(self.options.update(changes))
        dialog.destroy()

    def delete_profile(self, index: int) -> None:
        if self.options is None:
            return
        old = self.options.profiles[index]
        if not self._confirm(old.name):
            return
        profiles = [p for i, p in enumerate(self.options.profiles) if i != index]
        self._store(self.options.update({"profiles": self._profile_settings(profiles)}))

    def apply_profile(self, name: str, on: bool) -> None:
        """Applies a profile, or none; one at a time, as PowerToys has it."""
        if self.options is None:
            return
        active = (
            name
            if on
            else ("" if self.options.active_profile == name else self.options.active_profile)
        )
        if active != self.options.active_profile:
            self._store(self.options.update({"active_profile": active}))

    # The system's variables: /etc/environment.

    def reload(self) -> None:
        """Reads /etc/environment anew; what was not saved is dropped."""
        try:
            content = self._path.read_bytes()
        except OSError as error:
            self.system = SystemFile("")
            self.expect = ""
            self._tell(
                _("/etc/environment cannot be read: {reason}").format(
                    reason=error.strerror or error
                ),
                reload=True,
            )
            self._set_dirty(False)
            self.show_all_lists()
            return
        self.system = SystemFile(content.decode("utf-8", "replace"))
        self.expect = hashlib.sha256(content).hexdigest()
        self.bar.hide()
        self._set_dirty(False)
        self.show_all_lists()

    def _changed_outside(self) -> None:
        if self.saving:
            return
        try:
            now = hashlib.sha256(self._path.read_bytes()).hexdigest()
        except OSError:
            now = ""
        if now == self.expect:
            return
        if not self.dirty:
            self.reload()
            return
        self._tell(
            _(
                "/etc/environment was changed outside this window. Reload it to see the"
                " changes; yours would be lost."
            ),
            reload=True,
        )

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.save_button.set_sensitive(dirty and bool(self.expect) and not self.saving)
        self.status.set_text(_("There are changes not saved yet.") if dirty else "")

    def _system_names(self, but: str = "") -> frozenset[str]:
        return frozenset(n for _i, n, _v in self.system.variables() if n != but)

    def add_system_variable(self) -> None:
        dialog = VariableDialog(
            self, _("Add a system variable"), taken=self._system_names(), system=True
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self.system.add(*dialog.variable)
            self._set_dirty(True)
            self.show_all_lists()
        dialog.destroy()

    def edit_system_variable(self, index: int) -> None:
        line = self.system.lines[index]
        dialog = VariableDialog(
            self,
            _("Edit the system variable"),
            line.name,
            line.value,
            self._system_names(line.name),
            system=True,
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self.system.set(index, *dialog.variable)
            self._set_dirty(True)
            self.show_all_lists()
        dialog.destroy()

    def delete_system_variable(self, index: int) -> None:
        if not self._confirm(self.system.lines[index].name):
            return
        self.system.remove(index)
        self._set_dirty(True)
        self.show_all_lists()

    def save(self) -> None:
        if not self.dirty or self.saving or not self.expect:
            return
        self.saving = True
        self._set_dirty(True)
        self.status.set_text(_("Saving…"))
        argv = saving.command(self.expect, backup=not self.backed_up)
        self._runner(argv, self.system.text().encode("utf-8"), self._saved)

    def _saved(self, status: int, reason: str) -> None:
        self.saving = False
        result = pkexec.outcome(status)
        if result == "saved":
            self.backed_up = True
            self.reload()
            self.status.set_text(_("Saved. It applies at the next login."))
            return
        self._set_dirty(True)
        if result == "changed":
            self._tell(
                _(
                    "/etc/environment was changed outside this window, so it was not saved."
                    " Reload it to see the changes; yours would be lost."
                ),
                reload=True,
            )
        elif result == "not-allowed":
            self._tell(_("You are not allowed to change the system's variables."), error=True)
        elif result != "dismissed":
            self._tell(
                _("/etc/environment could not be saved: {reason}").format(reason=reason or status),
                error=True,
            )

    # Showing it all.

    def show_all_lists(self) -> None:
        self._fill(self.profiles, self._profile_rows())
        user = list(self.options.variables) if self.options else []
        self._fill(
            self.user,
            [
                VariableRow(
                    name,
                    value,
                    None,
                    lambda i=index: self.edit_user_variable(i),
                    lambda i=index: self.delete_user_variable(i),
                )
                for index, (name, value) in enumerate(user)
            ],
        )
        self._fill(
            self.system_list,
            [
                VariableRow(
                    name,
                    value,
                    None,
                    lambda i=index: self.edit_system_variable(i),
                    lambda i=index: self.delete_system_variable(i),
                )
                for index, name, value in self.system.variables()
            ],
        )
        self._fill(self.applied_list, [VariableRow(n, v, o) for n, v, o in self.applied()])

    def _profile_rows(self) -> list[Gtk.ListBoxRow]:
        rows = []
        if self.options is None:
            return rows
        for index, profile in enumerate(self.options.profiles):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(spacing=12, margin_start=12, margin_end=6, margin_top=4, margin_bottom=4)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            texts.pack_start(Gtk.Label(label=profile.name, xalign=0), False, False, 0)
            names = ", ".join(name for name, _value in profile.variables)
            summary = dim(names or _("No variables"))
            summary.set_line_wrap(False)
            summary.set_ellipsize(Pango.EllipsizeMode.END)
            texts.pack_start(summary, False, False, 0)
            box.pack_start(texts, True, True, 0)
            switch = Gtk.Switch(
                active=profile.name == self.options.active_profile, valign=Gtk.Align.CENTER
            )
            switch.set_tooltip_text(_("Applied"))
            switch.connect(
                "notify::active",
                lambda s, _spec, n=profile.name: GLib.idle_add(
                    lambda: self.apply_profile(n, s.get_active()) and False
                ),
            )
            menu = Gtk.Menu()
            for label, action in (
                (_("Edit"), lambda i=index: self.edit_profile(i)),
                (_("Delete"), lambda i=index: self.delete_profile(i)),
            ):
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda _item, act=action: act())
                menu.append(item)
            menu.show_all()
            button = Gtk.MenuButton(
                popup=menu, relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER
            )
            button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
            button.set_tooltip_text(_("More"))
            box.pack_end(button, False, False, 0)
            box.pack_end(switch, False, False, 0)
            row.add(box)
            row.profile = profile.name
            row.switch = switch
            rows.append(row)
        return rows

    def _fill(self, box: Gtk.ListBox, rows: Sequence[Gtk.ListBoxRow]) -> None:
        for row in box.get_children():
            box.remove(row)
        for row in rows:
            box.add(row)
        box.show_all()

    def applied(self) -> list[tuple[str, str, str]]:
        """(name, value, origin) for what applies at the next login: PATH first, then the
        profile's variables, the user's and the system's, each once, as PowerToys lists them.
        """
        system = [(n, v) for _i, n, v in self.system.variables()]
        user = list(self.options.variables) if self.options else []
        profile = list(self.options.applied) if self.options else []
        values = variables.applied(system, user, profile, self._base)
        origins = variables.origins(system, user, profile)
        order = ["PATH"] + [n for n, _v in (*profile, *user, *system)]
        shown = []
        for name in dict.fromkeys(order):
            if name in values:
                shown.append((name, values[name], origins.get(name, "login")))
        return shown

    # The rest.

    def _confirm(self, what: str) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Delete {name}?").format(name=what),
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Delete"), Gtk.ResponseType.OK).get_style_context().add_class(
            "destructive-action"
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _tell(self, text: str, reload: bool = False, error: bool = False) -> None:
        self.bar_text.set_text(text)
        self.bar.set_message_type(Gtk.MessageType.ERROR if error else Gtk.MessageType.WARNING)
        self.reload_button.set_visible(reload)
        self.bar.show()

    def _on_delete(self, _window: Gtk.Window, _event: Gdk.Event) -> bool:
        """Asks before closing with system variables not saved."""
        if not self.dirty or self.saving:
            return self.saving
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Save the changes to the system's variables?"),
        )
        dialog.format_secondary_text(_("Your changes will be lost if you don't save them."))
        dialog.add_button(_("Close without saving"), Gtk.ResponseType.CLOSE)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Save"), Gtk.ResponseType.OK).get_style_context().add_class(
            "suggested-action"
        )
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.CLOSE:
            return False
        if response == Gtk.ResponseType.OK:
            self.save()
        return True

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if (
            event.state & Gdk.ModifierType.CONTROL_MASK
            and Gdk.keyval_to_lower(event.keyval) == Gdk.KEY_s
        ):
            self.save()
            return True
        return False
