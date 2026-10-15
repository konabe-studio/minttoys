"""Environment Variables, as the daemon runs it: it keeps ~/.config/tuxtoys/environment
written from its settings, and the lines in ~/.xsessionrc and ~/.bashrc that load it,
while it is on (see userfile); and its entry in the applications menu. The system's
variables are /etc/environment, which the window saves through pkexec, never through the
daemon, which runs as the user.

Switching it off takes both lines and the file away again; an ~/.xsessionrc left with
nothing in it goes too. Settings stay in TuxToys' config, for when it comes back on.
"""

import logging
import os
import shlex
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from tuxtoys.api import ENVVARS_SETTINGS
from tuxtoys.core.i18n import N_, _
from tuxtoys.core.menu_entry import MenuEntry
from tuxtoys.core.nemo_action import PACKAGE_ROOT, program
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.envvars import userfile
from tuxtoys.modules.envvars.options import Options

log = logging.getLogger(__name__)

LAUNCHER = "tuxtoys-environment-variables"
PROGRAM = "tuxtoys.envvars"


def menu_entry() -> MenuEntry:
    return MenuEntry(
        file_name="io.github.konabe_studio.TuxToys.EnvironmentVariables.desktop",
        name=N_("Environment Variables"),
        # TRANSLATORS: the tooltip of Environment Variables' entry in the applications menu.
        comment=N_("Set your environment variables, profiles of them, and the system's"),
        launcher=LAUNCHER,
        module=PROGRAM,
    )


def editor_command(package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The command that opens the window: the installed program, or the checkout's."""
    return shlex.split(program(package_root, LAUNCHER, PROGRAM, "")[0])


def config_home(environ: Mapping[str, str] = os.environ) -> Path:
    value = environ.get("XDG_CONFIG_HOME", "")
    return Path(value) if os.path.isabs(value) else Path.home() / ".config"


class EnvironmentVariables(Module):
    id: ClassVar[str] = "envvars"
    name: ClassVar[str] = _("Environment Variables")
    description: ClassVar[str] = _("Sets your environment variables, and profiles of them.")
    settings_types: ClassVar[Mapping[str, str]] = ENVVARS_SETTINGS

    def __init__(
        self,
        home: Callable[[], Path] = Path.home,
        config: Callable[[], Path] = config_home,
        adapt: Callable[[MenuEntry], MenuEntry] = lambda entry: entry,
    ) -> None:
        """The tests hand in a home and a config folder of their own, and `adapt` the
        menu entry to a folder of their own.
        """
        self._home = home
        self._config = config
        self.entry = adapt(menu_entry())

    @property
    def file(self) -> Path:
        return self._config() / "tuxtoys" / "environment"

    @property
    def loaders(self) -> tuple[Path, Path]:
        """~/.xsessionrc for the session, ~/.bashrc for each new terminal."""
        return self._home() / ".xsessionrc", self._home() / ".bashrc"

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self.entry.write()
        self.apply_settings(context.settings)
        line = userfile.hook(str(self.file))
        session, terminal = self.loaders
        _write(session, userfile.with_hook(_text(session), line))
        if terminal.exists():
            _write(terminal, userfile.with_hook(_text(terminal), line))

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        options = Options.read(settings)
        _write(self.file, userfile.render(options.variables, options.applied))

    def disable(self) -> None:
        pass  # the file and its lines stay across sessions; see switched_off()

    def switched_off(self) -> None:
        self.entry.remove()
        session, terminal = self.loaders
        for path in (session, terminal):
            if path.exists():
                left = userfile.without_hook(_text(path))
                if path == session and not left.strip():
                    path.unlink()
                    log.info("removed %s, which only loaded TuxToys' variables", path)
                elif left != _text(path):
                    _write(path, left)
        self.file.unlink(missing_ok=True)


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write(path: Path, text: str) -> None:
    """Writes `text` in one step, keeping an existing file's mode. A link, as a dotfiles
    manager makes ~/.bashrc, is written through, so it stays a link.
    """
    if path.is_symlink():
        path = path.resolve()
    if path.exists() and _text(path) == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tuxtoys-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    log.info("written: %s", path)
