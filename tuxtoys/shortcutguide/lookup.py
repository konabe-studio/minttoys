"""The keys the user has now, read from GSettings for the sheets: Cinnamon's, Muffin's and the
Terminal's, and Cinnamon's custom shortcuts. A schema or key that is not installed reads as
nothing, so its shortcuts are left out.
"""

from collections.abc import Sequence

from gi.repository import Gio

from tuxtoys.core import gsettings
from tuxtoys.modules.shortcutguide.sheets import Setting


class Settings:
    def __init__(self) -> None:
        self._open: dict[tuple[str, str], Gio.Settings | None] = {}

    def _settings(self, schema: str, path: str) -> Gio.Settings | None:
        if (schema, path) not in self._open:
            try:
                self._open[schema, path] = gsettings.settings(schema, path or None)
            except RuntimeError:
                self._open[schema, path] = None
        return self._open[schema, path]

    def __call__(self, setting: Setting) -> Sequence[str] | str | None:
        settings = self._settings(setting.schema, setting.path)
        if settings is None or setting.key not in settings.props.settings_schema.list_keys():
            return None
        value = settings.get_value(setting.key)
        if value.get_type_string() == "as":
            return list(value.unpack())
        if value.get_type_string() == "s":
            return str(value.unpack())
        return None


def customs_and_above() -> tuple[list, list[str]]:
    """Cinnamon's custom shortcuts, and the keys of Muffin's toggle-above; none without
    Cinnamon's settings.
    """
    try:
        from tuxtoys.core.keybindings import CinnamonKeybindings

        bindings = CinnamonKeybindings()
        return bindings.customs(), bindings.wm_keys("toggle-above")
    except RuntimeError:
        return [], []
