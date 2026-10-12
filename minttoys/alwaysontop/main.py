"""The frame helper: draws a frame around every window Muffin keeps above the others, until
the daemon stops it. Started by the Always on Top module, not by hand.
"""

import argparse
import logging
import signal
import sys

from minttoys.modules.alwaysontop.options import LEAST_OPACITY, MOST_RADIUS, MOST_WIDTH

log = logging.getLogger("minttoys-always-on-top")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minttoys-always-on-top")
    parser.add_argument("--width", type=int, default=4, choices=range(1, MOST_WIDTH + 1))
    parser.add_argument("--opacity", type=int, default=100, choices=range(LEAST_OPACITY, 101))
    parser.add_argument("--radius", type=int, default=8, choices=range(MOST_RADIUS + 1))
    parser.add_argument("--color", default="")
    parser.add_argument("--sound", action="store_true")
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk

        from minttoys.alwaysontop.border import Borders, Sounds, Style, parse_color, theme_accent
        from minttoys.platform.x11 import AboveWindows
    except (ImportError, ValueError) as error:
        log.error("cannot draw frames: %s", error)
        return 1
    if not Gtk.init_check(sys.argv)[0]:
        log.error("cannot draw frames: no display")
        return 1

    style = Style(parse_color(args.color) or theme_accent(), args.width, args.opacity, args.radius)
    borders = Borders(style, Sounds() if args.sound else None)
    windows = AboveWindows(borders.show, args.exclude)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, Gtk.main_quit)
    log.info("framing windows kept above")
    Gtk.main()
    del windows
    return 0
