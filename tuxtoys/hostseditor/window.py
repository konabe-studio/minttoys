"""Hosts File Editor's window: the entries of /etc/hosts with their address, host names,
comment and an Active switch, as PowerToys lists them; filters; a ping for each; and Save,
which asks for an administrator's password through pkexec.

The window runs as the user, who may read the file but not write it. Changes stay in the
window until Save. A change made to the file elsewhere is picked up at once when there is
nothing unsaved, and reported otherwise; the root helper never writes over it.
"""

import hashlib
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from tuxtoys import APP_ID  # noqa: E402
from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.pkexec import run as run_saver  # noqa: E402
from tuxtoys.modules.hosts import saving  # noqa: E402
from tuxtoys.modules.hosts.hostsfile import (  # noqa: E402
    Entry,
    HostsFile,
    duplicates,
    is_address,
    is_host,
)
from tuxtoys.modules.hosts.options import Options  # noqa: E402
from tuxtoys.modules.hosts.save import HOSTS  # noqa: E402

type Done = Callable[[int, str], None]
type Runner = Callable[[list[str], bytes, Done], None]
type Pinger = Callable[[str, Callable[[bool], None]], None]

WARNING_ICON = "dialog-warning-symbolic"
# The warning sign in the theme's warning colour, amber in Mint-Y, as Mint's own settings
# show one: in a field, and beside an entry in the list.
CSS = b"""
entry image.right { color: @warning_color; }
image.tuxtoys-warning { color: @warning_color; }
"""


def bold(text: str) -> str:
    """Markup for a heading. The message is passed in, never written inside an f-string,
    where xgettext would not find it.
    """
    return f"<b>{GLib.markup_escape_text(text)}</b>"


class Client(Protocol):
    def module_settings(self, module_id: str) -> dict: ...


def run_ping(address: str, done: Callable[[bool], None]) -> None:
    """One ping, waiting two seconds at most, in the background."""
    try:
        process = Gio.Subprocess.new(
            ["ping", "-c", "1", "-W", "2", "-n", address],
            Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE,
        )
    except GLib.Error:
        done(False)
        return

    def finished(process: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        with suppress(GLib.Error):
            process.wait_finish(result)
        done(process.get_if_exited() and process.get_exit_status() == 0)

    process.wait_async(None, finished)


class EntryDialog(Gtk.Dialog):
    """A new entry or a change to one: address, host names, comment, Active."""

    def __init__(self, parent: Gtk.Window, entry: Entry | None) -> None:
        title = _("Add new entry") if entry is None else _("Update the entry")
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(440, -1)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.ok = self.add_button(_("Add") if entry is None else _("Update"), Gtk.ResponseType.OK)
        self.ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        entry = entry or Entry("", ())
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=18)
        self.address = self._field(grid, 0, _("Address"), entry.address)
        self.hosts = self._field(grid, 1, _("Hosts"), " ".join(entry.hosts))
        self.hosts.set_placeholder_text(_("server server.local"))
        self.hosts.set_tooltip_text(_("Separate several host names with spaces."))
        self.comment = self._field(grid, 2, _("Comment"), entry.comment)
        grid.attach(Gtk.Label(label=_("Active"), xalign=0), 0, 3, 1, 1)
        self.active = Gtk.Switch(active=entry.active, halign=Gtk.Align.START)
        grid.attach(self.active, 1, 3, 1, 1)
        self.get_content_area().add(grid)
        self.get_content_area().show_all()
        self.check()

    def _field(self, grid: Gtk.Grid, row: int, label: str, text: str) -> Gtk.Entry:
        grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        field = Gtk.Entry(text=text, hexpand=True, activates_default=True)
        field.connect("changed", lambda _field: self.check())
        grid.attach(field, 1, row, 1, 1)
        return field

    @property
    def entry(self) -> Entry:
        return Entry(
            self.address.get_text().strip(),
            tuple(self.hosts.get_text().split()),
            self.comment.get_text().strip().replace("\n", " "),
            self.active.get_active(),
        )

    def check(self) -> None:
        """Marks a field that does not hold what it should, and allows Add only when none
        does. An empty field is not marked until something is typed in it.
        """
        entry = self.entry
        address = not entry.address or is_address(entry.address)
        hosts = not entry.hosts or all(is_host(host) for host in entry.hosts)
        _warn(self.address, None if address else _("Has to be an IPv4 or IPv6 address."))
        _warn(
            self.hosts,
            None if hosts else _("Has to be one or more host names, separated by spaces."),
        )
        self.ok.set_sensitive(entry.valid)


