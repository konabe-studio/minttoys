"""Which processes hold some files or folders, read from /proc. Free of GTK and D-Bus.

A process holds a path when one of its open files is that file, or lies inside that folder,
or when it works in it (its current directory, which keeps a USB stick from being
unmounted). Only the user's own processes can be looked at without administrator rights;
for the others, /proc does not show what they hold.
"""

import os
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")


@dataclass(frozen=True)
class Holder:
    pid: int
    name: str
    # What of the selection it holds, as absolute paths.
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Scan:
    holders: list[Holder]
    # Whether some processes could not be looked at, as other users' cannot.
    some_hidden: bool


def scan(targets: Iterable[str], proc: Path = PROC, skip: int | None = None) -> Scan:
    """The processes holding any of `targets`, by name and then PID. `skip` is a PID to
    leave out, the caller's own.
    """
    wanted = [_Target.of(target) for target in targets]
    holders = []
    some_hidden = False
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == skip:
            continue
        opened, hidden = _opened(entry)
        some_hidden = some_hidden or hidden
        held = sorted({path for path in opened if any(t.holds(path) for t in wanted)})
        if held:
            holders.append(Holder(int(entry.name), _name(entry), tuple(held)))
    holders.sort(key=lambda holder: (holder.name.lower(), holder.pid))
    return Scan(holders, some_hidden)


@dataclass(frozen=True)
class _Target:
    path: str
    folder: bool

    @classmethod
    def of(cls, target: str) -> "_Target":
        path = os.path.realpath(target)
        return cls(path, os.path.isdir(path))

    def holds(self, path: str) -> bool:
        if path == self.path:
            return True
        return self.folder and path.startswith(self.path.rstrip("/") + "/")


def _opened(entry: Path) -> tuple[list[str], bool]:
    """The paths a process has open, and its current directory; and whether /proc kept
    them from us. Sockets, pipes and deleted files have no path to match, so they are left
    out.
    """
    paths = []
    hidden = False
    try:
        for fd in (entry / "fd").iterdir():
            try:
                paths.append(os.readlink(fd))
            except OSError:
                continue  # closed while being read
    except PermissionError:
        hidden = True
    except OSError:
        return [], False  # the process ended
    with suppress(OSError):
        paths.append(os.readlink(entry / "cwd"))
    return [
        path for path in paths if path.startswith("/") and not path.endswith(" (deleted)")
    ], hidden


def _name(entry: Path) -> str:
    try:
        return (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return entry.name
