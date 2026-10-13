"""Hosts File Editor's window as a program of its own. One window at a time: opening it
again brings the open one forward. It reads its settings through the daemon, which D-Bus
starts if need be; without it, it starts from the defaults.
"""

import sys

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    del argv  # it takes no arguments
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk

        from tuxtoys.hostseditor.window import HostsWindow
    except (ImportError, ValueError) as error:
        print(
            _("Hosts File Editor needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys.api import NotRunning
    from tuxtoys.client import Client

    try:
        client = Client.connect()
    except NotRunning:
        client = None

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Hosts File Editor"))
    application = Gtk.Application(application_id=f"{APP_ID}.HostsEditor")

    def activate(app: Gtk.Application) -> None:
        if app.get_windows():
            app.get_windows()[0].present()
            return
        window = HostsWindow(app, client)
        window.present()
        if not window.warn():
            window.destroy()

    application.connect("activate", activate)
    return application.run(sys.argv[:1])
