from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.lightswitch import sun

BUDAPEST = ZoneInfo("Europe/Budapest")
# Where Night Light put a test machine in Hungary, from its time zone.
HERE = (47.3, 19.05)


def minutes(hours: float) -> int:
    return round(hours * 60)


def test_budapest_in_october() -> None:
    sunrise, sunset = sun.sunrise_sunset(datetime(2026, 10, 9, 12, tzinfo=BUDAPEST), *HERE)
    assert abs(minutes(sunrise) - (6 * 60 + 53)) <= 10
    assert abs(minutes(sunset) - (18 * 60 + 11)) <= 10


def test_summer_time_moves_the_clock_hours_too() -> None:
    summer = sun.sunrise_sunset(datetime(2026, 6, 21, 12, tzinfo=BUDAPEST), *HERE)
    winter = sun.sunrise_sunset(datetime(2026, 12, 21, 12, tzinfo=BUDAPEST), *HERE)
    assert 4.5 < summer[0] < 5.5
    assert 20.0 < summer[1] < 21.0
    assert 7.0 < winter[0] < 8.0
    assert 15.5 < winter[1] < 16.5


def test_no_sunset_at_the_pole_in_summer() -> None:
    assert sun.sunrise_sunset(datetime(2026, 6, 21, 12, tzinfo=ZoneInfo("UTC")), 89.0, 0.0) is None


@pytest.mark.parametrize("coordinates", [(91.0, 181.0), (47.3, 200.0), (-95.0, 19.0)])
def test_unknown_coordinates_give_nothing(coordinates: tuple[float, float]) -> None:
    assert not sun.valid_coordinates(*coordinates)
    assert sun.sunrise_sunset(datetime(2026, 6, 21, tzinfo=BUDAPEST), *coordinates) is None


@pytest.mark.parametrize(
    ("value", "start", "end", "inside"),
    [
        (21.0, 20.0, 6.0, True),
        (3.0, 20.0, 6.0, True),
        (6.0, 20.0, 6.0, False),
        (12.0, 20.0, 6.0, False),
        (20.0, 20.0, 6.0, True),
        (10.0, 9.0, 17.0, True),
        (17.0, 9.0, 17.0, False),
        (12.0, 8.0, 8.0, True),
    ],
)
def test_is_between(value: float, start: float, end: float, inside: bool) -> None:
    assert sun.is_between(value, start, end) is inside


def test_frac_day() -> None:
    assert sun.frac_day(datetime(2026, 1, 1, 16, 30, 36, tzinfo=BUDAPEST)) == pytest.approx(16.51)
