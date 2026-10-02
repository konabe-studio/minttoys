"""Notification bubbles, through the desktop's notification server on the session bus.

Straight over D-Bus rather than through libnotify: the daemon already has the bus, and it
is one package fewer to depend on.
"""

import logging

from gi.repository import Gio, GLib

from minttoys import APP_ID

log = logging.getLogger(__name__)

BUS_NAME = "org.freedesktop.Notifications"
OBJECT_PATH = "/org/freedesktop/Notifications"
INTERFACE = "org.freedesktop.Notifications"


def send(bus: Gio.DBusConnection, summary: str, body: str) -> None:
    """Shows a bubble. It does not wait for the server, and a failure is logged, not raised:
    a notification that cannot be shown is no reason to stop anything else.
    """
    hints = {"desktop-entry": GLib.Variant("s", APP_ID)}
    arguments = GLib.Variant("(susssasa{sv}i)", ("MintToys", 0, "", summary, body, [], hints, -1))
    bus.call(
        BUS_NAME,
        OBJECT_PATH,
        INTERFACE,
        "Notify",
        arguments,
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        _finished,
    )


def _finished(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
    try:
        bus.call_finish(result)
    except GLib.Error as error:
        log.warning("could not show a notification: %s", error.message)
