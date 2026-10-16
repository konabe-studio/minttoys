import pytest

from tuxtoys.api import SHORTCUTGUIDE_SETTINGS
from tuxtoys.modules.shortcutguide.options import MOST_PINS, Options


def test_the_defaults() -> None:
    assert Options.read({}).settings() == {
        "shortcut": True,
        "position": "left",
        "excluded": "",
        "pinned": [],
    }


def test_every_setting_has_a_d_bus_type() -> None:
    assert set(Options().settings()) == set(SHORTCUTGUIDE_SETTINGS)


def test_a_bad_value_in_the_config_gives_its_default() -> None:
    assert Options.read({"position": "top", "pinned": "x", "shortcut": 1}) == Options()


def test_values_it_takes() -> None:
    options = Options().update(
        {
            "position": "right",
            "excluded": "  Gimp \n\nfirefox\n",
            "pinned": ["cinnamon/show-desktop", "nemo/Rename", "cinnamon/show-desktop"],
        }
    )
    assert options.position == "right"
    assert options.excluded == "Gimp\nfirefox"
    assert options.excluded_apps == ["gimp", "firefox"]
    assert options.pinned == ("cinnamon/show-desktop", "nemo/Rename")
    assert options.settings()["pinned"] == ["cinnamon/show-desktop", "nemo/Rename"]


@pytest.mark.parametrize(
    "changes",
    [
        {"shortcut": "yes"},
        {"position": "top"},
        {"excluded": "fire fox"},
        {"excluded": 3},
        {"pinned": ["no-slash"]},
        {"pinned": [3]},
        {"pinned": [f"a/{n}" for n in range(MOST_PINS + 1)]},
        {"theme": "dark"},
    ],
)
def test_values_it_refuses(changes: dict) -> None:
    with pytest.raises(ValueError, match=r"not|unknown|at most"):
        Options().update(changes)
