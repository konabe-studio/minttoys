"""How big a resized picture comes out, and which part of it is kept, as PowerToys' Image
Resizer works it out. Free of images: only numbers.

- Fit: the whole picture inside the size, in proportion. Nothing is cut.
- Fill: the whole size covered, in proportion; what sticks out is cut off, evenly on
  both sides.
- Stretch: exactly the size, out of proportion if need be.
A width or height left empty (0) follows from the other and the picture's proportions.
Percent is of the picture's own width and height; cm and in go through its resolution,
96 dots per inch when it has none.
"""

from dataclasses import dataclass

from tuxtoys.modules.imageresizer.options import Size

DEFAULT_DPI = 96.0
CM_PER_INCH = 2.54


@dataclass(frozen=True)
class Plan:
    """Scale the picture to `scaled`, then keep `crop` (left, top, right, bottom) of it.
    `width` and `height` are what comes out; `asked` is the size asked for, in pixels.
    """

    scaled: tuple[int, int]
    crop: tuple[int, int, int, int]
    asked: tuple[int, int]

    @property
    def width(self) -> int:
        return self.crop[2] - self.crop[0]

    @property
    def height(self) -> int:
        return self.crop[3] - self.crop[1]


def in_pixels(value: float, unit: str, own: int, dpi: float) -> float:
    """A width or a height in pixels; 0 stays 0, left empty."""
    if value <= 0:
        return 0.0
    if unit == "percent":
        return own * value / 100
    if unit == "in":
        return value * (dpi or DEFAULT_DPI)
    if unit == "cm":
        return value / CM_PER_INCH * (dpi or DEFAULT_DPI)
    return value


def plan(
    picture: tuple[int, int],
    size: Size,
    shrink_only: bool = False,
    ignore_orientation: bool = True,
    dpi: tuple[float, float] = (DEFAULT_DPI, DEFAULT_DPI),
) -> Plan:
    """What resizing a picture of `picture` pixels to `size` makes of it."""
    own_width, own_height = picture
    width = in_pixels(size.width, size.unit, own_width, dpi[0])
    height = in_pixels(size.height, size.unit, own_height, dpi[1])

    # Portrait and landscape pictures alike: the smaller number goes to the shorter side.
    if (
        ignore_orientation
        and width
        and height
        and size.unit != "percent"
        and (own_width < own_height) != (width < height)
    ):
        width, height = height, width

    scale_x = width / own_width if width else 0.0
    scale_y = height / own_height if height else 0.0
    if not scale_x:
        scale_x = scale_y
    if not scale_y:
        scale_y = scale_x

    if size.fit == "fit":
        scale_x = scale_y = min(scale_x, scale_y)
    elif size.fit == "fill":
        scale_x = scale_y = max(scale_x, scale_y)

    if shrink_only and scale_x >= 1 and scale_y >= 1:
        scale_x = scale_y = 1.0

    scaled = (max(1, round(own_width * scale_x)), max(1, round(own_height * scale_y)))
    asked = (round(width) or scaled[0], round(height) or scaled[1])
    if size.fit == "fill" and not (shrink_only and scale_x == 1.0):
        keep_width = min(scaled[0], asked[0])
        keep_height = min(scaled[1], asked[1])
        left = (scaled[0] - keep_width) // 2
        top = (scaled[1] - keep_height) // 2
        crop = (left, top, left + keep_width, top + keep_height)
    else:
        crop = (0, 0, *scaled)
    return Plan(scaled, crop, asked)
