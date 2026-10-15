import pytest

from tuxtoys.modules.colorpicker.colors import Color
from tuxtoys.modules.colorpicker.names import _DARK, _LIGHT, _MID, name, name_id, names


@pytest.mark.parametrize(
    ("color", "made"),
    [
        (Color(255, 255, 255), "white"),
        (Color(243, 243, 243), "white"),  # PowerToys calls f3f3f3 White
        (Color(0, 0, 0), "black"),
        (Color(200, 200, 200), "light-gray"),
        (Color(128, 128, 128), "gray"),
        (Color(60, 60, 60), "dark-gray"),
        (Color(255, 0, 0), "red"),
        (Color(0, 128, 0), "dark-green"),  # PowerToys: lightness 64 is dark
        (Color(0, 0, 255), "blue"),
        (Color(0, 0, 100), "dark-blue"),
        (Color(255, 255, 0), "yellow"),
        (Color(255, 165, 0), "gold"),  # PowerToys: hue 39 at full saturation
        (Color(144, 238, 144), "light-green"),
    ],
)
def test_names(color: Color, made: str) -> None:
    assert name_id(color) == made


def test_every_name_has_its_words() -> None:
    known = names()
    for name_ in {*_LIGHT, *_MID, *_DARK, "white", "black", "gray", "light-gray", "dark-gray"}:
        assert name_ in known
    assert name(Color(255, 255, 255)) == "White"
