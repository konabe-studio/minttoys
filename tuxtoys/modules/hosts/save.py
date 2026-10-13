"""Saves /etc/hosts as root: the one thing Hosts File Editor needs administrator rights
for. pkexec runs it, as /usr/libexec/tuxtoys/tuxtoys-hosts-save, after polkit's
io.github.konabe_studio.TuxToys.hosts.save has let the user through.

It runs as root, so it does little and trusts nothing: it takes only the new content, on
standard input, and its options; writes /etc/hosts and nothing else but backups in
/var/backups/tuxtoys; and imports nothing outside the standard library and this package's
backups module.

- The content must be UTF-8 text without NUL, at most MOST_BYTES.
- --expect is the SHA-256 of /etc/hosts as the editor read it. If the file has changed
  since, nothing is written, so a change made elsewhere is never lost.
- --backup copies the file as it is into /var/backups/tuxtoys first, then deletes old
  backups by --keep (never, count, age), --count and --days.
- The new file goes in beside the old one under a hidden name, with the old one's owner
  and mode, is flushed to disk, and then takes its place in one step. Neither /etc/hosts
  nor the backups folder is ever followed through a symbolic link.

Exit status: 0 saved, 2 bad options or content, 3 changed since it was read, 4 could
not be saved (the reason on standard error, in English). pkexec itself exits 126 when
the password dialog is dismissed and 127 when not authorized.
"""

import argparse
import hashlib
import os
import secrets
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from tuxtoys.modules.hosts.backups import KEEPS, backup_name, to_delete

HOSTS = Path("/etc/hosts")
BACKUPS = Path("/var/backups/tuxtoys")
MOST_BYTES = 1_000_000
SAVED, BAD, CHANGED, FAILED = 0, 2, 3, 4
# Never through a symbolic link; and on Windows, where the tests also run, bytes as they are.
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)


class _Refused(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status


def _options(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tuxtoys-hosts-save", exit_on_error=False)
    parser.add_argument("--expect", required=True)
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--keep", choices=KEEPS, default="age")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--days", type=int, default=15)
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise _Refused(BAD, f"bad options: {error}") from None
    if len(options.expect) != 64 or any(c not in "0123456789abcdef" for c in options.expect):
        raise _Refused(BAD, "--expect is a SHA-256 in hex")
    if not 0 <= options.count <= 1000 or not 0 <= options.days <= 3650:
        raise _Refused(BAD, "--count is 0 to 1000 and --days 0 to 3650")
    return options


def _content(stdin: BinaryIO) -> bytes:
    content = stdin.read(MOST_BYTES + 1)
    if len(content) > MOST_BYTES:
        raise _Refused(BAD, f"the content is over {MOST_BYTES} bytes")
    if b"\0" in content:
        raise _Refused(BAD, "the content holds a NUL byte")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        raise _Refused(BAD, "the content is not UTF-8") from None
    return content


def _read(hosts: Path) -> tuple[bytes, os.stat_result]:
    status = os.lstat(hosts)
    if not stat.S_ISREG(status.st_mode):
        raise _Refused(FAILED, f"{hosts} is not a plain file")
    descriptor = os.open(hosts, os.O_RDONLY | _NOFOLLOW)
    with os.fdopen(descriptor, "rb") as file:
        return file.read(), status


def _create(path: Path, mode: int) -> int:
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, mode)


def _back_up(content: bytes, backups: Path, now: datetime, options: argparse.Namespace) -> None:
    if not os.path.lexists(backups):
        os.mkdir(backups, 0o755)
    if not stat.S_ISDIR(os.lstat(backups).st_mode):
        raise _Refused(FAILED, f"{backups} is not a folder")
    name = backup_name(now)
    number = 1
    while True:
        candidate = backups / (name if number == 1 else f"{name}-{number}")
        try:
            descriptor = _create(candidate, 0o644)
            break
        except FileExistsError:
            number += 1
    with os.fdopen(descriptor, "wb") as file:
        file.write(content)
    for old in to_delete(os.listdir(backups), options.keep, options.count, options.days, now):
        path = backups / old
        if stat.S_ISREG(os.lstat(path).st_mode):
            path.unlink()


def _replace(hosts: Path, content: bytes, status: os.stat_result) -> None:
    temporary = hosts.with_name(f".{hosts.name}.tuxtoys-{secrets.token_hex(6)}")
    descriptor = _create(temporary, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as file:
            if hasattr(os, "fchown"):
                os.fchown(file.fileno(), status.st_uid, status.st_gid)
            if hasattr(os, "fchmod"):
                os.fchmod(file.fileno(), stat.S_IMODE(status.st_mode))
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, hosts)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if hasattr(os, "O_DIRECTORY"):
        folder = os.open(hosts.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)


def save(
    argv: list[str],
    stdin: BinaryIO,
    hosts: Path = HOSTS,
    backups: Path = BACKUPS,
    now: datetime | None = None,
) -> tuple[int, str]:
    """Does it all; the exit status and, when not saved, why."""
    try:
        options = _options(argv)
        content = _content(stdin)
        current, status = _read(hosts)
        if hashlib.sha256(current).hexdigest() != options.expect:
            raise _Refused(CHANGED, f"{hosts} has changed since it was read")
        if options.backup:
            _back_up(current, backups, now or datetime.now(UTC), options)
        _replace(hosts, content, status)
    except _Refused as refused:
        return refused.status, str(refused)
    except OSError as error:
        return FAILED, f"{error.filename or hosts}: {error.strerror or error}"
    return SAVED, ""


def main() -> int:
    status, reason = save(sys.argv[1:], sys.stdin.buffer)
    if reason:
        print(reason, file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
