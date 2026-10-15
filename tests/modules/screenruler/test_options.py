import pytest

from tuxtoys.modules.screenruler.options import Options


def test_the_defaults_are_powertoys_own() -> None:
    assert Options.read({}).settings() == {
        "shortcut": True,
        "default_mode": "none",
        "tolerance": 30,
        "per_channel": False,
        "extra_unit": "none",
        "draw_feet": True,
        "line_color": "#ff4500",
    }


def test_a_bad_value_in_the_config_gives_its_default() -> None:
    options = Options.read({"tolerance": 300, "default_mode": "zigzag", "line_color": "red"})
    assert options == Options()
    options = Options.read({"tolerance": 45, "extra_unit": "cm", "line_color": "#00FF00"})
    assert (options.tolerance, options.extra_unit, options.line_color) == (45, "cm", "#00ff00")


@pytest.mark.parametrize(
    "changes",
    [
        {"tolerance": -1},
        {"tolerance": True},
        {"default_mode": "diagonal"},
        {"extra_unit": "px"},
        {"line_color": "#12345"},
        {"draw_feet": 1},
        {"ruler": True},
    ],
    ids=["negative", "bool", "mode", "unit", "color", "flag", "unknown"],
)
def test_a_change_is_checked(changes: dict) -> None:
    with pytest.raises(ValueError, match=r"not|unknown"):
        Options().update(changes)


def test_a_change_is_all_or_none() -> None:
    with pytest.raises(ValueError, match="extra_unit"):
        Options().update({"tolerance": 60, "extra_unit": "yards"})
    assert Options().update({"tolerance": 60, "default_mode": "spacing"}).tolerance == 60
