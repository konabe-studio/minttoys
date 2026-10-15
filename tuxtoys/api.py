"""The D-Bus API: where each object is, and the shapes and errors that come back.

Shared by the daemon and its clients (the command line now, the panel icon and the settings
app later), with no PyGObject in it.

- io.github.konabe_studio.TuxToys at /io/github/konabe_studio/TuxToys: the modules,
  switching them on and off, and every module's settings; see
  tuxtoys/daemon/service.py.
- io.github.konabe_studio.TuxToys.Awake at /io/github/konabe_studio/TuxToys/modules/awake:
  see tuxtoys/modules/awake/module.py.
- io.github.konabe_studio.TuxToys.LightSwitch at
  /io/github/konabe_studio/TuxToys/modules/lightswitch: see
  tuxtoys/modules/lightswitch/module.py.
"""

from typing import NamedTuple

from tuxtoys import APP_ID, OBJECT_PATH

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
ALWAYSONTOP_PATH = f"{OBJECT_PATH}/modules/alwaysontop"
ALWAYSONTOP_INTERFACE = f"{APP_ID}.AlwaysOnTop"
ALWAYSONTOP_SETTINGS = {
    "shortcut": "b",
    "opacity_shortcuts": "b",
    "border": "b",
    "border_color": "s",
    "border_width": "u",
    "border_opacity": "u",
    "border_radius": "u",
    "sound": "b",
    "excluded": "s",
}
NEWPLUS_SETTINGS = {
    "replace_variables": "b",
    "hide_digits": "b",
}
IMAGERESIZER_SETTINGS = {
    "sizes": "a(ssdds)",
    "selected": "u",
    "custom": "(sdds)",
    "shrink_only": "b",
    "replace_original": "b",
    "ignore_orientation": "b",
    "remove_metadata": "b",
    "jpeg_quality": "u",
    "file_name": "s",
    "keep_date": "b",
}
RENAMEPLUS_SETTINGS = {
    "regex": "b",
    "match_all": "b",
    "case_sensitive": "b",
    "apply_to": "s",
    "text_case": "s",
    "enumerate": "b",
    "randomize": "b",
    "include_files": "b",
    "include_folders": "b",
    "include_subfolders": "b",
    "recent_search": "as",
    "recent_replace": "as",
    "restore_flags": "b",
    "show_recent": "b",
    "nemo_rename": "b",
    "previous_tool": "s",
}
HOSTS_SETTINGS = {
    "show_warning": "b",
    "loopback_duplicates": "b",
    "backup": "b",
    "keep": "s",
    "count": "u",
    "days": "u",
}
ENVVARS_SETTINGS = {
    "variables": "a(ss)",
    "profiles": "a(sa(ss))",
    "active_profile": "s",
}
COLORPICKER_SETTINGS = {
    "shortcut": "b",
    "default_format": "s",
    "formats": "a(ssb)",
    "history": "as",
}
# Every module's settings types, by module id, for clients that send settings.
MODULE_SETTINGS = {
    "awake": AWAKE_SETTINGS,
    "lightswitch": LIGHTSWITCH_SETTINGS,
    "alwaysontop": ALWAYSONTOP_SETTINGS,
    "newplus": NEWPLUS_SETTINGS,
    "imageresizer": IMAGERESIZER_SETTINGS,
    "renameplus": RENAMEPLUS_SETTINGS,
    "hosts": HOSTS_SETTINGS,
    "envvars": ENVVARS_SETTINGS,
    "colorpicker": COLORPICKER_SETTINGS,
}


class ModuleInfo(NamedTuple):
    id: str
    name: str
    description: str
    state: str  # "on", "off" or "failed"
    error: str  # why it failed, empty otherwise


class NotRunning(Exception):
    """TuxToys is not running in this session."""


class ModuleOff(Exception):
    """The module asked for is not switched on in the daemon."""


class Refused(Exception):
    """The daemon refused the call. The message says why, in English."""
