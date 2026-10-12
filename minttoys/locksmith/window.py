"""File Locksmith's window: the processes that hold the chosen files and folders, and a way
to end one.
"""

import os
import signal
from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from minttoys import APP_ID  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.modules.locksmith import text  # noqa: E402
from minttoys.modules.locksmith.scan import Scan, scan  # noqa: E402

# How long a process has to stop after being asked, before the window offers to force it.
GRACE_MS = 3000
PID, NAME, HELD = range(3)

type Scanner = Callable[[Sequence[str]], Scan]
type Killer = Callable[[int, int], None]


def alive(pid: int) -> bool:
    return os.path.exists(f"/proc/{pid}")


class LocksmithWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        targets: Sequence[str],
        find: Scanner | None = None,
        kill: Killer = os.kill,
        is_alive: Callable[[int], bool] = alive,
    ) -> None:
        """The tests hand in stand-ins for /proc and for signals."""
        super().__init__(application=application, title=_("File Locksmith"))
        self.set_icon_name(APP_ID)
        self.set_default_size(560, 380)
        self.connect("key-press-event", self._on_key)
        self._targets = list(targets)
        self._find = find or (lambda paths: scan(paths, skip=os.getpid()))
        self._kill = kill
        self._is_alive = is_alive

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        self.heading = Gtk.Label(xalign=0, wrap=True)
        self.heading.set_markup(f"<b>{GLib.markup_escape_text(text.heading(self._targets))}</b>")
        box.pack_start(self.heading, False, False, 0)
        if len(self._targets) == 1:
            where = Gtk.Label(label=self._targets[0], xalign=0, wrap=True, selectable=True)
            where.get_style_context().add_class("dim-label")
            box.pack_start(where, False, False, 0)

        self.store = Gtk.ListStore(int, str, str)
        self.list = Gtk.TreeView(model=self.store)
        for title, column in ((_("Process"), NAME), (_("PID"), PID), (_("Holds"), HELD)):
            view = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=column)
            view.set_resizable(True)
            view.set_expand(column == HELD)
            self.list.append_column(view)
        self.list.get_selection().connect("changed", self._on_selection)
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scroller.add(self.list)
        self.nothing = Gtk.Label(label=text.nothing())
        self.nothing.get_style_context().add_class("dim-label")
        self.stack = Gtk.Stack()
        self.stack.add_named(scroller, "list")
        self.stack.add_named(self.nothing, "nothing")
        box.pack_start(self.stack, True, True, 0)

        self.hidden = Gtk.Label(label=text.hidden(), xalign=0, wrap=True)
        self.hidden.get_style_context().add_class("dim-label")
        self.hidden.set_no_show_all(True)
        box.pack_start(self.hidden, False, False, 0)

        buttons = Gtk.Box(spacing=6)
        refresh = Gtk.Button(label=_("Refresh"))
        refresh.connect("clicked", lambda _button: self.refresh())
        buttons.pack_start(refresh, False, False, 0)
        self.end = Gtk.Button(label=_("End process"))
        self.end.get_style_context().add_class("destructive-action")
        self.end.connect("clicked", self._on_end)
        buttons.pack_end(self.end, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        self.add(box)
        box.show_all()
        self.refresh()

    def refresh(self) -> None:
        found = self._find(self._targets)
        self.store.clear()
        for holder in found.holders:
            self.store.append([holder.pid, holder.name, text.held(holder.paths, self._targets)])
        self.stack.set_visible_child_name("list" if found.holders else "nothing")
        self.hidden.set_visible(found.some_hidden)
        self._on_selection(self.list.get_selection())

    def _selected(self) -> tuple[int, str] | None:
        model, row = self.list.get_selection().get_selected()
        if row is None:
            return None
        return model[row][PID], model[row][NAME]

    def _on_selection(self, _selection: Gtk.TreeSelection) -> None:
        self.end.set_sensitive(self._selected() is not None)

    def _on_end(self, _button: Gtk.Button) -> None:
        selected = self._selected()
        if selected is None:
            return
        pid, name = selected
        if not self._signal(pid, name, signal.SIGTERM):
            return
        GLib.timeout_add(GRACE_MS, self._after_grace, pid, name)

    def _after_grace(self, pid: int, name: str) -> bool:
        if self._is_alive(pid) and self._ask_force(name):
            self._signal(pid, name, signal.SIGKILL)
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _signal(self, pid: int, name: str, number: int) -> bool:
        try:
            self._kill(pid, number)
        except ProcessLookupError:
            self.refresh()  # it ended meanwhile
            return False
        except PermissionError:
            self._tell(_("You may not end {name}.").format(name=name))
            return False
        return True

    def _ask_force(self, name: str) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("{name} did not stop.").format(name=name),
        )
        dialog.format_secondary_text(_("Force it to stop? Unsaved work in it will be lost."))
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        force = dialog.add_button(_("Force stop"), Gtk.ResponseType.ACCEPT)
        force.get_style_context().add_class("destructive-action")
        answer = dialog.run()
        dialog.destroy()
        return answer == Gtk.ResponseType.ACCEPT

    def _tell(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
