import io
import sys
from pathlib import Path

from PIL import Image

from tuxtoys.textextractor.main import settings_command
from tuxtoys.textextractor.reading import Region, Request, picture, read, word_region

WIDTH, HEIGHT = 100, 60
COLUMNS = "level page_num block_num par_num line_num word_num left top width height conf text"
TSV_HEAD = "\t".join(COLUMNS.split()) + "\n"


def screen() -> bytes:
    """White, RGB, with a black pixel at (10, 20); rows padded to 304 bytes."""
    rowstride = WIDTH * 3 + 4
    data = bytearray([255] * rowstride * HEIGHT)
    start = 20 * rowstride + 10 * 3
    data[start : start + 3] = b"\0\0\0"
    return bytes(data)


def word(text: str, left: int, top: int, line: int = 1, number: int = 1) -> str:
    return f"5\t1\t1\t1\t{line}\t{number}\t{left}\t{top}\t40\t20\t95\t{text}\n"


def test_the_region_is_cut_scaled_and_padded() -> None:
    png, plan = picture(screen(), WIDTH, HEIGHT, WIDTH * 3 + 4, 3, Region(10, 20, 30, 10))
    image = Image.open(io.BytesIO(png))
    assert image.mode == "L"
    assert image.size == (plan.width, plan.height) == (90, 80)
    assert (plan.margin_x, plan.margin_y) == (0, 8)
    # The corner's color fills the margin: the black pixel at (10, 20).
    assert image.getpixel((0, 0)) == 0
    assert image.getpixel((45, 20)) == 255


def test_light_text_on_a_dark_ground_is_turned_over() -> None:
    dark = bytes(len(screen()))
    png, _plan = picture(dark, WIDTH, HEIGHT, WIDTH * 3 + 4, 3, Region(0, 0, 50, 50))
    assert Image.open(io.BytesIO(png)).getpixel((10, 10)) == 255


def test_colored_text_stands_apart_from_its_ground() -> None:
    rowstride = WIDTH * 3 + 4
    # Red text on a dark ground, a terminal's error: as dark as black text once read.
    data = bytearray(rowstride * HEIGHT)
    data[0:3] = bytes((205, 49, 49))
    png, _plan = picture(bytes(data), WIDTH, HEIGHT, rowstride, 3, Region(0, 0, 50, 50))
    picture_read = Image.open(io.BytesIO(png))
    assert picture_read.getpixel((1, 1)) == 255 - 205
    # Blue text on a light ground, a link.
    light = bytearray([255] * rowstride * HEIGHT)
    light[0:3] = bytes((26, 115, 232))
    png, _plan = picture(bytes(light), WIDTH, HEIGHT, rowstride, 3, Region(0, 0, 50, 50))
    assert Image.open(io.BytesIO(png)).getpixel((1, 1)) == 26


def test_the_text_comes_back_in_the_form_asked() -> None:
    tsv = TSV_HEAD + word("one", 0, 0) + word("two", 50, 0, number=2) + word("three", 0, 30, 2)
    seen: list[str] = []

    def run(png: bytes, language: str) -> str:
        seen.append(language)
        return tsv

    def reading(mode: str, point: tuple[int, int] = (0, 0)) -> str:
        request = Request(Region(0, 0, 100, 60), mode, "hun", point)
        return read(request, screen(), (WIDTH, HEIGHT), WIDTH * 3 + 4, 3, run)

    assert reading("text") == "one two\nthree"
    assert reading("single") == "one two three"
    assert reading("table") == "one two\nthree"
    # The scale is 3: (25, 5) on the screen is (75, 15) in tesseract's picture.
    assert reading("word", (25, 5)) == "two"
    assert seen == ["hun"] * 4


def test_a_click_reads_a_band_of_its_monitor() -> None:
    monitor = Region(100, 0, 800, 600)
    assert word_region(300, 300, monitor) == Region(100, 240, 800, 120)
    assert word_region(300, 10, monitor) == Region(100, 0, 800, 70)


def test_the_settings_button_opens_the_checkout_s_settings() -> None:
    command, folder = settings_command("textextractor")
    assert command == [sys.executable, "-m", "tuxtoys.settings", "--page", "textextractor"]
    assert folder is not None
    assert (Path(folder) / "tuxtoys" / "settings").is_dir()
