import pytest

from tuxtoys.modules.shortcutguide.placing import MARGIN, WIDTH, panel
from tuxtoys.overlay.monitors import Monitor

AREA = Monitor(1920, 0, 1920, 1040)  # the second monitor, a panel at its bottom


@pytest.mark.parametrize(
    ("position", "x"),
    [
        ("left", 1920 + MARGIN),
        ("right", 1920 + 1920 - MARGIN - WIDTH),
        ("center", 1920 + (1920 - WIDTH) // 2),
    ],
)
def test_the_panel_stands_at_its_edge_of_the_work_area(position: str, x: int) -> None:
    assert panel(AREA, position) == (x, MARGIN, WIDTH, 1040 - 2 * MARGIN)


def test_a_narrow_monitor_gets_a_narrower_panel() -> None:
    x, _y, width, _height = panel(Monitor(0, 0, 400, 800), "right")
    assert width == 400 - 2 * MARGIN
    assert x == MARGIN
