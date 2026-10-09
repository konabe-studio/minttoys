"""Switches the modules on and off, each fenced off from the others.

A module that fails to import, or raises while being switched on or off, is logged and
marked failed. The daemon and every other module carry on.
"""

import importlib
import logging
from collections.abc import Callable, Mapping
from enum import StrEnum
from functools import partial
from typing import Any

from minttoys.api import ModuleInfo
from minttoys.core.config import Config
from minttoys.modules.base import Context, Module

log = logging.getLogger(__name__)

type ModuleLoader = Callable[[], type[Module]]


def lazy(spec: str) -> ModuleLoader:
    """A loader for "package.module:Class" that imports it only when called."""
    module_path, _, class_name = spec.partition(":")

    def load() -> type[Module]:
        return getattr(importlib.import_module(module_path), class_name)

    return load


class State(StrEnum):
    OFF = "off"
    ON = "on"
    FAILED = "failed"


type SettingsSetter = Callable[[str, Mapping[str, Any]], None]


def _discard(module_id: str, changes: Mapping[str, Any]) -> None:
    pass


class ModuleHost:
    def __init__(
        self, loaders: Mapping[str, ModuleLoader], set_settings: SettingsSetter = _discard
    ) -> None:
        """`set_settings(module_id, changes)` is what a module's Context.set_settings calls."""
        self._loaders = loaders
        self._set_settings = set_settings
        self._classes: dict[str, type[Module] | None] = {}
        # In the order they were switched on, so they go off in reverse.
        self._running: dict[str, Module] = {}
        self.states: dict[str, State] = dict.fromkeys(loaders, State.OFF)
        self.errors: dict[str, str] = {}

    def apply(self, config: Config, bus: object) -> None:
        """Switches each module on or off as `config` says, or as its default says.

        `bus` is the session bus, passed on to the modules in their Context.
        """
        for module_id in self._loaders:
            module_class = self._class(module_id)
            if module_class is None:
                continue
            section = config.module(module_id)
            wanted = section.get("enabled")
            if not isinstance(wanted, bool):
                wanted = module_class.enabled_by_default
            if wanted and module_id not in self._running:
                context = Context(
                    bus,
                    module_class.read_settings(section),
                    partial(self._set_settings, module_id),
                )
                self._enable(module_id, module_class, context)
            elif not wanted and module_id in self._running:
                self._switched_off(module_id)
                self._disable(module_id)

    def stop_all(self) -> None:
        """Switches every running module off, the last one switched on first."""
        for module_id in reversed(list(self._running)):
            self._disable(module_id)

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(self._loaders)

    def module_class(self, module_id: str) -> type[Module]:
        """The module's class, loading it if need be. ValueError for an id MintToys does
        not have, RuntimeError for a module that could not be loaded.
        """
        if module_id not in self._loaders:
            raise ValueError(f"unknown module: {module_id!r}")
        module_class = self._class(module_id)
        if module_class is None:
            raise RuntimeError(f"module {module_id} could not be loaded: {self.errors[module_id]}")
        return module_class

    def apply_settings(self, module_id: str, settings: Mapping[str, Any]) -> None:
        """Hands saved settings to the module, if it is on. Its error, if any, goes to the
        caller: the settings are saved by then, and the caller says that they did not all
        take effect.
        """
        module = self._running.get(module_id)
        if module is not None:
            module.apply_settings(settings)

    def describe(self) -> list[ModuleInfo]:
        """Every module with its state, as ListModules reports it. A module that could not
        be imported has no name or description to give, so it goes by its id.
        """
        infos = []
        for module_id in self._loaders:
            module_class = self._class(module_id)
            infos.append(
                ModuleInfo(
                    module_id,
                    module_class.name if module_class else module_id,
                    module_class.description if module_class else "",
                    str(self.states[module_id]),
                    self.errors.get(module_id, ""),
                )
            )
        return infos

    def _class(self, module_id: str) -> type[Module] | None:
        # A module that failed to import stays failed until the daemon restarts: importing
        # it again would only fail again.
        if module_id not in self._classes:
            try:
                self._classes[module_id] = self._loaders[module_id]()
            except Exception as error:
                log.exception("module %s could not be loaded", module_id)
                self._fail(module_id, error)
                self._classes[module_id] = None
        return self._classes[module_id]

    def _enable(self, module_id: str, module_class: type[Module], context: Context) -> None:
        module = module_class()
        try:
            module.enable(context)
        except Exception as error:
            log.exception("module %s could not be switched on", module_id)
            self._fail(module_id, error)
            try:
                module.disable()
            except Exception:
                log.exception("module %s could not clean up after that either", module_id)
            return
        self._running[module_id] = module
        self.states[module_id] = State.ON
        self.errors.pop(module_id, None)
        log.info("module %s is on", module_id)

    def _switched_off(self, module_id: str) -> None:
        """Tells a running module the user switched it off, before it goes off. Its error
        is logged and does not keep it from going off.
        """
        try:
            self._running[module_id].switched_off()
        except Exception:
            log.exception("module %s could not tidy up on being switched off", module_id)

    def _disable(self, module_id: str) -> None:
        module = self._running.pop(module_id)
        try:
            module.disable()
        except Exception as error:
            log.exception("module %s could not be switched off", module_id)
            self._fail(module_id, error)
            return
        self.states[module_id] = State.OFF
        log.info("module %s is off", module_id)

    def _fail(self, module_id: str, error: Exception) -> None:
        self.states[module_id] = State.FAILED
        self.errors[module_id] = f"{type(error).__name__}: {error}"
