from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.awake import text

BUDAPEST = ZoneInfo("Europe/Budapest")
NOW = datetime(2026, 6, 1, 10, 0, tzinfo=BUDAPEST)  # 08:00 UTC
OFF = {"mode": "off", "keep_screen": False, "ends_at": 0}


def unix(*fields: int) -> int:
    return int(datetime(*fields, tzinfo=UTC).timestamp())


class TestDescribeAwake:
    def test_off(self) -> None:
        assert text.describe(OFF, NOW) == "Awake is off."

    def test_indefinite_with_the_screen_on(self) -> None:
        state = {"mode": "indefinite", "keep_screen": True, "ends_at": 0}
        assert text.describe(state, NOW) == (
            "Awake is on until you turn it off.\nThe screen stays on."
        )

    def test_timed_without_the_screen(self) -> None:
        state = {"mode": "duration", "keep_screen": False, "ends_at": unix(2026, 6, 1, 9, 25)}
        assert text.describe(state, NOW) == (
            "Awake is on for 1 h 25 min more, until 11:25.\n"
            "The screen may turn off, but the computer will not sleep."
        )

    def test_past_midnight_shows_the_time_only(self) -> None:
        state = {"mode": "until", "keep_screen": False, "ends_at": unix(2026, 6, 1, 23, 0)}
        late = NOW.replace(hour=23)
        assert "for 2 h more, until 01:00." in text.describe(state, late)

    def test_a_day_or_more_away_shows_the_date(self) -> None:
        state = {"mode": "duration", "keep_screen": False, "ends_at": unix(2026, 6, 3, 8, 0)}
        assert "until 2026-06-03 10:00." in text.describe(state, NOW)

    def test_counts_real_time_across_a_clock_change(self) -> None:
        # 01:00 to 04:00 on the night the clocks go forward is two hours, not three.
        now = datetime(2026, 3, 29, 1, 0, tzinfo=BUDAPEST)
        state = {"mode": "until", "keep_screen": False, "ends_at": unix(2026, 3, 29, 2, 0)}
        assert "for 2 h more, until 04:00." in text.describe(state, now)


@pytest.mark.parametrize(
    ("minutes", "expected"), [(0, "0 min"), (45, "45 min"), (60, "1 h"), (125, "2 h 5 min")]
)
def test_format_minutes(minutes: int, expected: str) -> None:
    assert text.format_minutes(minutes) == expected


def test_headline_is_the_first_line() -> None:
    state = {"mode": "indefinite", "keep_screen": False, "ends_at": 0}
    assert text.headline(state, NOW) == "Awake is on until you turn it off."
