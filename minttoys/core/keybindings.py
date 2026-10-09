"""Cinnamon's custom keyboard shortcuts, written the way its Keyboard settings write them
(cinnamon-settings' KeybindingTable.py), so they show there and the user can change them.

A custom shortcut lives at /org/cinnamon/desktop/keybindings/custom-keybindings/customN/
with a name, a command and its keys, and is listed by name in
org.cinnamon.desktop.keybindings custom-list. Cinnamon rebuilds its shortcuts when that
list changes, so every write also adds or takes away a "__dummy__" entry, as Cinnamon does.
"""

from typing import NamedTuple

from gi.repository import Gio

from minttoys.core import accel, gsettings

PARENT = "org.cinnamon.desktop.keybindings"
CUSTOM = "org.cinnamon.desktop.keybindings.custom-keybinding"
BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings"
DUMMY = "__dummy__"
# Where Cinnamon's own shortcuts are, to check a new one against.
BUILT_IN = (
    PARENT,
    "org.cinnamon.desktop.keybindings.wm",
    "org.cinnamon.desktop.keybindings.media-keys",
)


class Custom(NamedTuple):
    path: str  # "custom3"
    name: str
    command: str
    binding: list[str]


class CinnamonKeybindings:
    def __init__(self) -> None:
        self._parent = gsettings.settings(PARENT)
        gsettings.settings(CUSTOM, f"{BASE}/{DUMMY}/")  # fails now if not installed

    def customs(self) -> list[Custom]:
        return [self._custom(path) for path in self._list() if path != DUMMY]

    def find(self, name: str, command: str) -> Custom | None:
        for custom in self.customs():
            if custom.name == name and custom.command == command:
                return custom
        return None

    def taken_by(self, keys: str) -> list[str]:
        """What already uses `keys`: Cinnamon's own shortcuts by their settings key, custom
        ones by their name.
        """
        found = []
        for schema in BUILT_IN:
            settings = self._parent if schema == PARENT else gsettings.settings(schema)
            for key in settings.props.settings_schema.list_keys():
                if key == "custom-list" or settings.get_value(key).get_type_string() != "as":
                    continue
                if any(accel.same(entry, keys) for entry in settings.get_strv(key)):
                    found.append(key)
        for custom in self.customs():
            if any(accel.same(entry, keys) for entry in custom.binding):
                found.append(custom.name)
        return found

    def add(self, name: str, command: str, keys: str) -> None:
        """Adds a custom shortcut at the lowest free customN, as Cinnamon numbers them."""
        listed = self._list()
        numbers = {
            int(path[6:]) for path in listed if path.startswith("custom") and path[6:].isdigit()
        }
        number = 0
        while number in numbers:
            number += 1
        path = f"custom{number}"
        settings = self._settings(path)
        settings.set_string("name", name)
        settings.set_string("command", command)
        settings.set_strv("binding", [keys])
        Gio.Settings.sync()
        self._set_list([*listed, path])

    def remove(self, path: str) -> None:
        settings = self._settings(path)
        settings.delay()
        for key in ("name", "command", "binding"):
            settings.reset(key)
        settings.apply()
        Gio.Settings.sync()
        self._set_list([entry for entry in self._list() if entry != path])

    def _list(self) -> list[str]:
        return list(self._parent.get_strv("custom-list"))

    def _set_list(self, paths: list[str]) -> None:
        # Cinnamon rebuilds its shortcuts only when the list changes.
        if DUMMY in paths:
            paths.remove(DUMMY)
        else:
            paths.append(DUMMY)
        self._parent.set_strv("custom-list", paths)

    def _settings(self, path: str) -> Gio.Settings:
        return gsettings.settings(CUSTOM, f"{BASE}/{path}/")

    def _custom(self, path: str) -> Custom:
        settings = self._settings(path)
        return Custom(
            path,
            settings.get_string("name"),
            settings.get_string("command"),
            list(settings.get_strv("binding")),
        )
