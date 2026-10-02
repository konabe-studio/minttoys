"""Starts the panel icon. One per session: like the daemon, it holds a bus name of its own,
and a second one finds it taken and exits.
"""

import signal
import sys

from minttoys import APP_ID
from minttoys.core.i18n import _


def main() -> int:
    try:
        import gi

        # Before the first import of Gtk, or PyGObject warns and picks a version itself.
        gi.require_version("Gtk", "3.0")
        gi.require_version("XApp", "1.0")
        from gi.repository import Gio, GLib, Gtk

        from minttoys.client import Client
        from minttoys.tray.app import Tray
    except (ImportError, ValueError) as error:
        # ValueError: gi.require_version found no GTK 3 or XApp typelib.
        message = _("The panel icon needs PyGObject, GTK 3 and XApp: {error}")
        print(message.format(error=error), file=sys.stderr)
        return 1
    if not Gtk.init_check()[0]:
        print(_("The panel icon needs a desktop session."), file=sys.stderr)
        return 1

    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    status = 0

    def on_name_acquired(connection: Gio.DBusConnection, name: str) -> None:
        Tray(connection, Client(connection))

    def on_name_lost(connection: Gio.DBusConnection | None, name: str) -> None:
        nonlocal status
        print(_("The MintToys panel icon is already running."), file=sys.stderr)
        status = 1
        Gtk.main_quit()

    for signal_number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal_number, Gtk.main_quit)
    Gio.bus_own_name_on_connection(
        bus, f"{APP_ID}.Tray", Gio.BusNameOwnerFlags.DO_NOT_QUEUE, on_name_acquired, on_name_lost
    )
    Gtk.main()
    return status


raise SystemExit(main())
