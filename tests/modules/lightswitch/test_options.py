import pytest

from minttoys.modules.lightswitch.options import Options

DEFAULTS = {"day_mode": "", "schedule": "night-light", "dark_from": "20:00", "dark_to": "06:00"}


def test_defaults() -> None:
    assert Options().settings() == DEFAULTS


def test_the_day_is_mixed_until_chosen() -> None:
    assert Options().day == "mixed"
    assert Options(day_mode="light").day == "light"


def test_read_keeps_good_values_and_drops_bad_ones() -> None:
    options = Options.read({"day_mode": "light", "schedule": "sometimes", "dark_from": "7:5"})
    assert options.settings() == {**DEFAULTS, "day_mode": "light"}


def test_read_normalizes_times() -> None:
    assert Options.read({"dark_to": "7:05"}).dark_to == "07:05"


def test_update_all_or_none() -> None:
    with pytest.raises(ValueError, match="dark_to"):
        Options().update({"schedule": "times", "dark_to": "25:00"})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"day_mode": "dark"}, "day_mode is mixed or light"),
        ({"day_mode": ""}, "day_mode is mixed or light"),
        ({"schedule": "sun"}, "schedule is night-light or times"),
        ({"dark_from": 20}, "dark_from is a time of day"),
        ({"colour": "green"}, "unknown setting"),
    ],
)
def test_update_refuses(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Options().update(changes)
