from tuxtoys.overlay.pixels import Pixels


def test_a_pixel_and_the_edges() -> None:
    # 2 by 2, RGB, rows padded to 8 bytes as GdkPixbuf pads them.
    data = bytes([1, 2, 3, 4, 5, 6, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0])
    pixels = Pixels(data, 2, 2, 8, 3)
    assert pixels.rgb(0, 0) == (1, 2, 3)
    assert pixels.rgb(1, 1) == (10, 11, 12)
    assert pixels.rgb(5, -3) == (4, 5, 6)
