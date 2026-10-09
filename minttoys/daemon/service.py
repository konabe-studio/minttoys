"""The daemon's own object on the bus: the modules, switching them on and off, and their
settings.

Interface io.github.konabe_studio.MintToys at /io/github/konabe_studio/MintToys:

- ListModules() -> a(sssss): id, name, description, state ("on", "off" or "failed") and
  the error that made it fail, for every module
- SetModuleEnabled(id s, enabled b): saves the choice in the config, then applies the
  config. An unknown id is InvalidArgs. Whether the module then came on is for
  ListModules, and ModulesChanged, to say.
- GetModuleSettings(id s) -> a{sv}: every setting of the module, on or off
- SetModuleSettings(id s, settings a{sv}): checks the settings given, saves them, the
  rest stay, and hands them to the module if it is on. An unknown id or setting, or a bad
  value, is InvalidArgs, and then nothing changes.
- ModulesChanged(a(sssss)): what ListModules gives, after SetModuleEnabled
- ModuleSettingsChanged(id s, settings a{sv}): every setting of that module, whenever one
  changes
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
from minttoys.modules.base import Module

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
    <method name="GetModuleSettings">
      <arg name="id" type="s" direction="in"/>
      <arg name="settings" type="a{{sv}}" direction="out"/>
    </method>
    <method name="SetModuleSettings">
      <arg name="id" type="s" direction="in"/>
      <arg name="settings" type="a{{sv}}" direction="in"/>
    </method>
    <signal name="ModulesChanged">
      <arg name="modules" type="a(sssss)"/>
    </signal>
    <signal name="ModuleSettingsChanged">
      <arg name="id" type="s"/>
      <arg name="settings" type="a{{sv}}"/>
    </signal>
  </interface>
</node>
"""


class DaemonService:
    def __init__(self, loaders: Mapping[str, ModuleLoader], config_path: Path) -> None:
        self._host = ModuleHost(loaders, set_settings=self.set_module_settings)
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
        self._emit("ModulesChanged", GLib.Variant("(a(sssss))", (self._modules(),)))

    def module_settings(self, module_id: str) -> dict[str, Any]:
        module_class = self._host.module_class(module_id)
        return module_class.read_settings(config.load(self._config_path).module(module_id))

    def set_module_settings(self, module_id: str, changes: Mapping[str, Any]) -> None:
        """Checks `changes`, saves them, says so on the bus, and hands every setting to the
        module if it is on. A bad change raises ValueError and an unwritable config
        OSError, and then nothing changes. If the module cannot take the settings on, its
        error comes through, though they are saved by then.
        """
        module_class = self._host.module_class(module_id)
        current = module_class.read_settings(config.load(self._config_path).module(module_id))
        updated = module_class.check_settings(current, changes)
        self.save_settings(module_id, {key: updated[key] for key in changes})
        arguments = GLib.Variant("(sa{sv})", (module_id, self._typed(module_class, updated)))
        self._emit("ModuleSettingsChanged", arguments)
        self._host.apply_settings(module_id, updated)

    def save_settings(self, module_id: str, changes: Mapping[str, Any]) -> config.Config:
        """Merges `changes` into one module's section of the config file and saves it.

        The file is read again first, so what another writer saved in between is kept.
        Returns the config as saved.
        """
        settings = config.load(self._config_path)
        settings.set_module(module_id, {**settings.module(module_id), **changes})
        config.save(settings, self._config_path)
        return settings

    def _modules(self) -> list[tuple]:
        return [tuple(info) for info in self._host.describe()]

    @staticmethod
    def _typed(module_class: type[Module], settings: Mapping[str, Any]) -> dict:
        types = module_class.settings_types
        return {key: GLib.Variant(types[key], value) for key, value in settings.items()}

    def _emit(self, signal: str, arguments: GLib.Variant) -> None:
        if self._bus is not None and self._registration:
            self._bus.emit_signal(None, OBJECT_PATH, DAEMON_INTERFACE, signal, arguments)

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
                invocation.return_value(GLib.Variant("(a(sssss))", (self._modules(),)))
            elif method == "SetModuleEnabled":
                self.set_module_enabled(*parameters.unpack())
                invocation.return_value(None)
            elif method == "GetModuleSettings":
                (module_id,) = parameters.unpack()
                module_class = self._host.module_class(module_id)
                settings = self._typed(module_class, self.module_settings(module_id))
                invocation.return_value(GLib.Variant("(a{sv})", (settings,)))
            elif method == "SetModuleSettings":
                self.set_module_settings(*parameters.unpack())
                invocation.return_value(None)
        except ValueError as error:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(error))
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))
