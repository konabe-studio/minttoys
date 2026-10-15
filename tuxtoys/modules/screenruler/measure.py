"""Screen Ruler's measuring, ported from PowerToys' MeasureTool, so it finds the same edges
and writes the same numbers. Free of GTK.

From the pixel under the pointer it walks left, right, up and down while each pixel stays
close to that first one: every channel within the tolerance, or, by default, all channels'
differences added up within it. Where a pixel differs more, the edge is the one before it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from tuxtoys.overlay.monitors import Monitor, monitor_at

# PowerToys' own: the scroll wheel changes the tolerance by this much a step.
TOLERANCE_STEP = 15
DEFAULT_DPI = 96.0
TIMES = "\N{MULTIPLICATION SIGN}"
# The second unit Screen Ruler can show beside the pixels.
EXTRA_UNITS = ("none", "in", "cm", "mm")


class Screen(Protocol):
    width: int
    height: int

    def rgb(self, x: int, y: int) -> tuple[int, int, int]: ...


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """In pixels, both edges counted, as PowerToys counts them."""
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1


type RGB = tuple[int, int, int]


def close(first: RGB, second: RGB, tolerance: int, per_channel: bool) -> bool:
    distances = [abs(a - b) for a, b in zip(first, second, strict=True)]
    if per_channel:
        return max(distances) <= tolerance
    return sum(distances) <= tolerance


def _edge(
    screen: Screen, x: int, y: int, dx: int, dy: int, tolerance: int, per_channel: bool
) -> int:
    start = screen.rgb(x, y)
    while True:
        old_x, old_y = x, y
        x, y = x + dx, y + dy
        if not (0 <= x < screen.width and 0 <= y < screen.height):
            break
        if not close(start, screen.rgb(x, y), tolerance, per_channel):
            return old_x if dx else old_y
    if dx:
        return screen.width - 1 if dx > 0 else 0
    return screen.height - 1 if dy > 0 else 0


def find_edges(screen: Screen, x: int, y: int, tolerance: int, per_channel: bool) -> Rect:
    """The edges around (x, y), kept one pixel inside the screen as PowerToys keeps them."""
    x = min(max(x, 1), screen.width - 2)
    y = min(max(y, 1), screen.height - 2)
    return Rect(
        _edge(screen, x, y, -1, 0, tolerance, per_channel),
        _edge(screen, x, y, 0, -1, tolerance, per_channel),
        _edge(screen, x, y, 1, 0, tolerance, per_channel),
        _edge(screen, x, y, 0, 1, tolerance, per_channel),
    )


def convert(pixels: float, unit: str, mm_per_pixel: float) -> float:
    """Pixels in `unit`, "" for pixels; with no size known for the monitor, at 96 pixels an inch."""
    if not unit:
        return pixels
    known = mm_per_pixel > 0
    millimetres = pixels * mm_per_pixel if known else pixels / DEFAULT_DPI * 25.4
    return {"in": millimetres / 25.4, "cm": millimetres / 10, "mm": millimetres}[unit]


def _number(value: float) -> str:
    return f"{value:.4g}"


def label(
    width: int | None,
    height: int | None,
    extra_unit: str,
    mm_per_pixel: float,
    names: dict[str, str],
) -> str:
    """What the ruler shows, as "120 x 40 px" with a multiplication sign, and the extra unit
    in brackets on a line of its own when both sides are measured, after them otherwise;
    "none" shows pixels alone. `names` gives each unit's abbreviation, "" for pixels.
    """

    def line(unit: str) -> str:
        sides = [side for side in (width, height) if side is not None]
        parts = [_number(convert(side, unit, mm_per_pixel)) for side in sides]
        return f" {TIMES} ".join(parts) + f" {names[unit]}"

    text = line("")
    if extra_unit != "none":
        both = width is not None and height is not None
        text += ("\n(" if both else " (") + line(extra_unit) + ")"
    return text


def copied(measurements: Sequence[tuple[int | None, int | None]]) -> str:
    """What goes to the clipboard: each measurement in pixels, with no unit, a line each."""
    lines = []
    for width, height in measurements:
        lines.append(f" {TIMES} ".join(str(side) for side in (width, height) if side is not None))
    return "\n".join(lines)


class Area:
    """One monitor of the screen, so the edges stop where the monitor does, as PowerToys
    measures each monitor on its own. Coordinates are the monitor's own.
    """

    def __init__(self, screen: Screen, monitor: Monitor) -> None:
        self._screen = screen
        self._monitor = monitor
        self.width = monitor.width
        self.height = monitor.height

    def rgb(self, x: int, y: int) -> tuple[int, int, int]:
        return self._screen.rgb(self._monitor.x + x, self._monitor.y + y)


def measure_at(
    screen: Screen, monitors: Sequence[Monitor], x: int, y: int, tolerance: int, per_channel: bool
) -> Rect:
    """The edges around a point of the whole screen, found on its monitor, in the whole
    screen's coordinates.
    """
    monitor = monitor_at(monitors, x, y)
    found = find_edges(Area(screen, monitor), x - monitor.x, y - monitor.y, tolerance, per_channel)
    return Rect(
        found.left + monitor.x,
        found.top + monitor.y,
        found.right + monitor.x,
        found.bottom + monitor.y,
    )


def box(start: tuple[int, int], end: tuple[int, int]) -> Rect:
    """The box dragged from one pixel to another, both inside it."""
    (x1, y1), (x2, y2) = start, end
    return Rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
