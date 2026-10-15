"""A tool's own entry in the applications menu, written while the tool is on. Free of GTK.

Like a Nemo action (see nemo_action), it goes into the user's data folder, where Cinnamon's
menu picks it up at once, in every language there is a catalogue for; it is written again
at each start of the daemon and taken away when the user switches the tool off. Installed,
TryExec names the program, so removing the package hides the entry on its own.
"""

import logging
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tuxtoys import APP_ID
from tuxtoys.core.i18n import in_every_language
from tuxtoys.core.nemo_action import LIBEXEC, PACKAGE_ROOT, program

log = logging.getLogger(__name__)


def applications_dir(environ: Mapping[str, str] = os.environ) -> Path:
    data_home = environ.get("XDG_DATA_HOME", "")
    root = Path(data_home) if os.path.isabs(data_home) else Path.home() / ".local" / "share"
    return root / "applications"


@dataclass
class MenuEntry:
    """One tool's entry. `name` and `comment` are English messages marked with N_."""

    file_name: str
    name: str
    comment: str
    launcher: str  # in /usr/libexec/tuxtoys
    module: str  # python3 -m this, from a checkout
    categories: str = "System;Settings;"
    folder: Callable[[], Path] = applications_dir
    package_root: Path = field(default=PACKAGE_ROOT)

    @property
    def path(self) -> Path:
        return self.folder() / self.file_name

    def text(self) -> str:
        command, dependency = program(self.package_root, self.launcher, self.module, "")
        lines = ["[Desktop Entry]", "Type=Application"]
        for key, message in (("Name", self.name), ("Comment", self.comment)):
            lines.append(f"{key}={message}")
            lines.extend(
                f"{key}[{lang}]={text}" for lang, text in sorted(in_every_language(message).items())
            )
        lines.append(f"Exec={command.strip()}")
        if Path(dependency).parent == LIBEXEC:
            lines.append(f"TryExec={dependency}")
        lines += [
            f"Icon={APP_ID}",
            f"Categories={self.categories}",
            "OnlyShowIn=X-Cinnamon;",
            "StartupNotify=true",
        ]
        return "\n".join(lines) + "\n"

    def write(self) -> None:
        """Puts the entry in place, in one step so the menu never reads half of it."""
        text = self.text()
        folder = self.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.read_text(encoding="utf-8") == text:
            return
        handle, temporary = tempfile.mkstemp(dir=folder, prefix=".tuxtoys-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        log.info("menu entry written: %s", self.path)

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)
        log.info("menu entry removed: %s", self.path)
