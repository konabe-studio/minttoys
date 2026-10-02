"""What every module is, and what the daemon hands it."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class Context:
    """What a module gets from the daemon when it is switched on."""

    # The session bus, a Gio.DBusConnection. Typed loosely so that this file, the daemon's
    # module host and their tests need no PyGObject.
    bus: Any
    # The module's own section of the config.
    settings: Mapping[str, Any]


class Module(ABC):
    """One tool. The daemon creates it, switches it on, and switches it off again."""

    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    enabled_by_default: ClassVar[bool] = True

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
