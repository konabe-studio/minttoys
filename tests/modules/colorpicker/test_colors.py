"""Color Picker's formats, checked against PowerToys' own expectations
(ColorFormatConversionTest.cs) where it has them.
"""

import pytest

from tuxtoys.modules.colorpicker.colors import (
    DEFAULT_FORMATS,
    Color,
    cmyk,
    format_color,
    hsl,
    hue,
    lab,
)

FORMATS = dict(DEFAULT_FORMATS)
RED, WHITE = Color(255, 0, 0), Color(255, 255, 255)
GREEN, BLUE = Color(0, 255, 0), Color(0, 0, 255)


@pytest.mark.parametrize(
    ("color", "name", "made"),
    [
        (RED, "CMYK", "cmyk(0%, 100%, 100%, 0%)"),
        (RED, "HEX", "ff0000"),
        (RED, "RGB", "rgb(255, 0, 0)"),
        (RED, "HSL", "hsl(0, 100%, 50%)"),
        (RED, "HSV", "hsv(0, 100%, 100%)"),
        (RED, "HSB", "hsb(0, 100%, 100%)"),
        (RED, "HSI", "hsi(0, 100%, 33%)"),
        (RED, "HWB", "hwb(0, 0%, 0%)"),
        (RED, "Decimal", "255"),
        (RED, "HEX Int", "0xFFFF0000"),
        (RED, "VEC4", "(1f, 0f, 0f, 1f)"),
        (WHITE, "CMYK", "cmyk(0%, 0%, 0%, 0%)"),
        (WHITE, "HEX", "ffffff"),
        (WHITE, "HSL", "hsl(0, 0%, 100%)"),
        (WHITE, "HSV", "hsv(0, 0%, 100%)"),
        (WHITE, "Decimal", "16777215"),
        (WHITE, "VEC4", "(1f, 1f, 1f, 1f)"),
        (GREEN, "CMYK", "cmyk(100%, 0%, 100%, 0%)"),
        (GREEN, "HSL", "hsl(120, 100%, 50%)"),
        (GREEN, "Decimal", "65280"),
        (GREEN, "HEX Int", "0xFF00FF00"),
        (BLUE, "HEX", "0000ff"),
        (BLUE, "HSL", "hsl(240, 100%, 50%)"),
        (BLUE, "Decimal", "16711680"),
        (BLUE, "HEX Int", "0xFF0000FF"),
    ],
)
def test_as_powertoys_writes_them(color: Color, name: str, made: str) -> None:
    assert format_color(color, FORMATS[name]) == made


def test_conversions() -> None:
    assert cmyk(Color(0, 0, 0)) == (0, 0, 0, 1)
    assert cmyk(Color(128, 128, 128))[3] == pytest.approx(1 - 128 / 255)
    assert hue(Color(255, 255, 0)) == 60
    assert hue(Color(255, 0, 255)) == 300
    assert hue(Color(9, 9, 9)) == 0
    assert hsl(Color(64, 128, 192))[1] == pytest.approx(0.5, abs=0.01)
    lightness, a, b = lab(WHITE)
    assert lightness == pytest.approx(100, abs=0.01)
    assert a == pytest.approx(0, abs=0.01)
    assert b == pytest.approx(0, abs=0.01)


def test_the_other_formats() -> None:
    moccasin = Color(255, 228, 181)
    assert format_color(moccasin, FORMATS["NCol"]) == "R64, 71%, 0%"  # hue 38.1
    assert format_color(RED, FORMATS["CIEXYZ"]) == "XYZ(41.2391, 21.2639, 1.9331)"
    assert format_color(RED, FORMATS["CIELAB"]) == "CIELab(53.24, 80.09, 67.2)"
    assert format_color(WHITE, FORMATS["Oklab"]) == "oklab(1, 0, 0)"
    assert format_color(RED, FORMATS["Oklch"]).startswith("oklch(0.63, 0.26, 29.")


def test_letters_after_a_parameter() -> None:
    color = Color(0x12, 0xAB, 0xFE)
    assert format_color(color, "#%ReX%GrX%BlX") == "#12ABFE"
    assert format_color(color, "%Reh%GrH") == "1A"
    assert format_color(color, "%Ref|%GrF|%Blb") == "0.07|.67|254"
    assert format_color(Color(0, 0, 0), "%ReF") == ""
    assert format_color(RED, "%Lci %Lc") == "53 53.24"
    # An unknown parameter, a lone % and one at the end stay as written.
    assert format_color(RED, "%Zz 50% %R") == "%Zz 50% %R"
    assert format_color(RED, "%Re%") == "255%"


def test_hex() -> None:
    assert Color.from_hex("#12abFE") == Color(0x12, 0xAB, 0xFE)
    assert Color(1, 2, 3).hex == "#010203"
    with pytest.raises(ValueError, match="not a color"):
        Color.from_hex("12ab")
