"""When Awake's timed modes end, and how much time is left.

Pure functions with no GTK or D-Bus, so every edge case is tested directly.

Every instant is computed and returned in UTC. Python subtracts and compares two aware
datetimes that share a tzinfo by their clock fields alone, ignoring the offset, so across a
daylight saving change the result is off by the size of the shift: 01:00 to 04:00 on the
night the clocks go forward comes out as three hours, not two. Converting to UTC first
avoids that.

Local time matters only for "until HH:MM", which is about what the clock shows. That is
why `now` has to carry real time zone rules (a ZoneInfo), not a fixed UTC offset such as
the one `datetime.now().astimezone()` returns.
"""

import math
import re
from datetime import UTC, datetime, time, timedelta, tzinfo

_MINUTES = re.compile(r"([0-9]+)m?")
_HOURS_MINUTES = re.compile(r"([0-9]+)h(?:([0-9]+)m)?")
_CLOCK = re.compile(r"([0-9]{1,2}):([0-9]{2})")


def end_after(now: datetime, duration: timedelta) -> datetime:
    """The instant `duration` of real time after `now`."""
    if duration <= timedelta(0):
        raise ValueError(f"duration must be positive, not {duration}")
    try:
        return _utc(now) + duration
    except OverflowError as error:
        raise ValueError(f"duration too long: {duration}") from error


def next_occurrence(now: datetime, target: time) -> datetime:
    """The first instant after `now` at which the local clock reaches `target`.

    A target at or before the current time of day means tomorrow, so 01:00 set at 23:00
    ends two hours later, and 18:00 set at 18:00 a day later.

    Daylight saving changes follow the clock as well. A time the clocks go back over comes
    twice: the first is taken, or the second when the first has already passed. A time the
    clocks jump over never shows, so it ends at the jump, the first moment the clock is
    past it.
    """
    start = _utc(now)
    zone = now.tzinfo
    assert zone is not None  # _utc() refuses a naive now
    for days in range(3):
        wall = datetime.combine(now.date() + timedelta(days=days), target)
        for instant in _crossings(wall, zone):
            if instant > start:
                return instant
    # Unreachable: the clock reaches every time of day within two days, even where a whole
    # day was skipped (Samoa, 2011).
    raise AssertionError(f"no {target} after {now}")


def remaining(now: datetime, end: datetime) -> timedelta:
    """Real time left from `now` to `end`, zero once `end` has passed."""
    return max(_utc(end) - _utc(now), timedelta(0))


def minutes_left(now: datetime, end: datetime) -> int:
    """Whole minutes left, rounded up, so the last minute shows as 1 and not 0."""
    return math.ceil(remaining(now, end) / timedelta(minutes=1))


def parse_duration(text: str) -> timedelta:
    """Reads a duration as the command line takes it: "90" or "90m", "2h", "1h30m"."""
    compact = "".join(text.split()).lower()
    if match := _MINUTES.fullmatch(compact):
        minutes = int(match[1])
    elif match := _HOURS_MINUTES.fullmatch(compact):
        minutes = int(match[1]) * 60 + int(match[2] or 0)
    else:
        raise ValueError(f"not a duration: {text!r}")
    if minutes == 0:
        raise ValueError(f"duration must be positive, not {text!r}")
    try:
        return timedelta(minutes=minutes)
    except OverflowError as error:
        raise ValueError(f"duration too long: {text!r}") from error


def parse_clock_time(text: str) -> time:
    """Reads a time of day as "18:00" or "8:05"."""
    match = _CLOCK.fullmatch(text.strip())
    if not match:
        raise ValueError(f"not a time of day: {text!r}")
    hour, minute = int(match[1]), int(match[2])
    if hour > 23 or minute > 59:
        raise ValueError(f"not a time of day: {text!r}")
    return time(hour, minute)


def _utc(moment: datetime) -> datetime:
    if moment.utcoffset() is None:
        raise ValueError(f"needs a timezone-aware datetime, not {moment}")
    return moment.astimezone(UTC)


def _wall(instant: datetime, zone: tzinfo) -> datetime:
    """What the clock in `zone` shows at `instant`, as a naive datetime."""
    return instant.astimezone(zone).replace(tzinfo=None)


def _crossings(wall: datetime, zone: tzinfo) -> list[datetime]:
    """Every instant at which the clock in `zone` reaches the naive time `wall`, in order."""
    # For a time shown twice, fold=0 is its first occurrence and fold=1 its second. For a
    # time that is skipped, fold=0 reads it with the offset from before the jump, which
    # lands after the jump, and fold=1 the other way round.
    first = wall.replace(tzinfo=zone, fold=0).astimezone(UTC)
    second = wall.replace(tzinfo=zone, fold=1).astimezone(UTC)
    if first == second:
        return [first]
    if _wall(first, zone) == wall:
        return [first, second]
    return [_jump(second, first, zone, wall)]


def _jump(before: datetime, after: datetime, zone: tzinfo, wall: datetime) -> datetime:
    """The moment the clock in `zone` jumps past `wall`, which lies between the two.

    Clocks change on a whole second, so bisecting over whole seconds lands on it exactly.
    The jump is usually an hour, but not everywhere (Lord Howe Island moves by 30 minutes),
    so it is searched for rather than assumed.
    """
    low, high = math.floor(before.timestamp()), math.ceil(after.timestamp())
    while high - low > 1:
        middle = (low + high) // 2
        if _wall(datetime.fromtimestamp(middle, UTC), zone) >= wall:
            high = middle
        else:
            low = middle
    return datetime.fromtimestamp(high, UTC)
