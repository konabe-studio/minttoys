"""Color Picker as a program of its own, which its keyboard shortcut starts through
`tuxtoys colorpicker`: the picker or the editor first, as set (see app.py). The history
and the settings go through the daemon when it is there.
"""

import sys
from collections.abc import Callable
from contextlib import suppress

from tuxtoys.core.i18n import _


def main(argv: list[str] | None = None) -> int:
    del argv  # it takes no arguments
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, GLib, Gtk

        from tuxtoys.colorpicker.editor import EditorWindow
        from tuxtoys.colorpicker.picker import Picker
        from tuxtoys.platform.x11 import capture_screen
    except (ImportError, ValueError) as error:
        print(
            _("Color Picker needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys import APP_ID
    from tuxtoys.api import ModuleOff, NotRunning, Refused
    from tuxtoys.client import Client
    from tuxtoys.colorpicker.app import ColorPickerApp
    from tuxtoys.modules.colorpicker.colors import Color
    from tuxtoys.modules.colorpicker.options import Options

    client = None
    options = Options()
    with suppress(NotRunning, ModuleOff, Refused):
        client = Client.connect()
        options = Options.read(client.module_settings("colorpicker"))

    class GtkUi:
        def __init__(self) -> None:
            self._quitting = False

        def picker(self, options: Options, done: Callable[[Color | None, str], None]) -> bool:
            screen = capture_screen()
            if screen is None:
                print(_("Color Picker cannot see the screen."), file=sys.stderr)
                return False
            actions = {1: options.left, 2: options.middle, 3: options.right}
            picker = Picker(
                screen,
                options.template(options.default_format),
                options.show_name,
                actions,
                done,
            )
            picker.show_all()
            return True

        def editor(self, app: ColorPickerApp) -> EditorWindow:
            window = EditorWindow(app)
            window.connect("destroy", lambda _window: app.editor_closed())
            window.present()
            return window

        def copy(self, text: str) -> None:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            # Handed to the clipboard manager, so it stays once this program has ended.
            clipboard.store()

        def later(self, milliseconds: int, call: Callable[[], None]) -> None:
            GLib.timeout_add(milliseconds, lambda: call() and False)

        def quit(self) -> None:
            if not self._quitting:
                self._quitting = True
                # A moment for the clipboard manager to take what was copied.
                GLib.timeout_add(400, Gtk.main_quit)

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Color Picker"))
    ColorPickerApp(client, options, GtkUi()).start()
    Gtk.main()
    return 0
