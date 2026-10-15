import pytest

from tuxtoys.modules.textextractor import tesseract
from tuxtoys.modules.textextractor.layout import Box

LANGS = (
    'List of available languages in "/usr/share/tesseract-ocr/5/tessdata/" (4):\n'
    "eng\nhun\nosd\ndeu\n"
)

TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t400\t100\t-1\t\n"
    "4\t1\t1\t1\t1\t0\t10\t10\t200\t20\t-1\t\n"
    "5\t1\t1\t1\t1\t1\t10\t10\t60\t20\t96.5\tHello\n"
    "5\t1\t1\t1\t1\t2\t80\t10\t60\t20\t95.1\tvilág\n"
    "5\t1\t1\t1\t2\t1\t10\t40\t60\t20\t91.0\tagain\n"
    "5\t1\t2\t1\t1\t1\t10\t80\t60\t20\t-1\t \n"
    "5\t1\t2\t1\t1\t2\t10\t80\t60\t20\t90.0\tlast\n"
)


def test_the_languages_skip_the_heading_and_tesseract_s_own_data() -> None:
    assert tesseract.parse_languages(LANGS) == ["deu", "eng", "hun"]
    assert tesseract.name("hun") == "Magyar"
    assert tesseract.name("xyz") == "xyz"


def test_the_tsv_gives_words_by_line_in_reading_order() -> None:
    lines = tesseract.parse_tsv(TSV)
    assert [line.text for line in lines] == ["Hello világ", "again", "last"]
    assert lines[0].words[1].box == Box(80, 10, 60, 20)
    assert tesseract.parse_tsv("") == []


@pytest.mark.parametrize(
    ("environ", "short"),
    [
        ({"LANGUAGE": "hu:en", "LANG": "en_US.UTF-8"}, "hu"),
        ({"LANG": "hu_HU.UTF-8"}, "hu"),
        ({"LC_ALL": "C", "LANG": "de_DE.UTF-8"}, "de"),
        ({"LANG": "zh_TW.UTF-8"}, "zh_TW"),
        ({}, "en"),
    ],
    ids=["language", "lang", "c-skipped", "taiwan", "none"],
)
def test_the_desktop_language(environ: dict, short: str) -> None:
    assert tesseract.desktop_language(environ) == short


def test_the_language_picked() -> None:
    hungarian = {"LANG": "hu_HU.UTF-8"}
    assert tesseract.pick("deu", ["deu", "eng", "hun"], hungarian) == "deu"
    assert tesseract.pick("", ["deu", "eng", "hun"], hungarian) == "hun"
    assert tesseract.pick("fra", ["deu", "eng"], hungarian) == "eng"
    assert tesseract.pick("", ["deu"], hungarian) == "deu"
    assert tesseract.pick("", [], hungarian) == ""


def test_the_command_reads_stdin_and_writes_tsv() -> None:
    assert tesseract.command("/usr/bin/tesseract", "hun") == [
        "/usr/bin/tesseract",
        "stdin",
        "stdout",
        "-l",
        "hun",
        "--psm",
        "6",
        "tsv",
    ]


def test_the_plan_scales_and_pads_small_regions() -> None:
    plan = tesseract.plan(200, 20)
    assert (plan.scale, plan.width, plan.height) == (3.0, 600, 80)
    assert (plan.margin_x, plan.margin_y) == (0, 8)
    assert plan.back(300, 38) == (100, 10)
    assert tesseract.plan(2500, 1000).scale == 2.0
    big = tesseract.plan(3840, 2160)
    assert (big.scale, big.width, big.height) == (1.0, 3840, 2160)
