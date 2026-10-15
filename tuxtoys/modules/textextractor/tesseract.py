"""Text Extractor's reading of the screen, through the tesseract command (Debian's
tesseract-ocr): the languages installed, the command line, and its TSV output read back
into lines of words with their places. Free of GTK; only `run` and `installed` start a
process.
"""

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tuxtoys.modules.textextractor.layout import Box, Line, Word

COMMAND = "tesseract"
# Tesseract's own data, not languages to read: orientation and script detection, maths.
NOT_LANGUAGES = {"osd", "equ"}
TIMEOUT = 60

# PowerToys reads a region 1.5 times as large; tesseract does better larger still on
# screen text, which is small for it: its letters want to be some 20 to 30 pixels tall.
# The largest scale that fits is taken. Small regions get a margin, as PowerToys gives them.
SCALES = (3.0, 2.0, 1.0)
MOST_PIXELS = 6000
LEAST_SIZE = 64
MARGIN = 8


@dataclass(frozen=True)
class Language:
    code: str  # tesseract's, the data file's name: hun, eng, chi_sim
    short: str  # ISO 639-1, as the desktop's locale names it: hu, en, zh
    name: str  # in the language itself, as PowerToys lists them


# The languages Debian packages as tesseract-ocr-<code>, the common ones by name; any
# other installed language shows by its code.
KNOWN = (
    Language("eng", "en", "English"),
    Language("hun", "hu", "Magyar"),
    Language("deu", "de", "Deutsch"),
    Language("fra", "fr", "Français"),
    Language("spa", "es", "Español"),
    Language("ita", "it", "Italiano"),
    Language("por", "pt", "Português"),
    Language("nld", "nl", "Nederlands"),
    Language("pol", "pl", "Polski"),
    Language("ces", "cs", "Čeština"),
    Language("slk", "sk", "Slovenčina"),
    Language("slv", "sl", "Slovenščina"),
    Language("hrv", "hr", "Hrvatski"),
    Language("srp", "sr", "Српски"),
    Language("ron", "ro", "Română"),
    Language("bul", "bg", "Български"),
    Language("rus", "ru", "Русский"),
    Language("ukr", "uk", "Українська"),
    Language("ell", "el", "Ελληνικά"),
    Language("tur", "tr", "Türkçe"),
    Language("swe", "sv", "Svenska"),
    Language("nor", "nb", "Norsk"),
    Language("dan", "da", "Dansk"),
    Language("fin", "fi", "Suomi"),
    Language("est", "et", "Eesti"),
    Language("lav", "lv", "Latviešu"),
    Language("lit", "lt", "Lietuvių"),
    Language("cat", "ca", "Català"),
    Language("vie", "vi", "Tiếng Việt"),
    Language("ind", "id", "Bahasa Indonesia"),
    Language("ara", "ar", "العربية"),
    Language("heb", "he", "עברית"),
    Language("hin", "hi", "हिन्दी"),
    Language("tha", "th", "ไทย"),
    Language("kor", "ko", "한국어"),
    Language("jpn", "ja", "日本語"),
    Language("chi_sim", "zh", "简体中文"),
    Language("chi_tra", "zh_TW", "繁體中文"),
)
BY_CODE = {language.code: language for language in KNOWN}


def name(code: str) -> str:
    known = BY_CODE.get(code)
    return known.name if known else code


def parse_languages(output: str) -> list[str]:
    """`tesseract --list-langs`' answer: a heading line, then a code a line."""
    codes = []
    for line in output.splitlines():
        code = line.strip()
        if not code or " " in code or code.endswith(":") or code in NOT_LANGUAGES:
            continue
        codes.append(code)
    return sorted(codes, key=lambda code: name(code).casefold())


