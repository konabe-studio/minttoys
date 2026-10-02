"""Talks to the daemon over the session bus: the command line now, the settings app later.

Every call is synchronous and turns D-Bus errors into the exceptions in minttoys.api, so a
caller never has to look at a D-Bus error name.
"""

from gi.repository import Gio, GLib

from minttoys import BUS_NAME, OBJECT_PATH
from minttoys.api import (
    AWAKE_INTERFACE,
    AWAKE_PATH,
    DAEMON_INTERFACE,
    ModuleInfo,
    ModuleOff,
    NotRunning,
    Refused,
)

NOT_RUNNING = {
    "org.freedesktop.DBus.Error.ServiceUnknown",
    "org.freedesktop.DBus.Error.NameHasNoOwner",
}
# Nothing at the module's path: the module is switched off, or failed to come on.
MODULE_OFF = {
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.UnknownObject",
    "org.freedesktop.DBus.Error.UnknownInterface",
}


class Client:
    def __init__(self, bus: Gio.DBusConnection) -> None:
        self._bus = bus

    @classmethod
    def connect(cls) -> "Client":
        try:
            return cls(Gio.bus_get_sync(Gio.BusType.SESSION))
        except GLib.Error as error:
            raise NotRunning(error.message) from error

    def modules(self) -> list[ModuleInfo]:
        (rows,) = self._call(OBJECT_PATH, DAEMON_INTERFACE, "ListModules", None, "(a(sssss))")
        return [ModuleInfo(*row) for row in rows]

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        arguments = GLib.Variant("(sb)", (module_id, enabled))
        self._call(OBJECT_PATH, DAEMON_INTERFACE, "SetModuleEnabled", arguments, None)

    def awake_state(self) -> dict:
        (state,) = self._call(AWAKE_PATH, AWAKE_INTERFACE, "GetState", None, "(a{sv})")
        return state

    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None:
        arguments = GLib.Variant("(susb)", (mode, minutes, until, keep_screen))
        self._call(AWAKE_PATH, AWAKE_INTERFACE, "Start", arguments, None)

    def awake_stop(self) -> None:
        self._call(AWAKE_PATH, AWAKE_INTERFACE, "Stop", None, None)

    def awake_toggle(self) -> None:
        self._call(AWAKE_PATH, AWAKE_INTERFACE, "Toggle", None, None)

    def awake_set_keep_screen(self, keep_screen: bool) -> None:
        arguments = GLib.Variant("(b)", (keep_screen,))
        self._call(AWAKE_PATH, AWAKE_INTERFACE, "SetKeepScreen", arguments, None)

    def _call(
        self,
        path: str,
        interface: str,
        method: str,
        arguments: GLib.Variant | None,
        reply: str | None,
    ) -> tuple:
        try:
            result = self._bus.call_sync(
                BUS_NAME,
                path,
                interface,
                method,
                arguments,
                GLib.VariantType(reply) if reply else None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error as error:
            remote = Gio.DBusError.get_remote_error(error)
            if remote in NOT_RUNNING:
                raise NotRunning(error.message) from error
            if remote in MODULE_OFF:
                raise ModuleOff(error.message) from error
            raise Refused(error.message.removeprefix(f"GDBus.Error:{remote}: ")) from error
        return result.unpack()
