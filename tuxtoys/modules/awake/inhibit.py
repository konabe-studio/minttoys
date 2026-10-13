"""Keeps the session from suspending or going idle, through the session manager.

Cinnamon's session manager, cinnamon-session, answers on the session bus under the name
GNOME's uses, org.gnome.SessionManager, with GNOME's Inhibit and Uninhibit calls. Nothing
here touches a power or screensaver setting: an inhibitor is a request the session manager
keeps track of, and it ends when it is released or when the D-Bus connection that asked
for it goes away, so a crashed daemon cannot leave the computer stuck awake. The session
tests in tests/modules/awake/test_inhibit.py check both against the real session manager.
"""

from enum import IntFlag

from gi.repository import Gio, GLib

BUS_NAME = "org.gnome.SessionManager"
OBJECT_PATH = "/org/gnome/SessionManager"
INTERFACE = "org.gnome.SessionManager"


class Flags(IntFlag):
    """What an inhibitor holds off, as the session manager numbers it."""

    SUSPEND = 4
    IDLE = 8  # the session is not marked idle, which is what keeps the screen on


class Inhibitor:
    """At most one inhibitor at a time, replaced when what it holds off changes."""

    def __init__(self, connection: Gio.DBusConnection, app_id: str) -> None:
        self._connection = connection
        self._app_id = app_id
        self._cookie: int | None = None

    @property
    def held(self) -> bool:
        return self._cookie is not None

    def hold(self, flags: Flags, reason: str) -> None:
        """Holds off `flags`, in place of whatever was held so far.

        The new inhibitor is taken before the old one is released, so switching between
        screen-on and suspend-only never leaves a moment with nothing held. `reason` is
        shown to the user, in Cinnamon's log out dialog for one, so it is translated.
        """
        arguments = GLib.Variant("(susu)", (self._app_id, 0, reason, int(flags)))
        (cookie,) = self._call("Inhibit", arguments, "(u)")
        self.release()
        self._cookie = cookie

    def release(self) -> None:
        """Releases the inhibitor, if one is held."""
        if self._cookie is None:
            return
        cookie, self._cookie = self._cookie, None
        self._call("Uninhibit", GLib.Variant("(u)", (cookie,)), None)

    def _call(self, method: str, arguments: GLib.Variant, reply: str | None) -> tuple:
        result = self._connection.call_sync(
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE,
            method,
            arguments,
            GLib.VariantType(reply) if reply else None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        return result.unpack() if result else ()
