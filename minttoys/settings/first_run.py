"""Whether the settings window has been opened before, so that the Overview can greet a new
user once.

Kept apart from the daemon's config, in $XDG_STATE_HOME/minttoys/settings-window.ini: it
records what happened, not a choice, which is what the state directory is for.
"""

import configparser
import os
from collections.abc import Mapping
from pathlib import Path

SECTION = "window"


def state_file(environ: Mapping[str, str] = os.environ) -> Path:
    base = environ.get("XDG_STATE_HOME", "")
    # The XDG spec says to ignore a relative path.
    root = Path(base) if os.path.isabs(base) else Path.home() / ".local" / "state"
    return root / "minttoys" / "settings-window.ini"


def welcomed(path: Path) -> bool:
    """Whether the Overview has greeted the user already. An unreadable file counts as no,
    so the worst case is one greeting too many.
    """
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        return parser.getboolean(SECTION, "welcomed", fallback=False)
    except (configparser.Error, ValueError, OSError):
        return False


def mark_welcomed(path: Path) -> None:
    """Records the greeting. Raises OSError when the file cannot be written."""
    parser = configparser.ConfigParser()
    parser[SECTION] = {"welcomed": "true"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)
