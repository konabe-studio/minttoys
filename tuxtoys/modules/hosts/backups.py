"""Which backups of the hosts file to keep, as PowerToys has it: never delete any, keep a
number of the newest, or delete those older than some days but always keep a number of
the newest. Free of the file system.

A backup is named after the moment it was made, "hosts-20261013-153000", so the names
sort by age.
"""

import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

KEEPS = ("never", "count", "age")
PREFIX = "hosts-"
_NAME = re.compile(r"hosts-(\d{8}-\d{6})(?:-\d+)?")
_STAMP = "%Y%m%d-%H%M%S"


def backup_name(now: datetime) -> str:
    """The name of a backup made at `now`, in UTC so a change of clocks cannot reorder."""
    return PREFIX + now.astimezone(UTC).strftime(_STAMP)


def made_at(name: str) -> datetime | None:
    found = _NAME.fullmatch(name)
    if not found:
        return None
    return datetime.strptime(found[1], _STAMP).replace(tzinfo=UTC)


def to_delete(names: Iterable[str], keep: str, count: int, days: int, now: datetime) -> list[str]:
    """The backups among `names` to delete; names that are not backups are left alone."""
    if keep == "never":
        return []
    dated = sorted(
        ((when, name) for name in names if (when := made_at(name)) is not None),
        reverse=True,
    )
    older = dated[max(count, 0) :]
    if keep == "count":
        return [name for _when, name in older]
    cutoff = now.astimezone(UTC) - timedelta(days=days)
    return [name for when, name in older if when < cutoff]
