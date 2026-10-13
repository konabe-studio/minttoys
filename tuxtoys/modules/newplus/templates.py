"""The templates folder Nemo offers under Create New Document, and what is in it. Free of
GTK.

The folder is the user's XDG templates directory, from ~/.config/user-dirs.dirs as
xdg-user-dir reads it: ~/Templates in English, ~/Sablonok in Hungarian, and so on. Set to
the home folder itself, it means no templates folder, as the XDG spec has it.
"""

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

_LINE = re.compile(r'^\s*XDG_TEMPLATES_DIR\s*=\s*"(.*)"\s*$')


class TemplateNameError(ValueError):
    """A template name that cannot be used. The subclass says why."""


class EmptyName(TemplateNameError):
    pass


class BadName(TemplateNameError):
    """A slash in it, or "." or "..": not the name of a file in the folder."""


class TakenName(TemplateNameError):
    pass


@dataclass(frozen=True)
class Template:
    name: str
    path: Path
    folder: bool


def templates_dir(home: Path, config_home: Path) -> Path | None:
    """The templates folder, or None when there is none set, or it is the home folder."""
    try:
        lines = (config_home / "user-dirs.dirs").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        match = _LINE.match(line)
        if match:
            value = match[1].replace("$HOME", str(home))
            path = Path(value) if os.path.isabs(value) else home / value
            return None if path == home else path
    return None


def templates(folder: Path) -> list[Template]:
    """What is in the folder, as Nemo offers it, hidden files left out, by name."""
    try:
        entries = [entry for entry in folder.iterdir() if not entry.name.startswith(".")]
    except OSError:
        return []
    found = [Template(entry.name, entry, entry.is_dir()) for entry in entries]
    return sorted(found, key=lambda template: template.name.casefold())


def free_name(folder: Path, name: str) -> str:
    """`name`, or "name (2).ext" and so on when it is taken in the folder."""
    if not (folder / name).exists():
        return name
    stem, dot, suffix = name.rpartition(".")
    if not stem or stem.endswith("."):
        stem, dot, suffix = name, "", ""
    number = 2
    while True:
        candidate = f"{stem} ({number}){dot}{suffix}"
        if not (folder / candidate).exists():
            return candidate
        number += 1


def add(folder: Path, source: Path) -> Path:
    """Copies a file or a folder into the templates folder, under a free name."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / free_name(folder, source.name)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)
    return target


def check_name(folder: Path, template: Template, name: str) -> str:
    """The new name for a template, trimmed; raises a TemplateNameError when it cannot be used."""
    name = name.strip()
    if not name:
        raise EmptyName(name)
    if "/" in name or name in (".", ".."):
        raise BadName(name)
    if name != template.name and (folder / name).exists():
        raise TakenName(name)
    return name
