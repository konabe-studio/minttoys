"""The daemon's process: one per session, owning MintToys' name on the session bus.

The bus name is the lock. A second daemon finds it taken and exits, leaving the first
alone. SIGTERM, which is what ending the session sends, and SIGINT switch every module off
before the process ends.

The objects go on the bus, and the modules on, as soon as the connection is up and before
the name is asked for. When D-Bus starts the daemon for a waiting call, it hands that call
over the moment the name is taken; an object put up only then could miss it, and the
caller would hear that it does not exist. A second daemon therefore switches its modules
on for the moment it takes to find the name taken, which a module's enable() has to allow.
"""

import logging
import signal

from gi.repository import Gio, GLib

from minttoys import BUS_NAME
from minttoys.core import config
from minttoys.daemon.host import lazy
from minttoys.daemon.service import DaemonService
from minttoys.modules import AVAILABLE

log = logging.getLogger("minttoysd")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="minttoysd: %(levelname)s: %(message)s")
    loop = GLib.MainLoop()
    loaders = {module_id: lazy(spec) for module_id, spec in AVAILABLE.items()}
    service = DaemonService(loaders, config.default_path())
    owned = False
    status = 0

    def on_bus_acquired(connection: Gio.DBusConnection, name: str) -> None:
        nonlocal status
        try:
            service.start(connection)
        except Exception:
            log.exception("could not start the modules")
            status = 1
            loop.quit()

    def on_name_acquired(connection: Gio.DBusConnection, name: str) -> None:
        nonlocal owned
        owned = True
        log.info("running as %s", name)

    def on_name_lost(connection: Gio.DBusConnection | None, name: str) -> None:
        nonlocal status
        if connection is None:
            log.error("cannot reach the session bus")
        elif owned:
            log.error("lost %s on the session bus", name)
        else:
            log.error("%s is taken: MintToys is already running in this session", name)
        status = 1
        loop.quit()

    def on_signal() -> bool:
        loop.quit()
        return GLib.SOURCE_REMOVE

    for signal_number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal_number, on_signal)

    owner = Gio.bus_own_name(
        Gio.BusType.SESSION,
        BUS_NAME,
        Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
        on_bus_acquired,
        on_name_acquired,
        on_name_lost,
    )
    try:
        loop.run()
    finally:
        service.stop()
        Gio.bus_unown_name(owner)
    log.info("stopped")
    return status
