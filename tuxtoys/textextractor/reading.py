"""From a region of the frozen screen to the text Text Extractor copies: the picture made
ready for tesseract (larger, with a margin when small), tesseract's answer, and the text
in the form asked for. No GTK: the screen comes as raw pixels.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageOps, ImageStat

from tuxtoys.modules.textextractor import layout, tesseract

# What a click without a drag reads around itself, above and below, to find its word.
WORD_BAND = 60
# A region darker than this on average, of 255, is light text on a dark ground.
DARK = 128


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Request:
    """A region to read, how to give its text back ("text", "single", "table", or "word"
    for the word at `point`), and in which language.
    """

    region: Region
    mode: str
    language: str
    point: tuple[int, int] = (0, 0)


def word_region(x: int, y: int, monitor: Region) -> Region:
    """The band of the monitor around a click, as wide as the monitor."""
    top = max(monitor.y, y - WORD_BAND)
    bottom = min(monitor.y + monitor.height, y + WORD_BAND)
    return Region(monitor.x, top, monitor.width, max(1, bottom - top))


def picture(
    pixels: bytes, width: int, height: int, rowstride: int, channels: int, region: Region
) -> tuple[bytes, tesseract.Plan]:
    """The region cut from the screen's pixels and made ready for tesseract, as PNG: in
    grey, dark text on a light ground, which is what tesseract reads best, so light text
    on a dark theme or terminal is turned over; larger; with a margin when small.

    Each pixel's grey is its brightest channel on a dark ground and its darkest on a light
    one, so colored text, a terminal's red error or a blue link, stands apart from the
    ground as well as black or white text does.
    """
    mode = "RGBA" if channels == 4 else "RGB"
    screen = Image.frombuffer(mode, (width, height), pixels, "raw", mode, rowstride, 1)
    cut = screen.crop(
        (region.x, region.y, region.x + region.width, region.y + region.height)
    ).convert("RGB")
    red, green, blue = cut.split()
    if ImageStat.Stat(cut.convert("L")).mean[0] < DARK:
        cut = ImageOps.invert(ImageChops.lighter(ImageChops.lighter(red, green), blue))
    else:
        cut = ImageChops.darker(ImageChops.darker(red, green), blue)
    plan = tesseract.plan(cut.width, cut.height)
    scaled = cut.resize(
        (round(cut.width * plan.scale), round(cut.height * plan.scale)),
        Image.Resampling.BICUBIC,
    )
    canvas = Image.new("L", (plan.width, plan.height), cut.getpixel((0, 0)))
    canvas.paste(scaled, (plan.margin_x, plan.margin_y))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue(), plan


def text_of(lines: list[layout.Line], request: Request, plan: tesseract.Plan) -> str:
    if request.mode == "single":
        return layout.single_line(lines, request.language)
    if request.mode == "table":
        return layout.table(layout.cells(lines), request.language)
    if request.mode == "word":
        x = (request.point[0] - request.region.x) * plan.scale + plan.margin_x
        y = (request.point[1] - request.region.y) * plan.scale + plan.margin_y
        return layout.word_at(lines, x, y)
    return layout.document(lines, request.language)


def read(
    request: Request,
    pixels: bytes,
    size: tuple[int, int],
    rowstride: int,
    channels: int,
    run: Callable[[bytes, str], str] = tesseract.run,
) -> str:
    """The text of the region, in the form asked for; "" when there is none. OSError or
    RuntimeError from tesseract go through.
    """
    png, plan = picture(pixels, *size, rowstride, channels, request.region)
    lines = tesseract.parse_tsv(run(png, request.language))
    return text_of(lines, request, plan)
