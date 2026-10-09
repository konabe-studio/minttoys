"""The settings window: a sidebar of tools on the left, under their headings, and the page
of the one selected on the right, the Overview first.

XApp.PreferencesWindow's own sidebar holds plain text only, so the sidebar is a list of our
own, with an icon per tool and a heading per group, as in Linux Mint's Software Sources.
The pages keep Mint's own settings widgets.
"""

import contextlib
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from minttoys import APP_ID, BUS_NAME, OBJECT_PATH  # noqa: E402
from minttoys.api import DAEMON_INTERFACE  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.settings import catalog, first_run  # noqa: E402
from minttoys.settings.awake_page import AwakePage, Client  # noqa: E402
from minttoys.settings.overview_page import OverviewPage  # noqa: E402

SIDEBAR_WIDTH = 200


class PageRow(Gtk.ListBoxRow):
    """A page in the sidebar: an icon and a name, and the heading it sits under."""

    def __init__(self, page: str, name: str, icon: str, heading: str) -> None:
        super().__init__()
        self.page = page
        self.heading = heading
        box = Gtk.Box(spacing=8, margin_start=10, margin_end=10, margin_top=6, margin_bottom=6)
        box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
        box.pack_start(Gtk.Label(label=name, xalign=0), True, True, 0)
        self.add(box)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application | None,
        bus: Gio.DBusConnection,
        client: Client,
        state_path: Path | None = None,
    ) -> None:
        super().__init__(application=application, title=_("MintToys"))
        self.set_icon_name(APP_ID)
        self.set_default_size(820, 580)
        self.connect("key-press-event", self._on_key)

        state_path = state_path or first_run.state_file()
        welcome = not first_run.welcomed(state_path)
        if welcome:
            # If it cannot be recorded, the greeting comes again next time: no harm done.
            with contextlib.suppress(OSError):
                first_run.mark_welcomed(state_path)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        self.sidebar.get_style_context().add_class("sidebar")
        self.sidebar.set_header_func(self._header)
        self.sidebar.connect("row-selected", self._on_row_selected)

        self.overview = OverviewPage(client, self._error, welcome=welcome)
        # TRANSLATORS: the first page of the settings window, listing every tool.
        self._add_page("overview", _("Overview"), "go-home-symbolic", "", self.overview)
        self.awake = AwakePage(client, self._error)
        pages = {"awake": self.awake}
        for heading, tools in catalog.grouped():
            for tool in tools:
                self._add_page(tool.id, tool.name, tool.icon, heading, pages[tool.id])
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))

        sidebar_scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        sidebar_scroller.set_size_request(SIDEBAR_WIDTH, -1)
        sidebar_scroller.add(self.sidebar)
        layout = Gtk.Box()
        layout.pack_start(sidebar_scroller, False, False, 0)
        layout.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        layout.pack_start(self.stack, True, True, 0)
        self.add(layout)

        bus.signal_subscribe(
            BUS_NAME,
            DAEMON_INTERFACE,
            "ModuleSettingsChanged",
            OBJECT_PATH,
            "awake",
            Gio.DBusSignalFlags.NONE,
            lambda *arguments: self.awake.show_settings(arguments[5].unpack()[1]),
        )
        # A module switched on or off elsewhere, from the command line for one.
        bus.signal_subscribe(
            BUS_NAME,
            DAEMON_INTERFACE,
            "ModulesChanged",
            OBJECT_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            lambda *_: self.refresh(),
        )
        # Follows the daemon leaving and coming back, so no page shows settings that are
        # not there any more.
        self._watch = Gio.bus_watch_name_on_connection(
            bus,
            BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            lambda *_: self.refresh(),
            lambda *_: self.refresh(),
        )

    def refresh(self) -> None:
        self.overview.refresh()
        self.awake.refresh()

    def show_page(self, page: str) -> None:
        for row in self.sidebar.get_children():
            if row.page == page:
                self.sidebar.select_row(row)

    def _add_page(self, page: str, name: str, icon: str, heading: str, widget: Gtk.Widget) -> None:
        # Scrolls rather than grows when a translation makes the page longer.
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add(widget)
        # Shown before they are added: a GtkListBox gives no header to a hidden row, and a
        # GtkStack does not switch to a hidden page.
        scroller.show_all()
        self.stack.add_named(scroller, page)
        row = PageRow(page, name, icon, heading)
        row.show_all()
        self.sidebar.add(row)

    def _header(self, row: PageRow, before: PageRow | None) -> None:
        if row.heading and (before is None or before.heading != row.heading):
            label = Gtk.Label(label=row.heading, xalign=0, margin_start=10, margin_top=12)
            label.get_style_context().add_class("dim-label")
            row.set_header(label)
        else:
            row.set_header(None)

    def _on_row_selected(self, _sidebar: Gtk.ListBox, row: PageRow | None) -> None:
        if row is not None:
            self.stack.set_visible_child_name(row.page)

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=message,
        )
        dialog.run()
        dialog.destroy()
