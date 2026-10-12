"""Where the frame around a pinned window goes. Free of GTK."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


def around(window: Rect, width: int) -> Rect:
    """The frame's area: the window's, grown by `width` on every side, so the frame sits
    outside the window and covers none of it.
    """
    return Rect(
        window.x - width, window.y - width, window.width + 2 * width, window.height + 2 * width
    )


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    """ "#rrggbb" as red, green and blue from 0 to 1, as cairo takes them."""
    value = color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return red, green, blue
