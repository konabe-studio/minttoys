"""What Light Switch reads from and writes to Cinnamon, through GSettings: the themes, as the
Themes window writes them, and Night Light's schedule.
"""

from pathlib import Path

from gi.repository import Gio, GLib

from minttoys.modules.lightswitch import styles
from minttoys.modules.lightswitch.schedule import NightLight
from minttoys.modules.lightswitch.styles import Look, Style

INTERFACE = "org.cinnamon.desktop.interface"
THEME = "org.cinnamon.theme"
PORTAL = "org.x.apps.portal"
COLOR = "org.cinnamon.settings-daemon.plugins.color"


def _settings(schema: str) -> Gio.Settings:
    # Gio.Settings.new aborts the whole process for a schema that is not installed, so ask
    # first: outside Cinnamon this is an error for this module alone.
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema, True) is None:
        raise RuntimeError(f"Light Switch needs Cinnamon: no {schema} settings")
    return Gio.Settings.new(schema)


class CinnamonDesktop:
    def __init__(self) -> None:
        self._interface = _settings(INTERFACE)
        self._theme = _settings(THEME)
        self._portal = _settings(PORTAL)
        self._color = _settings(COLOR)
        self._installed = styles.Installed(
            Path(GLib.get_home_dir()),
            Path(GLib.get_user_data_dir()),
            [Path(directory) for directory in GLib.get_system_data_dirs()],
        )

    def look(self) -> Look:
        return Look(
            gtk=self._interface.get_string("gtk-theme"),
            icons=self._interface.get_string("icon-theme"),
            cinnamon=self._theme.get_string("name"),
            cursor=self._interface.get_string("cursor-theme"),
        )

    def styles(self) -> list[Style]:
        return styles.load(self._installed)

    def write(self, mode: str, look: Look) -> None:
        """Sets a mode the way the Themes window's activate_mode and activate_variant do."""
        self._portal.set_string("color-scheme", styles.COLOR_SCHEMES[mode])
        self._interface.set_string("gtk-theme", look.gtk)
        self._interface.set_string("icon-theme", look.icons)
        self._theme.set_string("name", look.cinnamon)
        self._interface.set_string("cursor-theme", look.cursor)

    def night_light(self) -> NightLight:
        latitude, longitude = self._color.get_value("night-light-last-coordinates").unpack()
        return NightLight(
            mode=self._color.get_string("night-light-schedule-mode"),
            start=self._color.get_double("night-light-schedule-from"),
            end=self._color.get_double("night-light-schedule-to"),
            latitude=latitude,
            longitude=longitude,
        )
