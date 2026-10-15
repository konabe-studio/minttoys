"""Saves /etc/hosts as root: the one thing Hosts File Editor needs administrator rights
for. pkexec runs it, as /usr/libexec/tuxtoys/tuxtoys-hosts-save, after polkit's
io.github.konabe_studio.TuxToys.hosts.save has let the user through. How it saves, and
what it refuses, is in tuxtoys.core.rootfile; this file only names /etc/hosts.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from tuxtoys.core import rootfile
from tuxtoys.core.rootfile import BACKUPS, BAD, CHANGED, FAILED, SAVED

HOSTS = Path("/etc/hosts")
MOST_BYTES = 1_000_000

__all__ = ["BAD", "CHANGED", "FAILED", "HOSTS", "MOST_BYTES", "SAVED", "main", "save"]


def save(
    argv: list[str],
    stdin: BinaryIO,
    hosts: Path = HOSTS,
    backups: Path = BACKUPS,
    now: datetime | None = None,
) -> tuple[int, str]:
    target = rootfile.Target(hosts, "hosts-", MOST_BYTES, "tuxtoys-hosts-save")
    return rootfile.save(argv, stdin, target, backups, now)


def main() -> int:
    status, reason = save(sys.argv[1:], sys.stdin.buffer)
    if reason:
        print(reason, file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
