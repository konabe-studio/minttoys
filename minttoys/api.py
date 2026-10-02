"""The D-Bus API: where each object is, and the shapes and errors that come back.

Shared by the daemon and its clients (the command line now, the panel icon and the settings
app later), with no PyGObject in it.

- io.github.konabe_studio.MintToys at /io/github/konabe_studio/MintToys:
  ListModules() -> a(sssss), one ModuleInfo per module; SetModuleEnabled(id s, enabled b),
  saved in the config and applied at once.
- io.github.konabe_studio.MintToys.Awake at /io/github/konabe_studio/MintToys/modules/awake:
  see minttoys/modules/awake/module.py.
"""

from typing import NamedTuple

from minttoys import APP_ID, OBJECT_PATH

DAEMON_INTERFACE = APP_ID
AWAKE_PATH = f"{OBJECT_PATH}/modules/awake"
AWAKE_INTERFACE = f"{APP_ID}.Awake"


class ModuleInfo(NamedTuple):
    id: str
    name: str
    description: str
    state: str  # "on", "off" or "failed"
    error: str  # why it failed, empty otherwise


class NotRunning(Exception):
    """MintToys is not running in this session."""


class ModuleOff(Exception):
    """The module asked for is not switched on in the daemon."""


class Refused(Exception):
    """The daemon refused the call. The message says why, in English."""
