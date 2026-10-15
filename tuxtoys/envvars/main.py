"""Environment Variables' window as a program of its own. One window at a time: opening it
again brings the open one forward. The user's variables and the profiles go through the
daemon, which D-Bus starts if need be; without it, only the system's can be changed.
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

        from tuxtoys.envvars.window import EnvironmentWindow
    except (ImportError, ValueError) as error:
        print(
            _("Environment Variables needs PyGObject and GTK 3: {error}").format(error=error),
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
    GLib.set_application_name(_("Environment Variables"))
    application = Gtk.Application(application_id=f"{APP_ID}.EnvironmentVariables")

    def activate(app: Gtk.Application) -> None:
        if app.get_windows():
            app.get_windows()[0].present()
            return
        EnvironmentWindow(app, client).present()

    application.connect("activate", activate)
    return application.run(sys.argv[:1])
