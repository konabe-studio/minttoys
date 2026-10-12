"""File Locksmith, as the daemon runs it: it keeps its Nemo action in place.

The action is written when File Locksmith comes on, in every language there is a catalogue
for, and again at each start of the daemon, so a new language or a moved checkout is picked
up. It is taken away only when the user switches File Locksmith off, not at the end of a
session. The window it opens is a program of its own (minttoys.locksmith) and needs no
daemon.
"""

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from minttoys.core.i18n import N_, _, in_every_language
from minttoys.modules.base import Context, Module
from minttoys.modules.locksmith import action

log = logging.getLogger(__name__)

# TRANSLATORS: File Locksmith's item in Nemo's right-click menu.
MENU_NAME = N_("What is using this?")
# TRANSLATORS: the tooltip of File Locksmith's item in Nemo's right-click menu.
MENU_COMMENT = N_("Shows the processes that hold it open, and lets you end them.")
PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class FileLocksmith(Module):
    id: ClassVar[str] = "locksmith"
    name: ClassVar[str] = _("File Locksmith")
    description: ClassVar[str] = _(
        "Shows which processes hold a file or a folder, from Nemo's right-click menu."
    )

    def __init__(
        self,
        folder: Callable[[], Path] = action.actions_dir,
        package_root: Path = PACKAGE_ROOT,
    ) -> None:
        """The daemon uses the defaults; the tests hand in a folder of their own."""
        self._folder = folder
        self._package_root = package_root

    @property
    def path(self) -> Path:
        return self._folder() / action.ACTION_NAME

    def enable(self, context: Context) -> None:
        command, dependency = action.program(self._package_root)
        text = action.render(
            {"": MENU_NAME, **in_every_language(MENU_NAME)},
            {"": MENU_COMMENT, **in_every_language(MENU_COMMENT)},
            command,
            dependency,
        )
        self._write(text)

    def disable(self) -> None:
        pass  # the action stays across sessions; see switched_off()

    def switched_off(self) -> None:
        self.path.unlink(missing_ok=True)
        log.info("Nemo action removed")

    def _write(self, text: str) -> None:
        """Replaces the action file in one step, so Nemo never reads half of it."""
        folder = self.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.read_text(encoding="utf-8") == text:
            return
        handle, temporary = tempfile.mkstemp(dir=folder, prefix=".minttoys-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        log.info("Nemo action written: %s", self.path)
