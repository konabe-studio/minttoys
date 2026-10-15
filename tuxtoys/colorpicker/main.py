"""Color Picker's picker as a program of its own, which its keyboard shortcut starts
through `tuxtoys colorpicker`. It takes a picture of the screen first, then shows it; a
picked color goes to the clipboard in the format set, and into the history, through the
daemon when it is there.
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

        from tuxtoys.colorpicker.picker import Picker
        from tuxtoys.platform.x11 import capture_screen
    except (ImportError, ValueError) as error:
        print(
            _("Color Picker needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys.api import ModuleOff, NotRunning, Refused
    from tuxtoys.client import Client
    from tuxtoys.modules.colorpicker.colors import Color, format_color
    from tuxtoys.modules.colorpicker.options import Options

    screen = capture_screen()
    if screen is None:
        print(_("Color Picker cannot see the screen."), file=sys.stderr)
        return 1
    client = None
    options = Options()
    with suppress(NotRunning, ModuleOff, Refused):
        client = Client.connect()
        options = Options.read(client.module_settings("colorpicker"))

    def picked(color: Color) -> None:
        text = format_color(color, options.template(options.default_format))
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        # Handed to the clipboard manager, so it stays once this program has ended.
        clipboard.store()
        if client is not None:
            with suppress(NotRunning, ModuleOff, Refused):
                client.set_module_settings(
                    "colorpicker", {"history": list(options.picked(color).history)}
                )

    picker = Picker(screen, options.template(options.default_format), picked)
    # A moment more than needed once it has closed, for the clipboard manager to take it.
    picker.connect("destroy", lambda _window: GLib.timeout_add(400, Gtk.main_quit))
    picker.show_all()
    Gtk.main()
    return 0
