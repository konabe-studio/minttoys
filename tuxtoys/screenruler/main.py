"""Screen Ruler as a program of its own, which its keyboard shortcut starts through
`tuxtoys screenruler`: the frozen screen with the ruler over it. The settings come from
the daemon when it is there, PowerToys' defaults otherwise.
"""

import sys
from contextlib import suppress

from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    del argv  # it takes no arguments
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, GLib, Gtk

        from tuxtoys.platform.x11 import capture_screen
        from tuxtoys.screenruler.ruler import Ruler, monitors_of, pointer_of
    except (ImportError, ValueError) as error:
        print(
            _("Screen Ruler needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys import APP_ID
    from tuxtoys.api import ModuleOff, NotRunning, Refused
    from tuxtoys.client import Client
    from tuxtoys.modules.screenruler.options import Options

    options = Options()
    with suppress(NotRunning, ModuleOff, Refused):
        options = Options.read(Client.connect().module_settings("screenruler"))

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Screen Ruler"))
    screen = capture_screen()
    if screen is None:
        print(_("Screen Ruler cannot see the screen."), file=sys.stderr)
        return 1
    display = Gdk.Display.get_default()
    copied = False

    def copy(text: str) -> None:
        nonlocal copied
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        # Handed to the clipboard manager, so it stays once this program has ended.
        clipboard.store()
        copied = True

    def closed(_window: Gtk.Window) -> None:
        # A moment for the clipboard manager to take what was copied.
        GLib.timeout_add(400 if copied else 0, Gtk.main_quit)

    ruler = Ruler(screen, monitors_of(display), pointer_of(display), options, copy)
    ruler.connect("destroy", closed)
    ruler.show_all()
    Gtk.main()
    return 0