def installed() -> list[str] | None:
    """The languages tesseract can read, or None without tesseract."""
    program = shutil.which(COMMAND)
    if program is None:
        return None
    try:
        done = subprocess.run(  # the system's tesseract, by its full path
            [program, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_languages(done.stdout + done.stderr)


def desktop_language(environ: Mapping[str, str] = os.environ) -> str:
    """The desktop's language as ISO 639-1 ("hu"), from LANGUAGE, LC_ALL, LC_MESSAGES or
    LANG, the way gettext looks; "zh_TW" kept whole, as tesseract tells it apart.
    """
    for key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = environ.get(key, "")
        first = value.split(":")[0].split(".")[0].split("@")[0]
        if first and first not in ("C", "POSIX"):
            return first if first == "zh_TW" else first.split("_")[0]
    return "en"


def pick(wanted: str, available: Sequence[str], environ: Mapping[str, str] = os.environ) -> str:
    """The language to read in: the one set if installed, else the desktop's, else
    English, else whatever there is; "" when nothing is installed.
    """
    if wanted in available:
        return wanted
    short = desktop_language(environ)
    for language in KNOWN:
        if language.short == short and language.code in available:
            return language.code
    if "eng" in available:
        return "eng"
    return available[0] if available else ""


def command(program: str, language: str) -> list[str]:
    """Reads a PNG on stdin, writes TSV on stdout. Page segmentation 6, one block of
    text: line by line across the whole region, as PowerToys reads it. Tesseract's own
    default looks for columns and reads them one after the other, which mixes up a
    selection of screen text.
    """
    return [program, "stdin", "stdout", "-l", language, "--psm", "6", "tsv"]


def run(png: bytes, language: str) -> str:
    """Tesseract's TSV for a picture. OSError when it cannot run, RuntimeError with its
    message when it fails.
    """
    program = shutil.which(COMMAND)
    if program is None:
        raise OSError(COMMAND)
    done = subprocess.run(  # the system's tesseract, by its full path
        command(program, language),
        input=png,
        capture_output=True,
        timeout=TIMEOUT,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr.decode("utf-8", "replace").strip())
    return done.stdout.decode("utf-8", "replace")


def parse_tsv(output: str) -> list[Line]:
    """Tesseract's TSV as lines of words in reading order. A word is a row of level 5;
    its block, paragraph and line numbers tell which line it is on.
    """
    lines: dict[tuple[int, int, int, int], list[Word]] = {}
    for row in output.splitlines()[1:]:
        fields = row.split("\t")
        if len(fields) < 12 or fields[0] != "5":
            continue
        text = "\t".join(fields[11:]).strip()
        if not text:
            continue
        try:
            page, block, paragraph, line = (int(field) for field in fields[1:5])
            left, top, width, height = (float(field) for field in fields[6:10])
        except ValueError:
            continue
        lines.setdefault((page, block, paragraph, line), []).append(
            Word(text, Box(left, top, width, height))
        )
    return [Line(tuple(words)) for _key, words in sorted(lines.items())]


@dataclass(frozen=True)
class Plan:
    """How a region goes to tesseract: scaled by `scale`, placed `margin` pixels in on a
    canvas `width` by `height` filled with the region's corner color.
    """

    scale: float
    width: int
    height: int
    margin_x: int
    margin_y: int

    def back(self, x: float, y: float) -> tuple[float, float]:
        """A point of tesseract's picture in the region's own pixels."""
        return (x - self.margin_x) / self.scale, (y - self.margin_y) / self.scale


def plan(width: int, height: int) -> Plan:
    """PowerToys' BitmapPreprocessor, with tesseract's larger scale where it fits."""
    scale = next((s for s in SCALES if max(width, height) * s <= MOST_PIXELS), 1.0)
    scaled_width = max(1, round(width * scale))
    scaled_height = max(1, round(height * scale))
    margin_x = MARGIN if scaled_width < LEAST_SIZE else 0
    margin_y = MARGIN if scaled_height < LEAST_SIZE else 0
    out_width = max(scaled_width, LEAST_SIZE) + 2 * margin_x if margin_x else scaled_width
    out_height = max(scaled_height, LEAST_SIZE) + 2 * margin_y if margin_y else scaled_height
    return Plan(scale, out_width, out_height, margin_x, margin_y)
