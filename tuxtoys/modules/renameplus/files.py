"""Rename+ on the file system: the items under the chosen ones, and the renaming. Free of
GTK.

Renaming goes from the deepest items up, so a folder is renamed after what is inside it
and every path still holds when its turn comes. Each level goes in two steps: every item
to a hidden name of its own first, then to its new name. That lets names be swapped
("a" to "b" and "b" to "a") and the case of a name be changed on a file system that
ignores case. A name that is taken when its turn comes is never written over: the item
goes back to its old name and is reported.
"""

import os
import secrets
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tuxtoys.core.clock import local_zone
from tuxtoys.modules.newplus.names import order_key
from tuxtoys.modules.renameplus.plan import Item

# Past this many, what is inside the chosen folders is left out of the list.
MOST_ITEMS = 10_000


def file_time(path: Path) -> datetime | None:
    """When the item was made, where the file system keeps it, else when it was last
    changed; None when it cannot be read.
    """
    try:
        status = path.lstat()
    except OSError:
        return None
    stamp = getattr(status, "st_birthtime", None) or status.st_mtime
    return datetime.fromtimestamp(stamp, local_zone())


def gather(
    chosen: Iterable[Path],
    when: Callable[[Path], datetime | None] = file_time,
    most: int = MOST_ITEMS,
) -> tuple[list[Item], bool]:
    """The chosen items in name order, each folder followed by what is inside it, all
    the way down, also in name order; and whether some were left out past `most`.
    A link to a folder is an item, not a folder to go into.
    """
    items: list[Item] = []
    cut = False

    def add(path: Path, depth: int) -> None:
        nonlocal cut
        if len(items) >= most:
            cut = True
            return
        is_folder = path.is_dir() and not path.is_symlink()
        items.append(Item(str(path.parent), path.name, is_folder, depth, when(path)))
        if not is_folder:
            return
        try:
            inside = list(path.iterdir())
        except OSError:
            return
        for child in _sorted(inside):
            add(child, depth + 1)

    for path in _sorted(chosen):
        add(path, 0)
    return items, cut


def _sorted(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: order_key(path.name, _is_folder(path)))


def _is_folder(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def taken(folder: str, name: str, own: str) -> bool:
    """Whether `name` in `folder` is in use by something other than the item `own`, which
    it may be on a file system that ignores case.
    """
    target = Path(folder, name)
    if not os.path.lexists(target):
        return False
    try:
        return not os.path.samefile(target, Path(folder, own))
    except OSError:
        return True


@dataclass(frozen=True)
class Move:
    folder: str
    old: str
    new: str
    depth: int


@dataclass(frozen=True)
class Failure:
    folder: str
    name: str
    reason: str = ""  # the system's words; empty when the new name was taken
    left_as: str = ""  # the hidden name it is stuck at, when it could not go back either


def rename_all(moves: Sequence[Move]) -> tuple[list[Move], list[Failure]]:
    """Renames, deepest first. What was renamed, and what was not with why."""
    done: list[Move] = []
    failed: list[Failure] = []
    for depth in sorted({move.depth for move in moves}, reverse=True):
        level = [move for move in moves if move.depth == depth]
        parked: list[tuple[Move, str]] = []
        for move in level:
            hidden = _hidden_name(move.folder)
            try:
                os.rename(Path(move.folder, move.old), Path(move.folder, hidden))
            except OSError as error:
                failed.append(Failure(move.folder, move.old, error.strerror or str(error)))
                continue
            parked.append((move, hidden))
        for move, hidden in parked:
            failure = _settle(move, hidden)
            if failure:
                failed.append(failure)
            else:
                done.append(move)
    return done, failed


def _settle(move: Move, hidden: str) -> Failure | None:
    """Moves a parked item to its new name, or back to its old one when it cannot."""
    folder = Path(move.folder)
    reason = ""
    if not os.path.lexists(folder / move.new):
        try:
            os.rename(folder / hidden, folder / move.new)
            return None
        except OSError as error:
            reason = error.strerror or str(error)
    try:
        os.rename(folder / hidden, folder / move.old)
    except OSError as error:
        return Failure(move.folder, move.old, reason or error.strerror or str(error), hidden)
    return Failure(move.folder, move.old, reason)


def _hidden_name(folder: str) -> str:
    while True:
        name = f".tuxtoys-rename-{secrets.token_hex(6)}"
        if not os.path.lexists(Path(folder, name)):
            return name
