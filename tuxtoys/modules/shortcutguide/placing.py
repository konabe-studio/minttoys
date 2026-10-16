"""Where Shortcut Guide's window goes: a tall panel at the left or right edge of the monitor
the pointer is on, or in its middle, inside the part the panels leave free. Free of GTK.
"""

from tuxtoys.overlay.monitors import Monitor

WIDTH = 560
MARGIN = 12


def panel(workarea: Monitor, position: str) -> tuple[int, int, int, int]:
    """The window's x, y, width and height on a monitor's work area."""
    width = min(WIDTH, workarea.width - 2 * MARGIN)
    height = workarea.height - 2 * MARGIN
    y = workarea.y + MARGIN
    if position == "right":
        x = workarea.x + workarea.width - MARGIN - width
    elif position == "center":
        x = workarea.x + (workarea.width - width) // 2
    else:
        x = workarea.x + MARGIN
    return x, y, width, height
