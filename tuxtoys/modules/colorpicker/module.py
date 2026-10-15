"""Color Picker, as the daemon runs it: it keeps its keyboard shortcut, Super+Shift+C as in
PowerToys, among Cinnamon's custom shortcuts while it is on, and serves its settings. The
picker is a program of its own (tuxtoys.colorpicker), which the shortcut starts through
`tuxtoys colorpicker`.
"""

import shlex
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from tuxtoys.api import COLORPICKER_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.nemo_action import PACKAGE_ROOT, program
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.colorpicker.options import (
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)

LAUNCHER = "tuxtoys-color-picker"
PROGRAM = "tuxtoys.colorpicker"


def picker_command(package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The command that opens the picker: the installed program, or the checkout's."""
    return shlex.split(program(package_root, LAUNCHER, PROGRAM, "")[0])


class ColorPicker(Module):
    id: ClassVar[str] = "colorpicker"
    name: ClassVar[str] = _("Color Picker")
    description: ClassVar[str] = _(
        "Picks a color from anywhere on the screen with Super+Shift+C, and copies it."
    )
    settings_types: ClassVar[Mapping[str, str]] = COLORPICKER_SETTINGS

    def __init__(self, make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings) -> None:
        """The tests hand in Cinnamon's shortcuts of their own."""
        self.shortcut = CustomShortcut(
            SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS, make_keybindings
        )

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self.apply_settings(context.settings)

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        if Options.read(settings).shortcut:
            self.shortcut.keep()
        else:
            self.shortcut.drop()

    def disable(self) -> None:
        pass  # the shortcut stays across sessions; see switched_off()

    def switched_off(self) -> None:
        self.shortcut.drop()
