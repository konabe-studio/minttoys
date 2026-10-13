"""The local time zone, with its daylight saving rules, and the time in it.

`datetime.now().astimezone()` would be simpler, but it gives a fixed offset, which is wrong
for any time on the other side of a clock change. "Until 08:00" set the evening before the
clocks go forward needs the rules.
"""

import os
from collections.abc import Mapping
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOCALTIME = Path("/etc/localtime")


def local_zone(environ: Mapping[str, str] = os.environ, localtime: Path = LOCALTIME) -> tzinfo:
    """The zone the system clock is set to, read fresh each time, so a zone changed in the
    system settings applies from the next call.

    TZ wins when it names a zone, as it does for every other program. Otherwise
    /etc/localtime decides: the name of the zone it links to, or the file itself when it is
    a copy. With neither, it is UTC, as for the C library.
    """
    key = environ.get("TZ", "").removeprefix(":")
    if key:
        try:
            return ZoneInfo(key)
        except (ZoneInfoNotFoundError, ValueError):
            pass  # a POSIX rule such as "CET-1CEST", or a zone that is not installed
    if localtime.is_symlink():
        parts = Path(os.readlink(localtime)).parts
        if "zoneinfo" in parts:
            try:
                return ZoneInfo("/".join(parts[parts.index("zoneinfo") + 1 :]))
            except (ZoneInfoNotFoundError, ValueError):
                pass
    try:
        with localtime.open("rb") as file:
            return ZoneInfo.from_file(file, key="localtime")
    except (OSError, ValueError):
        return UTC


def now() -> datetime:
    """The current time in the local zone, with its rules."""
    return datetime.now(local_zone())
