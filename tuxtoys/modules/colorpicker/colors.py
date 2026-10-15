"""Colors as Color Picker shows and copies them, ported from PowerToys' ColorFormatHelper,
so a format written there gives the same text here. Free of GTK.

A format is text with parameters in it: %Re, %Gr and %Bl for red, green and blue, %Hu for
the hue, %Sl and %Ll for HSL's saturation and lightness, and the others in PARAMETERS. A
letter right after a parameter can change how it is written: x two lowercase hex digits,
X two uppercase, h and H one, f a fraction with a leading zero, F one without, i a whole
number. "%Rex%Grx%Blx" is red, green and blue in hex: ff0000 for red.

Numbers round half to even and print without a needless ".0", as .NET does it.
"""

import math
from dataclasses import dataclass

# The formats PowerToys starts with, in its order.
DEFAULT_FORMATS = (
    ("HEX", "%Rex%Grx%Blx"),
    ("RGB", "rgb(%Re, %Gr, %Bl)"),
    ("HSL", "hsl(%Hu, %Sl%, %Ll%)"),
    ("HSV", "hsv(%Hu, %Sb%, %Va%)"),
    ("CMYK", "cmyk(%Cy%, %Ma%, %Ye%, %Bk%)"),
    ("HSB", "hsb(%Hu, %Sb%, %Br%)"),
    ("HSI", "hsi(%Hu, %Si%, %In%)"),
    ("HWB", "hwb(%Hu, %Wh%, %Bn%)"),
    ("NCol", "%Hn, %Wh%, %Bn%"),
    ("CIEXYZ", "XYZ(%Xv, %Yv, %Zv)"),
    ("CIELAB", "CIELab(%Lc, %Ca, %Cb)"),
    ("Oklab", "oklab(%Lo, %Oa, %Ob)"),
    ("Oklch", "oklch(%Lo, %Oc, %Oh)"),
    ("VEC4", "(%Reff, %Grff, %Blff, 1f)"),
    ("Decimal", "%Dv"),
    ("HEX Int", "0xFF%ReX%GrX%BlX"),
)

