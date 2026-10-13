"""Rename+, as the daemon runs it: it keeps its Nemo action in place (see core.nemo_action),
serves its settings, and, when asked, makes Nemo's Rename open Rename+ on several items.
The window is a program of its own (tuxtoys.renameplus), which reads and saves the
settings through the daemon.

Nemo opens the program in its bulk-rename-tool setting when Rename (F2) is used on more
than one item, with their URIs after it; Mint sets it to Bulky. Rename+ remembers what was
there and puts it back when the setting or the tool is switched off; not at the end of a
session, and not when what is there is no longer Rename+.
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Protocol

from tuxtoys.api import RENAMEPLUS_SETTINGS
from tuxtoys.core.i18n import N_, _
from tuxtoys.core.nemo_action import NemoAction, program
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.renameplus.options import Options

log = logging.getLogger(__name__)

LAUNCHER = "tuxtoys-rename"
PROGRAM = "tuxtoys.renameplus"


class RenameTool(Protocol):
    """Nemo's bulk-rename-tool setting."""

    def get(self) -> str: ...
    def set(self, command: str) -> None: ...


def menu_item() -> NemoAction:
    return NemoAction(
        file_name="io.github.konabe_studio.TuxToys.renameplus.nemo_action",
        # TRANSLATORS: Rename+'s item in Nemo's right-click menu.
        name=N_("Rename with Rename+"),
        # TRANSLATORS: the tooltip of Rename+'s item in Nemo's right-click menu.
        comment=N_("Renames the chosen items together, with a preview."),
        launcher=LAUNCHER,
        module=PROGRAM,
        icon="document-edit-symbolic",
    )


def nemo_tool() -> RenameTool:
    from tuxtoys.modules.renameplus.nemo import NemoRenameTool

    return NemoRenameTool()


class RenamePlus(Module):
    id: ClassVar[str] = "renameplus"
    name: ClassVar[str] = _("Rename+")
    description: ClassVar[str] = _("Renames many files and folders at once, from Nemo.")
    settings_types: ClassVar[Mapping[str, str]] = RENAMEPLUS_SETTINGS

    def __init__(
        self,
        adapt: Callable[[NemoAction], NemoAction] = lambda action: action,
        tool: Callable[[], RenameTool] = nemo_tool,
    ) -> None:
        """The daemon writes the action where Nemo reads it and changes Nemo's own
        setting; the tests `adapt` the action to a folder of their own and hand in a
        `tool` of their own.
        """
        self.action = adapt(menu_item())
        self._tool_factory = tool
        self._tool: RenameTool | None = None
        self._context: Context | None = None
        self._options = Options()

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    @property
    def command(self) -> str:
        """What Nemo runs, with the URIs after it."""
        return program(self.action.package_root, LAUNCHER, PROGRAM, "")[0].strip()

    def enable(self, context: Context) -> None:
        self._context = context
        self._options = Options.read(context.settings)
        self.action.write()
        if self._options.nemo_rename:
            self._take_over()

    def disable(self) -> None:
        self._context = None  # the action and Nemo's setting stay; see switched_off()

    def switched_off(self) -> None:
        self.action.remove()
        self._give_back()

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        self._options = Options.read(settings)
        if self._options.nemo_rename:
            self._take_over()
        else:
            self._give_back()

    def _nemo(self) -> RenameTool | None:
        if self._tool is None:
            try:
                self._tool = self._tool_factory()
            except RuntimeError:
                log.exception("Nemo's Rename cannot be changed")
                return None
        return self._tool

    def _take_over(self) -> None:
        nemo = self._nemo()
        if nemo is None:
            return
        current = nemo.get()
        if current == self.command:
            return
        if not _is_ours(current) and current != self._options.previous_tool:
            # Remembered first, so a config that cannot be written changes nothing.
            if self._context is not None:
                self._context.set_settings({"previous_tool": current})
            self._options = self._options.update({"previous_tool": current})
        nemo.set(self.command)
        log.info("Nemo's Rename on several items now opens Rename+")

    def _give_back(self) -> None:
        nemo = self._nemo()
        if nemo is None or not _is_ours(nemo.get()):
            return
        nemo.set(self._options.previous_tool)
        log.info("Nemo's Rename on several items opens %r again", self._options.previous_tool)


def _is_ours(command: str) -> bool:
    """Whether a command is Rename+'s, from the package or from any checkout."""
    return LAUNCHER in command or f"-m {PROGRAM}" in command
