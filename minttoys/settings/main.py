"""The settings app's process. A Gtk.Application, so a second start brings the open window
to the front instead of opening another.
"""

import sys

from minttoys import APP_ID
from minttoys.core.i18n import _


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("XApp", "1.0")
        from gi.repository import Gio, GLib, Gtk

        from minttoys.client import Client
        from minttoys.settings.window import SettingsWindow
    except (ImportError, ValueError) as error:
        # ImportError: no PyGObject or python3-xapp; ValueError: no GTK 3 or XApp typelib.
        message = _("The settings need PyGObject, GTK 3 and python3-xapp: {error}")
        print(message.format(error=error), file=sys.stderr)
        return 1

    # The window's class is the app id, which is also the desktop file's name, so the
    # panel groups the window under the MintToys menu entry and its icon.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("MintToys"))
    application = Gtk.Application(application_id=f"{APP_ID}.Settings")

    def on_activate(application: Gtk.Application) -> None:
        for window in application.get_windows():
            window.present()
            return
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        window = SettingsWindow(application, bus, Client(bus))
        window.show_all()

    application.connect("activate", on_activate)
    return application.run(sys.argv[:1])
