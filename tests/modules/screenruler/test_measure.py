from dataclasses import dataclass

import pytest

from tuxtoys.modules.screenruler.measure import (
    TIMES,
    Monitor,
    Rect,
    box,
    close,
    convert,
    copied,
    find_edges,
    label,
    measure_at,
    monitor_at,
)

NAMES = {"": "px", "in": "in", "cm": "cm", "mm": "mm"}
WHITE = (255, 255, 255)
GREY = (200, 200, 200)


@dataclass
class Picture:
    """A white screen with grey boxes on it, as (left, top, right, bottom), both inclusive."""

    width: int
    height: int
    boxes: list[tuple[int, int, int, int]]
    box_color: tuple[int, int, int] = GREY

    def rgb(self, x: int, y: int) -> tuple[int, int, int]:
        assert 0 <= x < self.width
        assert 0 <= y < self.height
        for left, top, right, bottom in self.boxes:
            if left <= x <= right and top <= y <= bottom:
                return self.box_color
        return WHITE


def test_closeness_adds_the_channels_up_unless_asked_for_each() -> None:
    assert close((10, 10, 10), (20, 20, 20), 30, per_channel=False)
    assert not close((10, 10, 10), (21, 20, 20), 30, per_channel=False)
    assert close((10, 10, 10), (40, 40, 40), 30, per_channel=True)
    assert not close((10, 10, 10), (41, 10, 10), 30, per_channel=True)


def test_inside_a_box_its_edges_are_found() -> None:
    screen = Picture(100, 80, [(10, 20, 39, 29)])
    rect = find_edges(screen, 15, 25, 30, per_channel=False)
    assert rect == Rect(10, 20, 39, 29)
    assert (rect.width, rect.height) == (30, 10)


def test_outside_the_box_the_space_around_it_is_measured() -> None:
    screen = Picture(100, 80, [(10, 20, 39, 29)])
    # Left of the box: from the screen's edge to the column before the box.
    assert find_edges(screen, 5, 25, 30, per_channel=False) == Rect(0, 0, 9, 79)
    # Below it, the whole width.
    assert find_edges(screen, 15, 50, 30, per_channel=False) == Rect(0, 30, 99, 79)


def test_a_higher_tolerance_looks_through_a_faint_box() -> None:
    screen = Picture(100, 80, [(10, 20, 39, 29)], box_color=(245, 245, 245))
    assert find_edges(screen, 15, 50, 29, per_channel=False).top == 30
    assert find_edges(screen, 15, 50, 30, per_channel=False).top == 0
    assert find_edges(screen, 15, 50, 9, per_channel=True).top == 30
    assert find_edges(screen, 15, 50, 10, per_channel=True).top == 0


def test_the_start_stays_one_pixel_inside_the_screen() -> None:
    # A one-pixel line along the very top: PowerToys starts from the second row.
    screen = Picture(50, 40, [(0, 0, 49, 0)])
    assert find_edges(screen, 20, 0, 30, per_channel=False) == Rect(0, 1, 49, 39)
    assert find_edges(screen, 0, 39, 30, per_channel=False) == Rect(0, 1, 49, 39)


def test_pixels_convert_by_the_monitor_or_96_dpi() -> None:
    assert convert(96, "", 0) == 96
    assert convert(96, "in", 0) == pytest.approx(1)
    assert convert(96, "cm", 0) == pytest.approx(2.54)
    assert convert(96, "mm", 0) == pytest.approx(25.4)
    assert convert(100, "mm", 0.25) == pytest.approx(25)
    assert convert(100, "cm", 0.25) == pytest.approx(2.5)
    assert convert(127, "in", 0.2) == pytest.approx(1)


def test_the_sign_is_a_multiplication_sign() -> None:
    assert ord(TIMES) == 0xD7


def test_the_label_shows_pixels_and_the_extra_unit() -> None:
    assert label(120, 40, "none", 0, NAMES) == f"120 {TIMES} 40 px"
    assert label(120, None, "none", 0, NAMES) == "120 px"
    assert label(None, 40, "none", 0, NAMES) == "40 px"
    assert label(96, 48, "in", 0, NAMES) == f"96 {TIMES} 48 px\n(1 {TIMES} 0.5 in)"
    assert label(96, None, "cm", 0, NAMES) == "96 px (2.54 cm)"
    # Four significant digits, as PowerToys writes them.
    assert label(1000, None, "mm", 0, NAMES) == "1000 px (264.6 mm)"


def test_the_clipboard_gets_plain_pixels_a_line_each() -> None:
    assert copied([(120, 40)]) == f"120 {TIMES} 40"
    assert copied([(120, None), (None, 40), (3, 4)]) == f"120\n40\n3 {TIMES} 4"


def test_each_monitor_is_measured_on_its_own() -> None:
    screen = Picture(200, 80, [(150, 10, 159, 19)])
    monitors = [Monitor(0, 0, 100, 80), Monitor(100, 0, 100, 60, 0.25)]
    assert monitor_at(monitors, 120, 10).mm_per_pixel == 0.25
    assert monitor_at(monitors, 120, 70).x == 0  # on no monitor: the first
    # The white around the box on the right monitor stops at that monitor's edges.
    assert measure_at(screen, monitors, 120, 15, 30, False) == Rect(100, 0, 149, 59)
    assert measure_at(screen, monitors, 155, 15, 30, False) == Rect(150, 10, 159, 19)
    assert measure_at(screen, monitors, 50, 40, 30, False) == Rect(0, 0, 99, 79)


def test_a_box_counts_both_ends_whichever_way_it_was_dragged() -> None:
    assert box((10, 20), (39, 29)) == Rect(10, 20, 39, 29)
    assert box((39, 29), (10, 20)) == Rect(10, 20, 39, 29)
    assert (box((5, 5), (5, 5)).width, box((5, 5), (5, 5)).height) == (1, 1)
