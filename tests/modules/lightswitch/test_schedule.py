from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.lightswitch import schedule
from minttoys.modules.lightswitch.schedule import Dark, NightLight

BUDAPEST = ZoneInfo("Europe/Budapest")
OCTOBER_NOON = datetime(2026, 10, 9, 12, tzinfo=BUDAPEST)


def night_light(mode: str = "auto", latitude: float = 47.3, longitude: float = 19.05) -> NightLight:
    return NightLight(mode, 20.0, 6.0, latitude, longitude)


def test_auto_follows_the_sun() -> None:
    dark = schedule.by_night_light(night_light(), OCTOBER_NOON)
    assert dark.by_sun
    assert 18 < dark.start < 19
    assert 6.5 < dark.end < 7.5


def test_auto_without_a_location_uses_the_set_hours() -> None:
    dark = schedule.by_night_light(night_light(latitude=91, longitude=181), OCTOBER_NOON)
    assert dark == Dark(20.0, 6.0, by_sun=False)


@pytest.mark.parametrize("mode", ["manual", "always"])
def test_other_modes_use_the_set_hours(mode: str) -> None:
    assert schedule.by_night_light(night_light(mode), OCTOBER_NOON) == Dark(20.0, 6.0, False)


def test_by_times() -> None:
    assert schedule.by_times("19:30", "7:15") == Dark(19.5, 7.25, by_sun=False)


def test_by_times_refuses_a_bad_time() -> None:
    with pytest.raises(ValueError, match="not a time of day"):
        schedule.by_times("25:00", "07:00")


@pytest.mark.parametrize(
    ("hour", "minute", "dark"),
    [(12, 0, False), (19, 29, False), (19, 30, True), (23, 59, True), (3, 0, True), (7, 15, False)],
)
def test_is_dark_across_midnight(hour: int, minute: int, dark: bool) -> None:
    hours = schedule.by_times("19:30", "07:15")
    moment = datetime(2026, 10, 9, hour, minute, tzinfo=BUDAPEST)
    assert schedule.is_dark(hours, moment) is dark


@pytest.mark.parametrize(("hours", "text"), [(18.34, "18:20"), (6.999, "07:00"), (23.999, "00:00")])
def test_clock(hours: float, text: str) -> None:
    assert schedule.clock(hours) == text
