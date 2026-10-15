"""A tool's own keyboard shortcut among Cinnamon's custom shortcuts, kept while the tool
and its setting are on and taken away when either goes off, as Light Switch does with
its own. Its keys are not taken when something else uses them already: the tool then
says so, and the user can set other keys in the Keyboard settings, where it shows.
"""

import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)


class Found(Protocol):
    path: str
    binding: list[str]


class Keybindings(Protocol):
    """Cinnamon's custom shortcuts; core.keybindings.CinnamonKeybindings is the real one."""

    def find(self, name: str, command: str) -> Found | None: ...
    def taken_by(self, keys: str) -> list[str]: ...
    def add(self, name: str, command: str, keys: str) -> None: ...
    def remove(self, path: str) -> None: ...


def cinnamon_keybindings() -> Keybindings:
    from tuxtoys.core.keybindings import CinnamonKeybindings

    return CinnamonKeybindings()


class CustomShortcut:
    def __init__(
        self,
        name: str,
        command: str,
        keys: str,
        make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings,
    ) -> None:
        self.name = name
        self.command = command
        self.keys = keys
        self._make = make_keybindings
        self._keybindings: Keybindings | None = None
        # "taken" when its keys were in use, "missing" without Cinnamon's settings.
        self.problem = ""

    def _bindings(self) -> Keybindings | None:
        if self._keybindings is None:
            try:
                self._keybindings = self._make()
            except RuntimeError:
                log.exception("no keyboard shortcut: Cinnamon's keybindings are not there")
                self.problem = "missing"
        return self._keybindings

    def _ours(self) -> Found | None:
        bindings = self._bindings()
        return None if bindings is None else bindings.find(self.name, self.command)

    def current_keys(self) -> str:
        """Its keys as they are now, which the user may have changed; "" for none."""
        ours = self._ours()
        return ours.binding[0] if ours is not None and ours.binding else ""

    def keep(self) -> None:
        """Adds the shortcut if it is not there, unless its keys are taken."""
        bindings = self._bindings()
        if bindings is None or self._ours() is not None:
            return
        taken = bindings.taken_by(self.keys)
        if taken:
            log.info("no keyboard shortcut: %s is taken by %s", self.keys, ", ".join(taken))
            self.problem = "taken"
            return
        self.problem = ""
        bindings.add(self.name, self.command, self.keys)

    def drop(self) -> None:
        if self.problem != "missing":
            self.problem = ""
        ours = self._ours()
        if ours is not None and self._keybindings is not None:
            self._keybindings.remove(ours.path)
