"""The settings app's process. A Gtk.Application, so a second start brings the open window
to the front instead of opening another.
"""

import sys

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("XApp", "1.0")
        from gi.repository import Gio, GLib, Gtk

        from tuxtoys.client import Client
        from tuxtoys.settings.window import SettingsWindow
    except (ImportError, ValueError) as error:
        # ImportError: no PyGObject or python3-xapp; ValueError: no GTK 3 or XApp typelib.
        message = _("The settings need PyGObject, GTK 3 and python3-xapp: {error}")
        print(message.format(error=error), file=sys.stderr)
        return 1

    # The window's class is the app id, which is also the desktop file's name, so the
    # panel groups the window under the TuxToys menu entry and its icon.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("TuxToys"))
    application = Gtk.Application(
        application_id=f"{APP_ID}.Settings",
        flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
    )

    def present(page: str) -> None:
        windows = application.get_windows()
        if windows:
            window = windows[0]
        else:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION)
            window = SettingsWindow(application, bus, Client(bus))
            window.show_all()
        if page:
            window.show_page(page)
        window.present()

    def on_command_line(
        _application: Gtk.Application, command_line: Gio.ApplicationCommandLine
    ) -> int:
        # --page opens a tool's page, as Text Extractor's settings button does; in the
        # window already open when there is one.
        arguments = command_line.get_arguments()[1:]
        page = ""
        if len(arguments) == 2 and arguments[0] == "--page":
            page = arguments[1]
        present(page)
        return 0

    application.connect("command-line", on_command_line)
    return application.run(sys.argv)
