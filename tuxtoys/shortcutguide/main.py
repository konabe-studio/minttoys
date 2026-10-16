"""Shortcut Guide as a program of its own, which its keyboard shortcut starts: the window of
shortcuts at the edge of the monitor the pointer is on. Pressed again while the window is
open, the shortcut puts it away. Over an excluded app it does nothing.
"""

import os
import subprocess
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

        from tuxtoys.shortcutguide.lookup import Settings, customs_and_above
        from tuxtoys.shortcutguide.window import Guide, Tab
    except (ImportError, ValueError) as error:
        print(
            _("Shortcut Guide needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1

    from tuxtoys import APP_ID
    from tuxtoys.api import ModuleOff, NotRunning, Refused
    from tuxtoys.client import Client
    from tuxtoys.modules.shortcutguide import apps, cinnamon, keys
    from tuxtoys.modules.shortcutguide.options import Options
    from tuxtoys.modules.shortcutguide.placing import panel
    from tuxtoys.modules.shortcutguide.reading import (
        cinnamon_sections,
        read,
        tuxtoys_sections,
    )
    from tuxtoys.overlay.monitors import Monitor
    from tuxtoys.textextractor.main import settings_command

    client = None
    options = Options()
    with suppress(NotRunning, ModuleOff, Refused):
        client = Client.connect()
        options = Options.read(client.module_settings("shortcutguide"))

    # Before any window of ours takes the focus.
    wm_class = ""
    with suppress(ImportError, OSError, RuntimeError):
        from tuxtoys.platform.x11 import active_window_class

        wm_class = active_window_class()
    if wm_class.lower() in options.excluded_apps:
        return 0

    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Shortcut Guide"))
    application = Gtk.Application(application_id=f"{APP_ID}.ShortcutGuide")
    guide: Guide | None = None

    def save_pins(pins: tuple[str, ...]) -> None:
        if client is not None:
            with suppress(NotRunning, ModuleOff, Refused):
                client.set_module_settings("shortcutguide", {"pinned": list(pins)})

    def open_settings() -> None:
        command, folder = settings_command("shortcutguide")
        with suppress(OSError):
            subprocess.Popen(  # our own program, by its full path
                command,
                cwd=folder,
                env=dict(os.environ),
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

    def tabs() -> tuple[list[Tab], str]:
        lookup = Settings()
        customs, above = customs_and_above()
        found = [
            Tab("cinnamon", "Cinnamon", cinnamon.SHEET.icon, cinnamon_sections(lookup, customs))
        ]
        ours = tuxtoys_sections(customs, above)
        if ours:
            found.append(Tab("tuxtoys", "TuxToys", f"{APP_ID}-symbolic", ours))
        first = "cinnamon"
        sheet = apps.for_window(wm_class)
        if sheet is not None:
            sections = read(sheet, lookup)
            if sections:
                found.append(Tab(sheet.id, sheet.name, sheet.icon, sections))
                first = sheet.id
        return found, first

    def geometry() -> tuple[int, int, int, int]:
        display = Gdk.Display.get_default()
        _screen, x, y = display.get_default_seat().get_pointer().get_position()
        area = display.get_monitor_at_point(x, y).get_workarea()
        return panel(Monitor(area.x, area.y, area.width, area.height), options.position)

    def name_above_tab() -> None:
        """Names Muffin's Above_Tab after what the layout has on the key above Tab, the
        key whose X keycode is 49 (TLDE).
        """
        keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
        found, keyval, *_rest = keymap.translate_keyboard_state(49, Gdk.ModifierType(0), 0)
        character = chr(Gdk.keyval_to_unicode(keyval)) if found else ""
        if character.strip():
            keys.LAYOUT_NAMES["Above_Tab"] = character.upper()

    def activate(app: Gtk.Application) -> None:
        nonlocal guide
        if guide is not None:
            # The shortcut again, from a second start: put the guide away.
            guide.close()
            return
        name_above_tab()
        found, first = tabs()
        guide = Guide(app, found, first, options.pinned, geometry(), save_pins, open_settings)
        guide.present_with_time(Gtk.get_current_event_time() or Gdk.CURRENT_TIME)

    application.connect("activate", activate)
    return application.run([])
