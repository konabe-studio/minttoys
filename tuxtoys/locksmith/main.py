"""File Locksmith's window as a program of its own, run by its Nemo action with the chosen
files and folders. Each run opens a window of its own.
"""

import sys

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    targets = sys.argv[1:] if argv is None else argv
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, GLib, Gtk

        from tuxtoys.locksmith.window import LocksmithWindow
    except (ImportError, ValueError) as error:
        print(
            _("File Locksmith needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1
    if not targets:
        print(_("Usage: tuxtoys-locksmith FILE..."), file=sys.stderr)
        return 2

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("File Locksmith"))
    application = Gtk.Application(
        application_id=f"{APP_ID}.Locksmith", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    application.connect("activate", lambda app: LocksmithWindow(app, targets).present())
    return application.run(sys.argv[:1])
