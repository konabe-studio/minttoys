"""Image Resizer's window as a program of its own, run by its Nemo action with the chosen
pictures. Each run opens a window of its own. It reads and remembers its settings through
the daemon, which D-Bus starts if need be; without it, it starts from the defaults.
"""

import sys

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    pictures = sys.argv[1:] if argv is None else argv
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, GLib, Gtk

        from tuxtoys.imageresizer.window import ResizeWindow
    except (ImportError, ValueError) as error:
        print(
            _("Image Resizer needs PyGObject, GTK 3 and Pillow: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1
    if not pictures:
        print(_("Usage: tuxtoys-image-resizer PICTURE..."), file=sys.stderr)
        return 2

    from tuxtoys.api import NotRunning
    from tuxtoys.client import Client

    try:
        client = Client.connect()
    except NotRunning:
        client = None

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Image Resizer"))
    application = Gtk.Application(
        application_id=f"{APP_ID}.ImageResizer", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    application.connect("activate", lambda app: ResizeWindow(app, pictures, client).present())
    return application.run(sys.argv[:1])
