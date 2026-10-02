"""The daemon's own object on the bus: the module list, and switching modules on and off.

Interface io.github.konabe_studio.MintToys at /io/github/konabe_studio/MintToys:

- ListModules() -> a(sssss): id, name, description, state ("on", "off" or "failed") and
  the error that made it fail, for every module
- SetModuleEnabled(id s, enabled b): saves the choice in the config, then applies the
  config. An unknown id is InvalidArgs. Whether the module then came on is for
  ListModules to say.
"""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from minttoys import OBJECT_PATH
from minttoys.api import DAEMON_INTERFACE
from minttoys.core import config
from minttoys.daemon.host import ModuleHost, ModuleLoader

log = logging.getLogger(__name__)

INTERFACE_XML = f"""
<node>
  <interface name="{DAEMON_INTERFACE}">
    <method name="ListModules">
      <arg name="modules" type="a(sssss)" direction="out"/>
    </method>
    <method name="SetModuleEnabled">
      <arg name="id" type="s" direction="in"/>
      <arg name="enabled" type="b" direction="in"/>
    </method>
  </interface>
</node>
"""


class DaemonService:
    def __init__(self, loaders: Mapping[str, ModuleLoader], config_path: Path) -> None:
        self._host = ModuleHost(loaders, save=self.save_settings)
        self._config_path = config_path
        self._bus: Gio.DBusConnection | None = None
        self._registration = 0

    def start(self, bus: Gio.DBusConnection) -> None:
        """Puts the object on the bus and switches the modules on as the config says."""
        self._bus = bus
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._registration = bus.register_object(
            OBJECT_PATH, node.interfaces[0], self._on_call, None, None
        )
        self._host.apply(config.load(self._config_path), bus)

    def stop(self) -> None:
        """Switches every module off and takes the object off the bus."""
        self._host.stop_all()
        if self._registration and self._bus is not None:
            self._bus.unregister_object(self._registration)
        self._registration = 0

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        if module_id not in self._host.module_ids:
            raise ValueError(f"unknown module: {module_id!r}")
        self._host.apply(self.save_settings(module_id, {"enabled": enabled}), self._bus)

    def save_settings(self, module_id: str, changes: Mapping[str, Any]) -> config.Config:
        """Merges `changes` into one module's section of the config file and saves it.

        The file is read again first, so what another writer saved in between is kept.
        Returns the config as saved.
        """
        settings = config.load(self._config_path)
        settings.set_module(module_id, {**settings.module(module_id), **changes})
        config.save(settings, self._config_path)
        return settings

    def _on_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        try:
            if method == "ListModules":
                rows = [tuple(info) for info in self._host.describe()]
                invocation.return_value(GLib.Variant("(a(sssss))", (rows,)))
            elif method == "SetModuleEnabled":
                self.set_module_enabled(*parameters.unpack())
                invocation.return_value(None)
        except ValueError as error:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(error))
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))
