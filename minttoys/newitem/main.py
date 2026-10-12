"""New from template as a program of its own, run by New+'s Nemo action with the folder
Nemo shows and the folders chosen in it. Each run opens a window of its own.

    minttoys-new-from-template [--variables] [--hide-digits] FOLDER [CHOSEN...]

The item is made in the one chosen folder, or in FOLDER when none or several are chosen.
"""

import argparse
import sys
from pathlib import Path

from minttoys import APP_ID
from minttoys.core.i18n import _
from minttoys.modules.newplus import templates
from minttoys.newplus.main import config_home


def target_of(shown: str, chosen: list[str]) -> Path | None:
    """Where the new item goes: the one chosen folder, else the folder Nemo shows. None
    when neither is a folder on disk, as in Nemo's Recent or Trash.
    """
    folders = [Path(path) for path in chosen if path and Path(path).is_dir()]
    if len(folders) == 1 and len(chosen) == 1:
        return folders[0]
    return Path(shown) if shown and Path(shown).is_dir() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minttoys-new-from-template")
    parser.add_argument("--variables", action="store_true")
    parser.add_argument("--hide-digits", action="store_true")
    parser.add_argument("folder")
    parser.add_argument("chosen", nargs="*")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio, GLib, Gtk

        from minttoys.modules.newplus.create import Naming
        from minttoys.newitem.window import NewItemWindow
    except (ImportError, ValueError) as error:
        print(
            _("New+ needs PyGObject and GTK 3: {error}").format(error=error),
            file=sys.stderr,
        )
        return 1
    target = target_of(args.folder, args.chosen)
    if target is None:
        print(_("New from template works in a folder on disk."), file=sys.stderr)
        return 1

    naming = Naming(variables=args.variables, hide_digits=args.hide_digits)
    folder = templates.templates_dir(Path.home(), config_home())
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("New from template"))
    application = Gtk.Application(
        application_id=f"{APP_ID}.NewItem", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    application.connect(
        "activate", lambda app: NewItemWindow(app, target, folder, naming).present()
    )
    return application.run(sys.argv[:1])
