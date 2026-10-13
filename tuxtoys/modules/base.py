"""What every module is, and what the daemon hands it."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar


def _discard(changes: Mapping[str, Any]) -> None:
    pass


@dataclass(frozen=True)
class Context:
    """What a module gets from the daemon when it is switched on."""

    # The session bus, a Gio.DBusConnection. Typed loosely so that this file, the daemon's
    # module host and their tests need no PyGObject.
    bus: Any
    # Every setting of the module, as read_settings() gives them from the config, as they
    # were when the module was switched on.
    settings: Mapping[str, Any]
    # Changes some of the module's settings the way SetModuleSettings does: checked, saved,
    # then handed back to apply_settings(). Raises ValueError for a bad change and OSError
    # when the config cannot be written, and then nothing changes.
    set_settings: Callable[[Mapping[str, Any]], None] = field(default=_discard)


class Module(ABC):
    """One tool. The daemon creates it, switches it on, and switches it off again."""

    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    # Off unless the module is harmless until used: after installing, nothing on the
    # system changes until the user picks a tool.
    enabled_by_default: ClassVar[bool] = False
    # Each setting's D-Bus type, by key. The settings live in the module's section of the
    # config, and the daemon serves them whether the module is on or off.
    settings_types: ClassVar[Mapping[str, str]] = {}

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        """Every setting, from the module's section of the config. A missing value, or one
        of the wrong kind, gives its default, so a config edited by hand cannot keep the
        module from starting.
        """
        return {}

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        """`settings` with `changes` made, all or none: ValueError, in English, for an
        unknown key or a value its key does not take.
        """
        for key in changes:
            raise ValueError(f"unknown setting: {key!r}")
        return dict(settings)

    @abstractmethod
    def enable(self, context: Context) -> None:
        """Switches the module on.

        If this raises, the daemon calls disable() to clean up whatever was set up before
        the failure, so disable() has to cope with a module that is only partly on.
        """

    @abstractmethod
    def disable(self) -> None:
        """Switches the module off and releases everything it holds: inhibitors, timers,
        windows, objects on the bus. Calling it twice does no harm.
        """

    def switched_off(self) -> None:  # noqa: B027
        """Called when the user switches the module off, just before disable(); not when the
        daemon stops at the end of a session. For what is set up once and kept across
        sessions, such as a keyboard shortcut, and taken away only on the user's word.
        """

    def apply_settings(self, settings: Mapping[str, Any]) -> None:  # noqa: B027
        """Takes on changed settings while on; `settings` is all of them, already saved."""
