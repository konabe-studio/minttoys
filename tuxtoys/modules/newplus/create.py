"""Making a file or a folder from a template, in the folder Nemo shows. Free of GTK.

Nothing is ever overwritten: the copy is made under a hidden name in the target folder
first, then given its name in one step, which fails when the name is taken by then. A
folder template is copied whole, and with variables on, the names inside it are replaced
too, $PARENT_FOLDER_NAME by the name of the folder each one ends up in.
"""

import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tuxtoys.modules.newplus.names import expand, order_key, without_leading_digits
from tuxtoys.modules.newplus.templates import BadName, EmptyName, TakenName, Template

_HIDDEN = ".tuxtoys-new-"


@dataclass(frozen=True)
class Naming:
    """How New+ names what it makes: its two settings, the time and the environment."""

    variables: bool = False
    hide_digits: bool = False
    now: datetime | None = None
    environ: Mapping[str, str] | None = None

    def shown(self, template: Template) -> str:
        """The template's name in the list."""
        if self.hide_digits:
            return without_leading_digits(template.name, template.folder)
        return template.name

    def offered(self, template: Template, target: Path) -> str:
        """The name offered for an item made from the template in `target`."""
        return self.expand(self.shown(template), target.name)

    def expand(self, name: str, parent: str) -> str:
        """`name` with its variables replaced, when that is on; `parent` names the folder
        the item lands in.
        """
        if not self.variables:
            return name
        now = self.now or datetime.now().astimezone()
        return expand(name, now, parent, os.environ if self.environ is None else self.environ)


def ordered(found: list[Template]) -> list[Template]:
    """Folders first, then by name, numbers by their value: the digits a name starts with
    order it even when they are not shown."""
    return sorted(found, key=lambda template: order_key(template.name, template.folder))


def check(target: Path, name: str) -> str:
    """The name, trimmed; raises a TemplateNameError when it cannot be used in `target`."""
    name = name.strip()
    if not name:
        raise EmptyName(name)
    if "/" in name or "\0" in name or name in (".", ".."):
        raise BadName(name)
    if (target / name).exists() or (target / name).is_symlink():
        raise TakenName(name)
    return name


def make(template: Template, target: Path, name: str, naming: Naming) -> Path:
    """Makes the item and returns its path. A TemplateNameError for a name that cannot be
    used, OSError for anything else.
    """
    name = check(target, name)
    final = target / name
    if template.folder:
        temporary = Path(tempfile.mkdtemp(dir=target, prefix=_HIDDEN))
        try:
            shutil.copytree(template.path, temporary, symlinks=True, dirs_exist_ok=True)
            if naming.variables:
                _expand_inside(temporary, name, naming)
            if final.exists() or final.is_symlink():
                raise TakenName(name)
            os.rename(temporary, final)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return final

    handle, temporary_name = tempfile.mkstemp(dir=target, prefix=_HIDDEN)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(template.path, temporary)
        _place(temporary, final)
    finally:
        temporary.unlink(missing_ok=True)
    return final


def _place(temporary: Path, final: Path) -> None:
    """Gives the copied file its name, unless that is taken."""
    try:
        os.link(temporary, final)
    except FileExistsError:
        raise TakenName(final.name) from None
    except OSError:
        # A file system without hard links: check, then rename.
        if final.exists() or final.is_symlink():
            raise TakenName(final.name) from None
        os.rename(temporary, final)


def _expand_inside(root: Path, root_name: str, naming: Naming) -> None:
    """Replaces the variables in every name inside a copied folder, top down, so each
    item sees the final name of the folder it is in. A name that would clash with another
    in the same folder stays as it was.
    """
    for folder, folders, files in os.walk(root):
        parent = root_name if Path(folder) == root else os.path.basename(folder)
        for index, entry in enumerate(folders):
            folders[index] = _rename(Path(folder), entry, parent, naming)
        for entry in files:
            _rename(Path(folder), entry, parent, naming)


def _rename(folder: Path, entry: str, parent: str, naming: Naming) -> str:
    new = naming.expand(entry, parent)
    if new == entry or new in (".", "..") or not new.strip():
        return entry
    if (folder / new).exists() or (folder / new).is_symlink():
        return entry
    os.rename(folder / entry, folder / new)
    return new
