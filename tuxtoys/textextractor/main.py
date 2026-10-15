"""Text Extractor as a program of its own, which its keyboard shortcut starts through
`tuxtoys textextractor`: the frozen screen to pick a region on, then tesseract reads it
and the text goes to the clipboard. The settings come from the daemon when it is there.
Without tesseract, or with no language for it, a notification says what to install.
"""

import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

from tuxtoys.core.i18n import _

INSTALLED_SETTINGS = Path("/usr/bin/tuxtoys-settings")


def settings_command(page: str) -> tuple[list[str], str | None]:
    """The settings window on a page: the installed one, or the checkout's, with the
    folder to start it in.
    """
    from tuxtoys.core.nemo_action import INSTALLED_ROOT, PACKAGE_ROOT

    if PACKAGE_ROOT == INSTALLED_ROOT and INSTALLED_SETTINGS.exists():
        return [str(INSTALLED_SETTINGS), "--page", page], None
    return [sys.executable, "-m", "tuxtoys.settings", "--page", page], str(PACKAGE_ROOT)


def main(argv: list[str] | None = None) -> int:
    del argv  # it takes no arguments
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gio, GLib, Gtk

        from tuxtoys.core import notifications
        from tuxtoys.overlay.toolbar import monitors_of, pointer_of
        from tuxtoys.platform.x11 import capture_screen
        from tuxtoys.textextractor.window import Extractor
    except (ImportError, ValueError) as error:
        print(
            _("Text Extractor needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys import APP_ID
    from tuxtoys.api import ModuleOff, NotRunning, Refused
    from tuxtoys.client import Client
    from tuxtoys.modules.textextractor import tesseract
    from tuxtoys.modules.textextractor.options import Options
    from tuxtoys.textextractor.reading import Request, read

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Text Extractor"))
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)

    def tell(summary: str, body: str) -> None:
        print(f"{summary} {body}".strip(), file=sys.stderr)
        notifications.send_now(bus, summary, body)

    languages = tesseract.installed()
    if languages is None:
        tell(
            _("Text Extractor needs tesseract."),
            _("Install it with: sudo apt install tesseract-ocr tesseract-ocr-hun"),
        )
        return 1
    if not languages:
        tell(
            _("Tesseract has no language to read."),
            _("Install one with: sudo apt install tesseract-ocr-eng"),
        )
        return 1

    options = Options()
    with suppress(NotRunning, ModuleOff, Refused):
        options = Options.read(Client.connect().module_settings("textextractor"))
    language = tesseract.pick(options.language, languages)

    screen = capture_screen()
    if screen is None:
        print(_("Text Extractor cannot see the screen."), file=sys.stderr)
        return 1
    display = Gdk.Display.get_default()
    copied = False

    def open_settings() -> None:
        command, folder = settings_command("textextractor")
        with suppress(OSError):
            subprocess.Popen(  # our own program, by its full path
                command,
                cwd=folder,
                env=dict(os.environ),
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

    def extract(request: Request) -> bool:
        nonlocal copied
        try:
            text = read(
                request,
                bytes(screen.get_pixels()),
                (screen.get_width(), screen.get_height()),
                screen.get_rowstride(),
                screen.get_n_channels(),
            )
        except (OSError, RuntimeError) as error:
            tell(_("Text Extractor could not read the text."), str(error))
            text = ""
        else:
            if not text:
                tell(_("No text found."), "")
        if text:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            # Handed to the clipboard manager, so it stays once this program has ended.
            clipboard.store()
            copied = True
        # A moment for the clipboard manager to take what was copied.
        GLib.timeout_add(400 if copied else 0, Gtk.main_quit)
        return False

    def done(request: Request | None) -> None:
        if request is None:
            GLib.idle_add(Gtk.main_quit)
        else:
            # After the window has gone from the screen.
            GLib.timeout_add(50, extract, request)

    extractor = Extractor(
        screen,
        monitors_of(display),
        pointer_of(display),
        languages,
        language,
        done,
        open_settings,
    )
    extractor.show_all()
    Gtk.main()
    return 0
