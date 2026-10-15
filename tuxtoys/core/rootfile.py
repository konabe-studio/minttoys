"""Saving one system file as root, for a helper pkexec runs: Hosts File Editor's for
/etc/hosts, Environment Variables' for /etc/environment. Each helper names its one file
here and nothing else, so no command line can make it write another.

It runs as root, so it does little and trusts nothing: it takes only the new content, on
standard input, and its options; writes its file and nothing else but backups in
/var/backups/tuxtoys; and imports nothing outside the standard library and this package's
backup rules.

- The content must be UTF-8 text without NUL, within the helper's size limit.
- --expect is the SHA-256 of the file as the editor read it. If the file has changed
  since, nothing is written, so a change made elsewhere is never lost.
- --backup copies the file as it is into /var/backups/tuxtoys first, then deletes that
  file's old backups by --keep (never, count, age), --count and --days.
- The new file goes in beside the old one under a hidden name, with the old one's owner
  and mode, is flushed to disk, and then takes its place in one step. Neither the file
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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from tuxtoys.core.backups import KEEPS, backup_name, to_delete

BACKUPS = Path("/var/backups/tuxtoys")
SAVED, BAD, CHANGED, FAILED = 0, 2, 3, 4
# Never through a symbolic link; and on Windows, where the tests also run, bytes as they are.
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)


@dataclass(frozen=True)
class Target:
    """The one file a helper writes."""

    path: Path
    prefix: str  # of its backups' names, "hosts-"
    most_bytes: int
    program: str  # the helper's name, for its usage line


class _Refused(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status


def _options(argv: list[str], program: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=program, exit_on_error=False)
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


def _content(stdin: BinaryIO, most_bytes: int) -> bytes:
    content = stdin.read(most_bytes + 1)
    if len(content) > most_bytes:
        raise _Refused(BAD, f"the content is over {most_bytes} bytes")
    if b"\0" in content:
        raise _Refused(BAD, "the content holds a NUL byte")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        raise _Refused(BAD, "the content is not UTF-8") from None
    return content


def _read(path: Path) -> tuple[bytes, os.stat_result]:
    status = os.lstat(path)
    if not stat.S_ISREG(status.st_mode):
        raise _Refused(FAILED, f"{path} is not a plain file")
    descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    with os.fdopen(descriptor, "rb") as file:
        return file.read(), status


def _create(path: Path, mode: int) -> int:
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, mode)


def _back_up(
    content: bytes, backups: Path, prefix: str, now: datetime, options: argparse.Namespace
) -> None:
    if not os.path.lexists(backups):
        os.mkdir(backups, 0o755)
    if not stat.S_ISDIR(os.lstat(backups).st_mode):
        raise _Refused(FAILED, f"{backups} is not a folder")
    name = backup_name(now, prefix)
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
    old = to_delete(os.listdir(backups), options.keep, options.count, options.days, now, prefix)
    for name in old:
        path = backups / name
        if stat.S_ISREG(os.lstat(path).st_mode):
            path.unlink()


def _replace(path: Path, content: bytes, status: os.stat_result) -> None:
    temporary = path.with_name(f".{path.name}.tuxtoys-{secrets.token_hex(6)}")
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
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if hasattr(os, "O_DIRECTORY"):
        folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)


def save(
    argv: list[str],
    stdin: BinaryIO,
    target: Target,
    backups: Path = BACKUPS,
    now: datetime | None = None,
) -> tuple[int, str]:
    """Does it all; the exit status and, when not saved, why."""
    try:
        options = _options(argv, target.program)
        content = _content(stdin, target.most_bytes)
        current, status = _read(target.path)
        if hashlib.sha256(current).hexdigest() != options.expect:
            raise _Refused(CHANGED, f"{target.path} has changed since it was read")
        if options.backup:
            _back_up(current, backups, target.prefix, now or datetime.now(UTC), options)
        _replace(target.path, content, status)
    except _Refused as refused:
        return refused.status, str(refused)
    except OSError as error:
        return FAILED, f"{error.filename or target.path}: {error.strerror or error}"
    return SAVED, ""
