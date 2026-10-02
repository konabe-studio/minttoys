import pytest

from minttoys.settings import values


def test_modes_are_what_toggle_can_start() -> None:
    assert [mode for mode, _ in values.modes()] == ["indefinite", "duration", "until"]


@pytest.mark.parametrize(("total", "fields"), [(60, (1, 0)), (90, (1, 30)), (5999, (99, 59))])
def test_split_minutes(total: int, fields: tuple[int, int]) -> None:
    assert values.split_minutes(total) == fields


@pytest.mark.parametrize(
    ("fields", "total"),
    [((1, 30), 90), ((0, 0), 1), ((99, 59), 5999), ((99, 60), 5999)],
)
def test_join_minutes_stays_in_what_the_daemon_takes(fields: tuple[int, int], total: int) -> None:
    assert values.join_minutes(*fields) == total


def test_time_round_trip() -> None:
    assert values.split_time("07:05") == (7, 5)
    assert values.join_time(7, 5) == "07:05"
