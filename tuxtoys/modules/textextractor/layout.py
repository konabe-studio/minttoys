"""What Text Extractor makes of the words tesseract found: the text as it reads, on one
line, as a table, or the one word clicked. Ported from PowerToys' OcrTextFormatter and
TableTextFormatter, so the result reads the same. Free of GTK.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

# PowerToys took six pixels off each cell before laying it on rows and columns, so that
# small overlaps between the boxes do not merge two cells into one.
BOUNDS_TOLERANCE = 6.0
LEAST_FOR_TOLERANCE = 10.0


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    def union(self, other: "Box") -> "Box":
        left, top = min(self.left, other.left), min(self.top, other.top)
        right, bottom = max(self.right, other.right), max(self.bottom, other.bottom)
        return Box(left, top, right - left, bottom - top)

    def overlap(self, other: "Box") -> float:
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        return width * height if width > 0 and height > 0 else 0.0

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass(frozen=True)
class Word:
    text: str
    box: Box


@dataclass(frozen=True)
class Line:
    words: tuple[Word, ...]

    @property
    def box(self) -> Box:
        box = self.words[0].box
        for word in self.words[1:]:
            box = box.union(word.box)
        return box

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


def uses_spaces(language: str) -> bool:
    """Whether the language puts spaces between words: not Chinese or Japanese. `language`
    is tesseract's code, or several joined with "+", the first deciding.
    """
    first = language.split("+")[0]
    return not first.startswith(("chi", "jpn"))


def document(lines: Sequence[Line], language: str) -> str:
    """The lines as they read, one under the other."""
    spaces = uses_spaces(language)
    texts = [line.text if spaces else join_words(line.words) for line in lines]
    return "\n".join(texts).strip()


def single_line(lines: Sequence[Line], language: str) -> str:
    """Every line on one, with single spaces between."""
    if uses_spaces(language):
        return re.sub(" {2,}", " ", document(lines, language).replace("\n", " ")).strip()
    return join_words([word for line in lines for word in line.words]).strip()


def table(cells: Sequence[Line], language: str) -> str:
    """The cells laid out in rows and columns, by where they are: a tab between columns, a
    line for each row, an empty cell kept as an empty column, trailing ones dropped.
    """
    if not cells:
        return ""
    bounds = cells[0].box
    for cell in cells[1:]:
        bounds = bounds.union(cell.box)
    rows = _segments(cells, bounds, horizontal=True)
    columns = _segments(cells, bounds, horizontal=False)
    values = [["" for _column in columns] for _row in rows]
    spaces = uses_spaces(language)
    for cell in cells:
        row = _best(rows, cell.box)
        column = _best(columns, cell.box)
        text = cell.text if spaces else join_words(cell.words)
        if values[row][column]:
            values[row][column] += (" " if spaces else "") + text
        else:
            values[row][column] = text
    output = []
    for row_values in values:
        while row_values and not row_values[-1]:
            row_values.pop()
        output.append("\t".join(row_values))
    return "\n".join(output)


def _segments(cells: Sequence[Line], bounds: Box, horizontal: bool) -> list[Box]:
    spans = []
    for cell in cells:
        box = cell.box
        start, end = (box.top, box.bottom) if horizontal else (box.left, box.right)
        if end <= start:
            continue
        inset = BOUNDS_TOLERANCE / 2 if end - start > LEAST_FOR_TOLERANCE else 0.0
        spans.append((start + inset, end - inset))
    if not spans:
        return [bounds]
    spans.sort()
    segments = []
    start, end = spans[0]
    for span_start, span_end in spans[1:]:
        if span_start >= end:
            segments.append(_segment(bounds, horizontal, start, end))
            start, end = span_start, span_end
        else:
            end = max(end, span_end)
    segments.append(_segment(bounds, horizontal, start, end))
    return segments


def _segment(bounds: Box, horizontal: bool, start: float, end: float) -> Box:
    if horizontal:
        return Box(bounds.left, start, bounds.width, end - start)
    return Box(start, bounds.top, end - start, bounds.height)


def _best(segments: Sequence[Box], box: Box) -> int:
    best, best_area = 0, -1.0
    for index, segment in enumerate(segments):
        area = segment.overlap(box)
        if area > best_area:
            best, best_area = index, area
    return best


def cells(lines: Sequence[Line]) -> list[Line]:
    """The lines split where the gap between two words is wider than the line is tall.
    Tesseract reads a table's row as one line; PowerToys' engine gave it cell by cell.
    """
    found = []
    for line in lines:
        height = max(word.box.height for word in line.words)
        current = [line.words[0]]
        for word in line.words[1:]:
            if word.box.left - current[-1].box.right > height:
                found.append(Line(tuple(current)))
                current = []
            current.append(word)
        found.append(Line(tuple(current)))
    return found


def word_at(lines: Sequence[Line], x: float, y: float) -> str:
    """The word under a point, or ""."""
    for line in lines:
        for word in line.words:
            if word.box.contains(x, y):
                return word.text
    return ""


# Punctuation that belongs to the word before it, and the CJK marks set tight.
SUFFIX = {",", ".", ":", ";", "!", "?", "%", chr(0x2025), chr(0x2026)}
TIGHT_CODES = (0x3001, 0x3002, 0x30FB, 0xFF01, 0xFF05, 0xFF0C, 0xFF0E, 0xFF1A, 0xFF1B)
TIGHT = {chr(code) for code in (*TIGHT_CODES, 0xFF1F, 0xFF61, 0xFF64, 0xFF65)}


def join_words(words: Sequence[Word]) -> str:
    """Words joined the way Chinese and Japanese text reads: a space only between words
    written in letters or digits, and none before closing or after opening punctuation.
    """
    text = ""
    previous: str | None = None
    for word in words:
        if not word.text:
            continue
        if previous is not None and _space_between(previous, word.text):
            text += " "
        text += word.text
        previous = word.text
    return text


def _space_between(left: str, right: str) -> bool:
    last, first = left[-1], right[0]
    left_category, right_category = unicodedata.category(last), unicodedata.category(first)
    punctuation_only = all(unicodedata.category(c).startswith("P") for c in right)
    if (
        left_category in ("Ps", "Pi")
        or right_category in ("Pe", "Pf")
        or (punctuation_only and first in SUFFIX)
        or last in TIGHT
        or first in TIGHT
        or right_category in ("Mn", "Mc", "Me")
    ):
        return False
    return _spaced(left) or _spaced(right)


def _spaced(text: str) -> bool:
    return any(unicodedata.category(c) in ("Lu", "Ll", "Lt", "Nd") for c in text)
