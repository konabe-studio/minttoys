"""Where the monitors are on the screen, for the screen tools: which one the pointer is on,
where a toolbar goes, where a measurement stops. Free of GTK.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Monitor:
    """A monitor's place on the screen, in pixels, and how large a pixel is on it, or 0
    when the monitor does not say.
    """

    x: int
    y: int
    width: int
    height: int
    mm_per_pixel: float = 0.0

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


def monitor_at(monitors: Sequence[Monitor], x: int, y: int) -> Monitor:
    """The monitor the point is on; the first one for a point on none."""
    return next((monitor for monitor in monitors if monitor.contains(x, y)), monitors[0])
