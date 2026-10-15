"""Saves /etc/environment as root: the one thing Environment Variables needs administrator
rights for. pkexec runs it, as /usr/libexec/tuxtoys/tuxtoys-environment-save, after
polkit's io.github.konabe_studio.TuxToys.environment.save has let the user through. How
it saves, and what it refuses, is in tuxtoys.core.rootfile; this file only names
/etc/environment.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from tuxtoys.core import rootfile
from tuxtoys.core.rootfile import BACKUPS

ENVIRONMENT = Path("/etc/environment")
MOST_BYTES = 256_000


def save(
    argv: list[str],
    stdin: BinaryIO,
    environment: Path = ENVIRONMENT,
    backups: Path = BACKUPS,
    now: datetime | None = None,
) -> tuple[int, str]:
    target = rootfile.Target(environment, "environment-", MOST_BYTES, "tuxtoys-environment-save")
    return rootfile.save(argv, stdin, target, backups, now)


def main() -> int:
    status, reason = save(sys.argv[1:], sys.stdin.buffer)
    if reason:
        print(reason, file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
