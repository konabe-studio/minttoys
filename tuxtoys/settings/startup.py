"""Whether the panel icon starts with the session. Free of GTK.

The package starts it from /etc/xdg/autostart. A file of the same name in the user's
~/.config/autostart takes its place, as the XDG autostart rules have it, and that is how
Cinnamon's Startup Applications switches an entry off: it writes a copy with
X-GNOME-Autostart-enabled=false. The General page does the same, so either one shows
what the other did. Switching the icon back on removes the copy if TuxToys wrote it, and
otherwise sets the key back, leaving the rest of the user's copy as it is.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from tuxtoys import APP_ID

ENTRY = f"{APP_ID}.Tray.desktop"
SYSTEM_ENTRY = Path("/etc/xdg/autostart") / ENTRY
MARK = "# Written by TuxToys: the panel icon does not start with the session."
_ENABLED = "X-GNOME-Autostart-enabled"


def autostart_dir(environ: Mapping[str, str] = os.environ) -> Path:
    config_home = environ.get("XDG_CONFIG_HOME", "")
    root = Path(config_home) if os.path.isabs(config_home) else Path.home() / ".config"
    return root / "autostart"


def _keys(text: str) -> dict[str, str]:
    keys = {}
    for line in text.splitlines():
        key, equals, value = line.partition("=")
        if equals:
            keys[key.strip()] = value.strip()
    return keys


def starts(folder: Path) -> bool:
    """Whether the panel icon starts with the next session."""
    path = folder / ENTRY
    if not path.exists():
        return True
    keys = _keys(path.read_text(encoding="utf-8", errors="replace"))
    return keys.get(_ENABLED, "true").lower() != "false" and keys.get("Hidden", "") != "true"


def set_starts(folder: Path, enabled: bool, system_entry: Path = SYSTEM_ENTRY) -> None:
    path = folder / ENTRY
    if enabled:
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.startswith(MARK):
            path.unlink()
            return
        lines = [
            f"{_ENABLED}=true" if line.startswith(f"{_ENABLED}=") else line
            for line in text.splitlines()
            if not line.startswith("Hidden=")
        ]
        _write(path, "\n".join(lines) + "\n")
        return
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in text.splitlines() if not line.startswith(f"{_ENABLED}=")]
        _write(path, "\n".join([*lines, f"{_ENABLED}=false"]) + "\n")
        return
    try:
        base = system_entry.read_text(encoding="utf-8").splitlines()
    except OSError:
        base = ["[Desktop Entry]", "Type=Application", "Name=TuxToys panel icon"]
    lines = [line for line in base if not line.startswith(f"{_ENABLED}=")]
    _write(path, "\n".join([MARK, *lines, f"{_ENABLED}=false"]) + "\n")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
