"""Items a tool adds to Nemo's right-click menu, as Nemo action files. Free of GTK.

Nemo reads actions from ~/.local/share/nemo/actions and watches the folder, so a file put
there shows at once. With an absolute path in Dependencies, Nemo shows the action only while
that file exists (nemo-action.c), so removing the package hides it on its own.

A tool's action is written when the tool comes on, in every language there is a catalogue
for, and again at each start of the daemon, so a new language or a moved checkout is picked
up; it is taken away only when the user switches the tool off.
"""

import logging
import os
import shlex
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from minttoys.core.i18n import in_every_language

log = logging.getLogger(__name__)

INSTALLED_ROOT = Path("/usr/lib/minttoys")
LIBEXEC = Path("/usr/libexec/minttoys")
# The checkout or the installed package: the folder that holds the minttoys package.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def actions_dir(environ: Mapping[str, str] = os.environ) -> Path:
    data_home = environ.get("XDG_DATA_HOME", "")
    root = Path(data_home) if os.path.isabs(data_home) else Path.home() / ".local" / "share"
    return root / "nemo" / "actions"


def program(
    package_root: Path, launcher: str, module: str, arguments: str = "%F"
) -> tuple[str, str]:
    """The command an action runs, and the file it depends on: the installed launcher, or
    the checkout's module when MintToys runs from a checkout. `arguments` follow it.
    """
    installed = LIBEXEC / launcher
    if package_root == INSTALLED_ROOT and installed.exists():
        return f"{installed} {arguments}", str(installed)
    main = package_root / Path(*module.split(".")) / "__main__.py"
    command = (
        f"env PYTHONPATH={shlex.quote(str(package_root))} "
        f"{shlex.quote(sys.executable)} -m {module} {arguments}"
    )
    return command, str(main)


def render(
    names: Mapping[str, str],
    comments: Mapping[str, str],
    command: str,
    dependency: str,
    icon: str,
    extensions: str = "any;",
    selection: str = "notnone",
) -> str:
    """An action file. `names` and `comments` map a language code to the text, "" to the
    English one. By default it is offered on one or more chosen files or folders.
    """
    lines = ["[Nemo Action]"]
    for key, texts in (("Name", names), ("Comment", comments)):
        lines.append(f"{key}={texts['']}")
        lines.extend(f"{key}[{lang}]={text}" for lang, text in sorted(texts.items()) if lang)
    lines += [
        f"Exec={command}",
        f"Icon-Name={icon}",
        f"Selection={selection}",
        f"Extensions={extensions}",
        "Quote=double",
        f"Dependencies={dependency};",
    ]
    return "\n".join(lines) + "\n"


@dataclass
class NemoAction:
    """One tool's action. `name` and `comment` are English messages marked with N_."""

    file_name: str
    name: str
    comment: str
    launcher: str  # in /usr/libexec/minttoys
    module: str  # python3 -m this, from a checkout
    icon: str
    extensions: str = "any;"
    # Nemo's Selection: notnone, any, none, s or m.
    selection: str = "notnone"
    # What follows the program: Nemo's %F (the chosen files), %P (the folder shown), and
    # options of the tool's own.
    arguments: str = "%F"
    folder: Callable[[], Path] = actions_dir
    package_root: Path = field(default=PACKAGE_ROOT)

    @property
    def path(self) -> Path:
        return self.folder() / self.file_name

    def write(self) -> None:
        """Puts the action in place, in one step so Nemo never reads half of it."""
        command, dependency = program(self.package_root, self.launcher, self.module, self.arguments)
        text = render(
            {"": self.name, **in_every_language(self.name)},
            {"": self.comment, **in_every_language(self.comment)},
            command,
            dependency,
            self.icon,
            self.extensions,
            self.selection,
        )
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

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)
        log.info("Nemo action removed: %s", self.path)