def _warn(field: Gtk.Entry, problem: str | None) -> None:
    field.set_icon_from_icon_name(
        Gtk.EntryIconPosition.SECONDARY, WARNING_ICON if problem else None
    )
    field.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, problem)


class EntryRow(Gtk.ListBoxRow):
    """An entry in the list."""

    def __init__(
        self,
        window: "HostsWindow",
        index: int,
        entry: Entry,
        problem: str,
        doubled: bool,
        ping: bool | None,
    ) -> None:
        super().__init__()
        self.index = index
        self.entry = entry
        self.doubled = doubled
        box = Gtk.Box(spacing=12, margin_start=12, margin_end=6, margin_top=4, margin_bottom=4)
        sign = Gtk.Image.new_from_icon_name(WARNING_ICON, Gtk.IconSize.MENU)
        sign.get_style_context().add_class("tuxtoys-warning")
        sign.set_tooltip_text(problem or None)
        sign.set_opacity(1 if problem else 0)
        box.pack_start(sign, False, False, 0)
        self.address = Gtk.Label(
            label=entry.address, xalign=0, width_chars=18, ellipsize=Pango.EllipsizeMode.END
        )
        box.pack_start(self.address, False, False, 0)
        self.hosts = Gtk.Label(
            label=" ".join(entry.hosts), xalign=0, ellipsize=Pango.EllipsizeMode.END
        )
        box.pack_start(self.hosts, True, True, 0)
        self.comment = Gtk.Label(
            label=entry.comment, xalign=0, width_chars=16, ellipsize=Pango.EllipsizeMode.END
        )
        self.comment.get_style_context().add_class("dim-label")
        box.pack_start(self.comment, True, True, 0)
        answer = {
            True: ("network-transmit-receive-symbolic", _("It answered the ping.")),
            False: ("network-offline-symbolic", _("No answer to the ping.")),
        }.get(ping)
        if answer:
            reply = Gtk.Image.new_from_icon_name(answer[0], Gtk.IconSize.MENU)
            reply.set_tooltip_text(answer[1])
            box.pack_start(reply, False, False, 0)
        self.switch = Gtk.Switch(active=entry.active, valign=Gtk.Align.CENTER)
        self.switch.set_tooltip_text(_("Active"))
        self.switch.connect(
            "notify::active", lambda switch, _spec: window.set_active(self, switch.get_active())
        )
        box.pack_start(self.switch, False, False, 0)
        box.pack_start(self._menu_button(window), False, False, 0)
        self.add(box)

    def _menu_button(self, window: "HostsWindow") -> Gtk.MenuButton:
        menu = Gtk.Menu()
        for label, action in (
            (_("Edit"), window.edit),
            (_("Duplicate"), window.duplicate),
            (_("Ping"), window.ping),
            (_("Move up"), lambda row: window.move(row, up=True)),
            (_("Move down"), lambda row: window.move(row, up=False)),
            (_("Delete"), window.delete),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item, action=action: action(self))
            menu.append(item)
        menu.show_all()
        button = Gtk.MenuButton(popup=menu, relief=Gtk.ReliefStyle.NONE)
        button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
        button.set_tooltip_text(_("More"))
        return button


class HostsWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        client: Client | None,
        path: Path = HOSTS,
        runner: Runner = run_saver,
        pinger: Pinger = run_ping,
    ) -> None:
        """Without a client the window starts from the default settings. The tests hand
        in a file, a saver and a ping of their own.
        """
        super().__init__(application=application, title=_("Hosts File Editor"))
        self.set_icon_name(APP_ID)
        self.set_default_size(820, 560)
        self._path = path
        self._runner = runner
        self._pinger = pinger
        self.options = self._load(client)
        self.hosts = HostsFile("")
        self.expect = ""
        self.dirty = False
        self.saving = False
        self.backed_up = False
        self.pings: dict[str, bool | None] = {}
        self._close_after_save = False

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        layout.pack_start(self._bar(), False, False, 0)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        page.pack_start(self._toolbar(), False, False, 0)
        page.pack_start(self._filters(), False, False, 0)
        page.pack_start(self._list(), True, True, 0)
        page.pack_start(self._bottom(), False, False, 0)
        layout.pack_start(page, True, True, 0)
        self.add(layout)
        layout.show_all()
        self.bar.hide()
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key)
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

    def _toolbar(self) -> Gtk.Widget:
        box = Gtk.Box(spacing=6)
        new = Gtk.Button(label=_("New entry"), always_show_image=True)
        new.set_image(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        new.set_tooltip_text(_("New entry (Ctrl+N)"))
        new.connect("clicked", lambda _button: self.add_entry())
        box.pack_start(new, False, False, 0)
        opener = self._icon_button("document-open-symbolic", _("Open the hosts file"))
        opener.connect("clicked", lambda _button: self.open_file())
        box.pack_end(opener, False, False, 0)
        self.filter_button = Gtk.ToggleButton()
        self.filter_button.set_image(
            Gtk.Image.new_from_icon_name("edit-find-symbolic", Gtk.IconSize.BUTTON)
        )
        self.filter_button.set_tooltip_text(_("Filters (Ctrl+F)"))
        self.filter_button.connect("toggled", self._on_filter_toggled)
        box.pack_end(self.filter_button, False, False, 0)
        return box

    def _icon_button(self, icon: str, tooltip: str) -> Gtk.Button:
        button = Gtk.Button()
        button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        button.set_tooltip_text(tooltip)
        return button

    def _filters(self) -> Gtk.Widget:
        self.filters = Gtk.Revealer()
        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        self.by_address = Gtk.SearchEntry(placeholder_text=_("Address"), hexpand=True)
        self.by_hosts = Gtk.SearchEntry(placeholder_text=_("Hosts"), hexpand=True)
        self.by_comment = Gtk.SearchEntry(placeholder_text=_("Comment"), hexpand=True)
        for column, field in enumerate((self.by_address, self.by_hosts, self.by_comment)):
            field.connect("search-changed", lambda _field: self.list.invalidate_filter())
            grid.attach(field, column, 0, 1, 1)
        self.only_duplicates = Gtk.CheckButton(label=_("Show only duplicates"))
        self.only_duplicates.connect("toggled", lambda _check: self.list.invalidate_filter())
        grid.attach(self.only_duplicates, 0, 1, 2, 1)
        clear = Gtk.Button(label=_("Clear filters"), halign=Gtk.Align.END)
        clear.connect("clicked", lambda _button: self.clear_filters())
        grid.attach(clear, 2, 1, 1, 1)
        self.filters.add(grid)
        return self.filters

    def _list(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        heads = Gtk.Box(spacing=12, margin_start=12 + 16 + 12, margin_end=6)
        for text, width, expand in (
            (_("Address"), 18, False),
            (_("Hosts"), -1, True),
            (_("Comment"), 16, True),
        ):
            label = Gtk.Label(xalign=0, width_chars=width)
            label.set_markup(bold(text))
            heads.pack_start(label, expand, expand, 0)
        active = Gtk.Label(margin_end=40)
        active.set_markup(bold(_("Active")))
        heads.pack_start(active, False, False, 0)
        box.pack_start(heads, False, False, 0)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.set_filter_func(self._shown)
        self.list.connect("row-activated", lambda _list, row: self.edit(row))
        self.empty = Gtk.Label(label=_("No entries in the hosts file"), margin=24)
        self.empty.get_style_context().add_class("dim-label")
        self.empty.show()
        self.list.set_placeholder(self.empty)
        scrolled = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scrolled.add(self.list)
        box.pack_start(scrolled, True, True, 0)
        return box

    def _bottom(self) -> Gtk.Widget:
        box = Gtk.Box(spacing=6)
        self.status = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.status.get_style_context().add_class("dim-label")
        box.pack_start(self.status, True, True, 0)
        self.save_button = Gtk.Button(label=_("Save"))
        self.save_button.set_tooltip_text(_("Save (Ctrl+S)"))
        self.save_button.get_style_context().add_class("suggested-action")
        self.save_button.connect("clicked", lambda _button: self.save())
        box.pack_end(self.save_button, False, False, 0)
        return box

    # The file.

    def reload(self) -> None:
        """Reads the file anew; what was not saved is dropped."""
        try:
            content = self._path.read_bytes()
        except OSError as error:
            self.hosts = HostsFile("")
            self.expect = ""
            self._tell(
                _("The hosts file cannot be read: {reason}").format(reason=error.strerror or error),
                reload=True,
            )
            self._set_dirty(False)
            self.show_entries()
            return
        self.hosts = HostsFile(content.decode("utf-8", "replace"))
        self.expect = hashlib.sha256(content).hexdigest()
        self.bar.hide()
        self._set_dirty(False)
        self.show_entries()

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
                "The hosts file was changed outside this window. Reload it to see the"
                " changes; yours would be lost."
            ),
            reload=True,
        )

    def _tell(self, text: str, reload: bool = False, error: bool = False) -> None:
        self.bar_text.set_text(text)
        self.bar.set_message_type(Gtk.MessageType.ERROR if error else Gtk.MessageType.WARNING)
        self.reload_button.set_visible(reload)
        self.bar.show()

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.save_button.set_sensitive(dirty and bool(self.expect) and not self.saving)
        self.status.set_text(_("There are changes not saved yet.") if dirty else "")

    # The list.

    def show_entries(self) -> None:
        for row in self.list.get_children():
            self.list.remove(row)
        doubled = duplicates(self.hosts, self.options.loopback_duplicates)
        for index, entry in self.hosts.entries():
            problem = self._problem(index, entry, doubled)
            ping = self.pings.get(entry.address)
            self.list.add(EntryRow(self, index, entry, problem, index in doubled, ping))
        self.list.show_all()
        self.list.invalidate_filter()

    def _problem(self, index: int, entry: Entry, doubled: set[int]) -> str:
        if not entry.valid_address:
            return _("Has to be an IPv4 or IPv6 address.")
        if not entry.valid_hosts:
            return _("Has to be one or more host names, separated by spaces.")
        if index in doubled:
            return _("A host name here is in another active entry too.")
        return ""

    def _shown(self, row: EntryRow) -> bool:
        entry = row.entry
        wanted = (
            (self.by_address.get_text(), entry.address),
            (self.by_hosts.get_text(), " ".join(entry.hosts)),
            (self.by_comment.get_text(), entry.comment),
        )
        if any(text and text.casefold() not in value.casefold() for text, value in wanted):
            return False
        return not self.only_duplicates.get_active() or row.doubled

    def _on_filter_toggled(self, button: Gtk.ToggleButton) -> None:
        self.filters.set_reveal_child(button.get_active())
        if button.get_active():
            self.by_address.grab_focus()
        else:
            self.clear_filters()

    def clear_filters(self) -> None:
        for field in (self.by_address, self.by_hosts, self.by_comment):
            field.set_text("")
        self.only_duplicates.set_active(False)
        self.list.invalidate_filter()

    def rows(self) -> list[EntryRow]:
        return list(self.list.get_children())

    # Changes.

    def _changed(self) -> None:
        self._set_dirty(True)
        self.show_entries()

    def add_entry(self) -> None:
        dialog = EntryDialog(self, None)
        if dialog.run() == Gtk.ResponseType.OK:
            self.hosts.add(dialog.entry)
            self._changed()
        dialog.destroy()

    def edit(self, row: EntryRow) -> None:
        dialog = EntryDialog(self, row.entry)
        if dialog.run() == Gtk.ResponseType.OK:
            self.hosts.set(row.index, dialog.entry)
            self._changed()
        dialog.destroy()

    def duplicate(self, row: EntryRow) -> None:
        self.hosts.add(row.entry)
        self._changed()

    def set_active(self, row: EntryRow, active: bool) -> None:
        if row.entry.active == active:
            return
        self.hosts.set(row.index, replace(row.entry, active=active))
        self._set_dirty(True)
        # The list is drawn anew once the switch has finished switching.
        GLib.idle_add(lambda: self.show_entries() and False)

    def move(self, row: EntryRow, up: bool) -> None:
        if self.hosts.move(row.index, up) != row.index:
            self._changed()

    def delete(self, row: EntryRow) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Delete this entry?"),
        )
        dialog.format_secondary_text(row.entry.line())
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Delete"), Gtk.ResponseType.OK).get_style_context().add_class(
            "destructive-action"
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self.hosts.remove(row.index)
            self._changed()
        dialog.destroy()

    def ping(self, row: EntryRow) -> None:
        address = row.entry.address
        self.pings[address] = None

        def answered(ok: bool) -> None:
            self.pings[address] = ok
            self.show_entries()

        self._pinger(address, answered)

    def open_file(self) -> None:
        with suppress(GLib.Error):
            Gio.AppInfo.launch_default_for_uri(self._path.as_uri(), None)

    # Saving.

    def save(self) -> None:
        if not self.dirty or self.saving or not self.expect:
            return
        self.saving = True
        self._set_dirty(True)
        self.status.set_text(_("Saving…"))
        argv = saving.command(self.expect, self.options, backup=not self.backed_up)
        self._runner(argv, self.hosts.text().encode("utf-8"), self._saved)

    def _saved(self, status: int, reason: str) -> None:
        self.saving = False
        result = saving.outcome(status)
        if result == "saved":
            self.backed_up = self.backed_up or self.options.backup
            self.reload()
            self.status.set_text(_("Saved."))
            if self._close_after_save:
                self.destroy()
            return
        self._close_after_save = False
        self._set_dirty(True)
        if result == "changed":
            self._tell(
                _(
                    "The hosts file was changed outside this window, so it was not saved."
                    " Reload it to see the changes; yours would be lost."
                ),
                reload=True,
            )
        elif result == "not-allowed":
            self._tell(_("You are not allowed to save the hosts file."), error=True)
        elif result != "dismissed":
            self._tell(
                _("The hosts file could not be saved: {reason}").format(reason=reason or status),
                error=True,
            )

    def _on_delete(self, _window: Gtk.Window, _event: Gdk.Event) -> bool:
        """Asks before closing with changes not saved."""
        if not self.dirty or self.saving:
            return self.saving
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Save the changes to the hosts file?"),
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
            self._close_after_save = True
            self.save()
        return True

    def warn(self) -> bool:
        """PowerToys' warning at the start, while it is switched on; False to quit."""
        if not self.options.show_warning:
            return True
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Warning"),
        )
        dialog.format_secondary_text(
            _(
                "Changing the hosts file changes how this computer finds other computers by"
                " name, for every program and every user."
            )
        )
        dialog.add_button(_("Quit"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Accept"), Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if not event.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        key = Gdk.keyval_to_lower(event.keyval)
        if key == Gdk.KEY_s:
            self.save()
        elif key == Gdk.KEY_n:
            self.add_entry()
        elif key == Gdk.KEY_f:
            self.filter_button.set_active(not self.filter_button.get_active())
        else:
            return False
        return True

    # Settings, through the daemon when it is there.

    def _load(self, client: Client | None) -> Options:
        if client is None:
            return Options()
        try:
            return Options.read(client.module_settings("hosts"))
        except (NotRunning, ModuleOff, Refused):
            return Options()
