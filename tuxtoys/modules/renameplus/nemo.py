"""Nemo's bulk-rename-tool setting, through GSettings: the program Nemo's Rename (F2)
opens on more than one item. A byte string, `bulky` on Linux Mint.
"""

from gi.repository import GLib

from tuxtoys.core.gsettings import settings

SCHEMA = "org.nemo.preferences"
KEY = "bulk-rename-tool"


class NemoRenameTool:
    def __init__(self) -> None:
        self._settings = settings(SCHEMA)

    def get(self) -> str:
        return self._settings.get_value(KEY).get_bytestring().decode("utf-8", "replace")

    def set(self, command: str) -> None:
        self._settings.set_value(KEY, GLib.Variant.new_bytestring(command.encode("utf-8")))
