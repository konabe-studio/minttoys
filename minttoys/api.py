"""The D-Bus API: where each object is, and the shapes and errors that come back.

Shared by the daemon and its clients (the command line now, the panel icon and the settings
app later), with no PyGObject in it.

- io.github.konabe_studio.MintToys at /io/github/konabe_studio/MintToys: the modules,
  switching them on and off, and every module's settings; see
  minttoys/daemon/service.py.
- io.github.konabe_studio.MintToys.Awake at /io/github/konabe_studio/MintToys/modules/awake:
  see minttoys/modules/awake/module.py.
- io.github.konabe_studio.MintToys.LightSwitch at
  /io/github/konabe_studio/MintToys/modules/lightswitch: see
  minttoys/modules/lightswitch/module.py.
"""

from typing import NamedTuple

from minttoys import APP_ID, OBJECT_PATH

DAEMON_INTERFACE = APP_ID
AWAKE_PATH = f"{OBJECT_PATH}/modules/awake"
AWAKE_INTERFACE = f"{APP_ID}.Awake"
# Awake's settings over D-Bus, with the type each one travels as.
AWAKE_SETTINGS = {
    "default_mode": "s",
    "default_minutes": "u",
    "default_until": "s",
    "keep_screen": "b",
}
LIGHTSWITCH_PATH = f"{OBJECT_PATH}/modules/lightswitch"
LIGHTSWITCH_INTERFACE = f"{APP_ID}.LightSwitch"
LIGHTSWITCH_SETTINGS = {
    "day_mode": "s",
    "schedule": "s",
    "dark_from": "s",
    "dark_to": "s",
    "shortcut": "b",
}
# Every module's settings types, by module id, for clients that send settings.
MODULE_SETTINGS = {
    "awake": AWAKE_SETTINGS,
    "lightswitch": LIGHTSWITCH_SETTINGS,
}


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