# Each parameter with the letter it is written with when none follows it.
PARAMETERS = {
    "Re": "b",  # red
    "Gr": "b",  # green
    "Bl": "b",  # blue
    "Al": "b",  # alpha
    "Cy": "p",  # cyan
    "Ma": "p",  # magenta
    "Ye": "p",  # yellow
    "Bk": "p",  # black key
    "Hu": "i",  # hue
    "Hn": "i",  # hue, natural
    "Si": "p",  # saturation, HSI
    "Sl": "p",  # saturation, HSL
    "Sb": "p",  # saturation, HSB
    "Br": "p",  # brightness
    "In": "p",  # intensity
    "Ll": "p",  # lightness, HSL
    "Va": "p",  # value
    "Wh": "p",  # whiteness
    "Bn": "p",  # blackness
    "Lc": "p",  # lightness, CIE
    "Ca": "p",  # chromaticity A, CIELAB
    "Cb": "p",  # chromaticity B, CIELAB
    "Lo": "p",  # lightness, Oklab and Oklch
    "Oa": "p",  # chromaticity A, Oklab
    "Ob": "p",  # chromaticity B, Oklab
    "Oc": "p",  # chroma, Oklch
    "Oh": "p",  # hue angle, Oklch
    "Xv": "i",  # X
    "Yv": "i",  # Y
    "Zv": "i",  # Z
    "Dr": "i",  # decimal, RGB
    "Dv": "i",  # decimal, BGR
}
LETTERS = "bhHxXfFpis"


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: int = 255

    @classmethod
    def from_hex(cls, text: str) -> "Color":
        """From "#rrggbb" or "rrggbb"; ValueError for anything else."""
        digits = text.strip().removeprefix("#")
        if len(digits) != 6 or any(c not in "0123456789abcdefABCDEF" for c in digits):
            raise ValueError(f"not a color: {text!r}")
        return cls(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


def hue(color: Color) -> float:
    """The hue in degrees, 0 for a gray, as System.Drawing.Color.GetHue gives it."""
    r, g, b = color.r / 255, color.g / 255, color.b / 255
    top, bottom = max(r, g, b), min(r, g, b)
    if top == bottom:
        return 0.0
    span = top - bottom
    if top == r:
        found = (g - b) / span
    elif top == g:
        found = 2 + (b - r) / span
    else:
        found = 4 + (r - g) / span
    found *= 60
    return found + 360 if found < 0 else found


def _min_max(color: Color) -> tuple[float, float]:
    return min(color.r, color.g, color.b) / 255, max(color.r, color.g, color.b) / 255


def cmyk(color: Color) -> tuple[float, float, float, float]:
    if color.r == color.g == color.b == 0:
        return 0.0, 0.0, 0.0, 1.0
    r, g, b = color.r / 255, color.g / 255, color.b / 255
    black = 1 - max(r, g, b)
    if 1 - black == 0:
        return 0.0, 0.0, 0.0, 1.0
    return (
        (1 - r - black) / (1 - black),
        (1 - g - black) / (1 - black),
        (1 - b - black) / (1 - black),
        black,
    )


def hsv(color: Color) -> tuple[float, float, float]:
    low, high = _min_max(color)
    return hue(color), 0.0 if high == 0 else (high - low) / high, high


def hsi(color: Color) -> tuple[float, float, float]:
    if color.r == color.g == color.b == 0:
        return 0.0, 0.0, 0.0
    intensity = (color.r + color.g + color.b) / 255 / 3
    low, _high = _min_max(color)
    return hue(color), 1 - low / intensity, intensity


def hsl(color: Color) -> tuple[float, float, float]:
    low, high = _min_max(color)
    lightness = (high + low) / 2
    if lightness == 0 or low == high:
        return hue(color), 0.0, lightness
    if lightness <= 0.5:
        return hue(color), (high - low) / (high + low), lightness
    return hue(color), (high - low) / (2 - (high + low)), lightness


def hwb(color: Color) -> tuple[float, float, float]:
    low, high = _min_max(color)
    return hue(color), low, 1 - high


def _linear(value: float) -> float:
    return ((value + 0.055) / 1.055) ** 2.4 if value > 0.04045 else value / 12.92


def xyz(color: Color) -> tuple[float, float, float]:
    r, g, b = (_linear(c / 255) for c in (color.r, color.g, color.b))
    return (
        r * 0.41239079926595948 + g * 0.35758433938387796 + b * 0.18048078840183429,
        r * 0.21263900587151036 + g * 0.71516867876775593 + b * 0.07219231536073372,
        r * 0.01933081871559185 + g * 0.11919477979462599 + b * 0.95053215224966058,
    )


def lab(color: Color) -> tuple[float, float, float]:
    x, y, z = xyz(color)
    x, z = x / 0.9504559270516717, z / 1.0890577507598784
    delta = 6 / 29
    slope = (1 / 3) * delta**-2
    edge = delta**3

    def f(value: float) -> float:
        return value ** (1 / 3) if value > edge else value * slope + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def oklab(color: Color) -> tuple[float, float, float]:
    r, g, b = (_linear(c / 255) for c in (color.r, color.g, color.b))
    long_ = 0.41222147079999993 * r + 0.5363325363 * g + 0.0514459929 * b
    medium = 0.2119034981999999 * r + 0.6806995450999999 * g + 0.1073969566 * b
    short = 0.08830246189999998 * r + 0.2817188376 * g + 0.6299787005000002 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (long_, medium, short))
    return (
        0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
    )


def oklch(color: Color) -> tuple[float, float, float]:
    lightness, a, b = oklab(color)
    chroma = math.sqrt(a * a + b * b)
    angle = 0.0 if round(chroma, 3) == 0 else (math.degrees(math.atan2(b, a)) + 360) % 360
    return lightness, chroma, angle


