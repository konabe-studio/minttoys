from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.awake.timer import (
    end_after,
    minutes_left,
    next_occurrence,
    parse_clock_time,
    parse_duration,
    remaining,
)

# In 2026 Budapest's clocks jump from 02:00 to 03:00 on 29 March, and go back from 03:00 to
# 02:00 on 25 October, so 02:30 does not exist on the first night and comes twice on the
# second.
BUDAPEST = ZoneInfo("Europe/Budapest")
# Lord Howe Island moves its clocks by 30 minutes: from 02:00 to 02:30 on 4 October 2026.
LORD_HOWE = ZoneInfo("Australia/Lord_Howe")


def budapest(*fields: int, fold: int = 0) -> datetime:
    return datetime(*fields, tzinfo=BUDAPEST, fold=fold)


def shown(instant: datetime, zone: ZoneInfo = BUDAPEST) -> str:
    """What the clock shows at `instant`, with the offset, so both are checked at once."""
    return instant.astimezone(zone).isoformat()


class TestEndAfter:
    def test_adds_the_duration(self) -> None:
        end = end_after(budapest(2026, 6, 1, 10, 0), timedelta(minutes=90))
        assert shown(end) == "2026-06-01T11:30:00+02:00"

    def test_returns_utc(self) -> None:
        assert end_after(budapest(2026, 6, 1, 10, 0), timedelta(hours=1)).tzinfo is UTC

    def test_counts_real_time_when_the_clocks_go_forward(self) -> None:
        end = end_after(budapest(2026, 3, 29, 1, 0), timedelta(hours=2))
        assert shown(end) == "2026-03-29T04:00:00+02:00"

    def test_counts_real_time_when_the_clocks_go_back(self) -> None:
        end = end_after(budapest(2026, 10, 25, 1, 30), timedelta(hours=2))
        assert shown(end) == "2026-10-25T02:30:00+01:00"

    @pytest.mark.parametrize("duration", [timedelta(0), timedelta(minutes=-5)])
    def test_refuses_a_duration_that_is_not_positive(self, duration: timedelta) -> None:
        with pytest.raises(ValueError, match="positive"):
            end_after(budapest(2026, 6, 1, 10, 0), duration)

    def test_refuses_a_duration_past_the_calendar(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            end_after(budapest(2026, 6, 1, 10, 0), timedelta.max)

    def test_refuses_a_naive_now(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            end_after(budapest(2026, 6, 1, 10, 0).replace(tzinfo=None), timedelta(hours=1))


class TestNextOccurrence:
    def test_later_today(self) -> None:
        end = next_occurrence(budapest(2026, 6, 1, 10, 0), time(18, 0))
        assert shown(end) == "2026-06-01T18:00:00+02:00"

    def test_returns_utc(self) -> None:
        assert next_occurrence(budapest(2026, 6, 1, 10, 0), time(18, 0)).tzinfo is UTC

    def test_past_midnight(self) -> None:
        end = next_occurrence(budapest(2026, 6, 1, 23, 0), time(1, 0))
        assert shown(end) == "2026-06-02T01:00:00+02:00"

    def test_into_the_next_year(self) -> None:
        end = next_occurrence(budapest(2026, 12, 31, 23, 30), time(0, 15))
        assert shown(end) == "2027-01-01T00:15:00+01:00"

    def test_the_current_time_means_tomorrow(self) -> None:
        end = next_occurrence(budapest(2026, 6, 1, 18, 0), time(18, 0))
        assert shown(end) == "2026-06-02T18:00:00+02:00"

    def test_seconds_before_means_today(self) -> None:
        end = next_occurrence(budapest(2026, 6, 1, 17, 59, 30), time(18, 0))
        assert shown(end) == "2026-06-01T18:00:00+02:00"

    def test_refuses_a_naive_now(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            next_occurrence(budapest(2026, 6, 1, 10, 0).replace(tzinfo=None), time(18, 0))

    # The night the clocks go forward.

    @pytest.mark.parametrize("target", [time(2, 0), time(2, 30), time(2, 59)])
    def test_a_skipped_time_ends_at_the_jump(self, target: time) -> None:
        end = next_occurrence(budapest(2026, 3, 29, 1, 0), target)
        assert shown(end) == "2026-03-29T03:00:00+02:00"
        assert shown(end - timedelta(seconds=1)) == "2026-03-29T01:59:59+01:00"

    def test_a_skipped_time_after_the_jump_means_tomorrow(self) -> None:
        end = next_occurrence(budapest(2026, 3, 29, 3, 10), time(2, 30))
        assert shown(end) == "2026-03-30T02:30:00+02:00"

    def test_a_time_after_the_jump(self) -> None:
        now = budapest(2026, 3, 29, 1, 0)
        end = next_occurrence(now, time(3, 30))
        assert shown(end) == "2026-03-29T03:30:00+02:00"
        assert minutes_left(now, end) == 90

    def test_a_jump_of_half_an_hour(self) -> None:
        now = datetime(2026, 10, 4, 1, 0, tzinfo=LORD_HOWE)
        end = next_occurrence(now, time(2, 15))
        assert shown(end, LORD_HOWE) == "2026-10-04T02:30:00+11:00"
        assert shown(end - timedelta(seconds=1), LORD_HOWE) == "2026-10-04T01:59:59+10:30"

    # The night the clocks go back.

    def test_a_repeated_time_ends_at_its_first_occurrence(self) -> None:
        end = next_occurrence(budapest(2026, 10, 25, 1, 0), time(2, 30))
        assert shown(end) == "2026-10-25T02:30:00+02:00"

    def test_a_repeated_time_ends_at_its_second_occurrence_once_the_first_passed(self) -> None:
        end = next_occurrence(budapest(2026, 10, 25, 2, 45), time(2, 30))
        assert shown(end) == "2026-10-25T02:30:00+01:00"

    def test_a_repeated_time_after_both_occurrences_means_tomorrow(self) -> None:
        end = next_occurrence(budapest(2026, 10, 25, 2, 45, fold=1), time(2, 30))
        assert shown(end) == "2026-10-26T02:30:00+01:00"

    def test_a_time_after_the_repeated_hour(self) -> None:
        now = budapest(2026, 10, 25, 1, 0)
        end = next_occurrence(now, time(4, 0))
        assert shown(end) == "2026-10-25T04:00:00+01:00"
        assert minutes_left(now, end) == 240


class TestRemaining:
    def test_counts_real_time_across_a_clock_change(self) -> None:
        # Both ends share one tzinfo, which is the case plain subtraction gets wrong (3 h).
        now, end = budapest(2026, 3, 29, 1, 0), budapest(2026, 3, 29, 4, 0)
        assert remaining(now, end) == timedelta(hours=2)

    def test_is_zero_once_the_end_has_passed(self) -> None:
        now = budapest(2026, 6, 1, 10, 0)
        assert remaining(now, now - timedelta(minutes=5)) == timedelta(0)
        assert minutes_left(now, now - timedelta(minutes=5)) == 0

    @pytest.mark.parametrize(
        ("left", "minutes"),
        [
            (timedelta(0), 0),
            (timedelta(seconds=1), 1),
            (timedelta(seconds=60), 1),
            (timedelta(seconds=61), 2),
            (timedelta(hours=2), 120),
        ],
    )
    def test_minutes_round_up(self, left: timedelta, minutes: int) -> None:
        now = budapest(2026, 6, 1, 10, 0)
        assert minutes_left(now, now + left) == minutes


class TestParseDuration:
    @pytest.mark.parametrize(
        ("text", "minutes"),
        [
            ("90", 90),
            ("90m", 90),
            ("2h", 120),
            ("1h30m", 90),
            ("1h 30m", 90),
            (" 45M ", 45),
            ("0h5m", 5),
        ],
    )
    def test_reads(self, text: str, minutes: int) -> None:
        assert parse_duration(text) == timedelta(minutes=minutes)

    @pytest.mark.parametrize(
        "text", ["", "h", "m", "1.5h", "-5", "90s", "1h30", "30m1h", "abc", "²"]
    )
    def test_refuses_what_is_not_a_duration(self, text: str) -> None:
        with pytest.raises(ValueError, match="not a duration"):
            parse_duration(text)

    @pytest.mark.parametrize("text", ["0", "0m", "0h", "0h0m"])
    def test_refuses_zero(self, text: str) -> None:
        with pytest.raises(ValueError, match="positive"):
            parse_duration(text)

    def test_refuses_a_duration_past_the_calendar(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            parse_duration("99999999999h")


class TestParseClockTime:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("18:00", time(18, 0)),
            ("8:05", time(8, 5)),
            ("00:00", time(0, 0)),
            ("23:59", time(23, 59)),
            (" 7:30 ", time(7, 30)),
        ],
    )
    def test_reads(self, text: str, expected: time) -> None:
        assert parse_clock_time(text) == expected

    @pytest.mark.parametrize(
        "text", ["", "24:00", "18:60", "18", "18:5", "1800", "18:00:00", "-1:00", "18.00"]
    )
    def test_refuses_what_is_not_a_time_of_day(self, text: str) -> None:
        with pytest.raises(ValueError, match="not a time of day"):
            parse_clock_time(text)
