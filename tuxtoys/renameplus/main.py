"""Rename+'s window as a program of its own, run by its Nemo action with the chosen paths,
or by Nemo's Rename with their URIs. Each run opens a window of its own. It reads and
remembers its settings through the daemon, which D-Bus starts if need be; without it, it
starts from the defaults.
"""

import sys

from tuxtoys import APP_ID
from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, GLib, Gtk

        from tuxtoys.renameplus.window import RenameWindow, local_paths
    except (ImportError, ValueError) as error:
        print(_("Rename+ needs PyGObject and GTK 3: {error}").format(error=error), file=sys.stderr)
        return 1
    if not arguments:
        print(_("Usage: tuxtoys-rename ITEM..."), file=sys.stderr)
        return 2
    chosen, elsewhere = local_paths(arguments)
    for argument in elsewhere:
        print(
            _("Left out, as it is not on this computer: {item}").format(item=argument),
            file=sys.stderr,
        )
    if not chosen:
        return 1

    from tuxtoys.api import NotRunning
    from tuxtoys.client import Client

    try:
        client = Client.connect()
    except NotRunning:
        client = None

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Rename+"))
    application = Gtk.Application(
        application_id=f"{APP_ID}.RenamePlus", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    application.connect("activate", lambda app: RenameWindow(app, chosen, client).present())
    return application.run(sys.argv[:1])