def natural_hue(color: Color) -> str:
    """PowerToys' NCol hue: a letter for the primary and how far towards the next."""
    angle = hue(color)
    for limit, letter in ((60, "R"), (120, "Y"), (180, "G"), (240, "C"), (300, "B")):
        if angle < limit:
            return f"{letter}{_number(round((angle - limit + 60) / 0.6))}"
    return f"M{_number(round((angle - 300) / 0.6))}"


def _number(value: float) -> str:
    """A number as .NET writes it: no needless ".0", and "-0" as "0"."""
    if value == 0:
        return "0"
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def _fraction(value: float, leading_zero: bool) -> str:
    """.NET's "0.##" and ".##"."""
    text = f"{round(value, 2):.2f}".rstrip("0").rstrip(".")
    if not leading_zero:
        text = text.removeprefix("0")
    return text


def _byte(value: int, letter: str) -> str:
    if letter in "hH":
        digit = f"{value // 16:x}"
        return digit.upper() if letter == "H" else digit
    if letter == "x":
        return f"{value:02x}"
    if letter == "X":
        return f"{value:02X}"
    if letter in "fF":
        return _fraction(value / 255, letter == "f")
    return str(value)


def _percent(value: float, letter: str) -> str:
    return _number(round(value)) if letter == "i" else _number(round(value, 2))


def _value(color: Color, name: str, letter: str) -> str:
    match name:
        case "Re" | "Gr" | "Bl" | "Al":
            return _byte({"Re": color.r, "Gr": color.g, "Bl": color.b, "Al": color.a}[name], letter)
        case "Cy" | "Ma" | "Ye" | "Bk":
            return _number(round(cmyk(color)["CyMaYeBk".index(name) // 2] * 100))
        case "Hu":
            return _number(round(hue(color)))
        case "Hn":
            return natural_hue(color)
        case "Sb":
            return _number(round(hsv(color)[1] * 100))
        case "Si":
            return _number(round(hsi(color)[1] * 100))
        case "Sl":
            return _number(round(hsl(color)[1] * 100))
        case "Va" | "Br":
            return _number(round(hsv(color)[2] * 100))
        case "In":
            return _number(round(hsi(color)[2] * 100))
        case "Ll":
            return _number(round(hsl(color)[2] * 100))
        case "Lc" | "Ca" | "Cb":
            return _percent(lab(color)["LcCaCb".index(name) // 2], letter)
        case "Lo" | "Oa" | "Ob":
            return _number(round(oklab(color)["LoOaOb".index(name) // 2], 2))
        case "Oc" | "Oh":
            return _number(round(oklch(color)[1 if name == "Oc" else 2], 2))
        case "Wh":
            return _number(round(hwb(color)[1] * 100))
        case "Bn":
            return _number(round(hwb(color)[2] * 100))
        case "Xv" | "Yv" | "Zv":
            return _number(round(xyz(color)["XvYvZv".index(name) // 2] * 100, 4))
        case "Dr":
            return str(color.r * 65536 + color.g * 256 + color.b)
        case "Dv":
            return str(color.r + color.g * 256 + color.b * 65536)
    return ""


def format_color(color: Color, template: str) -> str:
    """`template` with its parameters filled in, the way PowerToys does it: each "%"
    followed by a known parameter, and maybe a letter, is replaced; any other "%" stays.
    """
    text = template
    position = text.find("%")
    while position != -1:
        if position >= len(text) - 2:
            break
        name = text[position + 1 : position + 3]
        if name in PARAMETERS:
            letter = text[position + 3] if position + 3 < len(text) else ""
            used = 3
            if letter not in LETTERS or not letter:
                letter, used = PARAMETERS[name], 2
            value = _value(color, name, letter)
            text = text[:position] + value + text[position + used + 1 :]
        position = text.find("%", position + 1)
    return text
