"""The configuration file, ~/.config/minttoys/config.json.

Each module keeps its settings in a section of its own, under its id in "modules". Keys
this version does not know are kept as they are, so what a newer MintToys wrote survives a
save by an older one.
"""

import contextlib
import json
import logging
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def default_path() -> Path:
    """Where the file lives, by the XDG base directory spec."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", ""))
    # The spec says a relative path is to be ignored, the same as an unset one.
    root = base if base.is_absolute() else Path.home() / ".config"
    return root / "minttoys" / "config.json"


class Config:
    """The file's contents. Only the parts MintToys reads are interpreted."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data if data is not None else {}

    def module(self, module_id: str) -> dict[str, Any]:
        """A copy of one module's settings, empty when there are none."""
        modules = self._data.get("modules")
        section = modules.get(module_id) if isinstance(modules, dict) else None
        return dict(section) if isinstance(section, dict) else {}

    def set_module(self, module_id: str, settings: Mapping[str, Any]) -> None:
        """Replaces one module's settings."""
        modules = self._data.get("modules")
        if not isinstance(modules, dict):
            modules = self._data["modules"] = {}
        modules[module_id] = dict(settings)

    def to_json(self) -> str:
        return json.dumps(self._data, indent=2, ensure_ascii=False) + "\n"


def load(path: Path) -> Config:
    """Reads the file. A missing file is an empty config.

    A file that is not a JSON object is moved aside to config.json.broken, where the user
    can still get at it, and MintToys starts from its defaults rather than not at all. The
    next save would otherwise overwrite it.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Config()
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:  # UnicodeDecodeError is one too
        data = None
    if isinstance(data, dict):
        return Config(data)
    broken = path.with_name(path.name + ".broken")
    path.replace(broken)
    log.warning("%s could not be read, moved it to %s and started from defaults", path, broken)
    return Config()


def save(config: Config, path: Path) -> None:
    """Writes the file atomically: a temporary file next to it, then a rename.

    A crash, a full disk or a power cut halfway through leaves the previous file whole
    instead of half written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(config.to_json())
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise
