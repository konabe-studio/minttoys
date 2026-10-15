"""The frozen screen as plain bytes, to read a pixel from without GTK: what Color Picker
picks and what Screen Ruler looks along for edges.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Pixels:
    data: bytes
    width: int
    height: int
    rowstride: int
    channels: int

    @classmethod
    def from_pixbuf(cls, pixbuf: Any) -> "Pixels":  # noqa: ANN401, a GdkPixbuf.Pixbuf
        return cls(
            bytes(pixbuf.get_pixels()),
            pixbuf.get_width(),
            pixbuf.get_height(),
            pixbuf.get_rowstride(),
            pixbuf.get_n_channels(),
        )

    def rgb(self, x: int, y: int) -> tuple[int, int, int]:
        """The pixel at (x, y), or the nearest one inside the screen."""
        x = min(max(x, 0), self.width - 1)
        y = min(max(y, 0), self.height - 1)
        start = y * self.rowstride + x * self.channels
        return self.data[start], self.data[start + 1], self.data[start + 2]
