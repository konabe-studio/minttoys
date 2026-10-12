"""The frame helper: draws a frame around every window Muffin keeps above the others, until
the daemon stops it. Started by the Always on Top module, not by hand.
"""

import argparse
import logging
import signal
import sys

from minttoys.modules.alwaysontop.options import MOST_WIDTH

log = logging.getLogger("minttoys-always-on-top")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minttoys-always-on-top")
    parser.add_argument("--width", type=int, default=4, choices=range(1, MOST_WIDTH + 1))
    parser.add_argument("--color", default="")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk

        from minttoys.alwaysontop.border import Borders, parse_color, theme_accent
        from minttoys.platform.x11 import AboveWindows
    except (ImportError, ValueError) as error:
        log.error("cannot draw frames: %s", error)
        return 1
    if not Gtk.init_check(sys.argv)[0]:
        log.error("cannot draw frames: no display")
        return 1

    borders = Borders(parse_color(args.color) or theme_accent(), args.width)
    windows = AboveWindows(borders.show)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, Gtk.main_quit)
    log.info("framing windows kept above")
    Gtk.main()
    del windows
    return 0
