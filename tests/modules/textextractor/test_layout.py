from tuxtoys.modules.textextractor.layout import (
    Box,
    Line,
    Word,
    cells,
    document,
    join_words,
    single_line,
    table,
    word_at,
)


def cell(text: str, x: float, y: float, width: float = 40, height: float = 20) -> Line:
    """One word at (x, y), the size PowerToys' tests give their cells."""
    return Line((Word(text, Box(x, y, width, height)),))


def line(*words: tuple[str, float], y: float = 0, height: float = 20) -> Line:
    """Words at the given x positions on one line, each 30 wide."""
    return Line(tuple(Word(text, Box(x, y, 30, height)) for text, x in words))


# PowerToys' own TableTextFormatterTests.


def test_a_two_by_two_grid_uses_tabs_and_lines() -> None:
    grid = [cell("A1", 0, 0), cell("B1", 100, 0), cell("A2", 0, 40), cell("B2", 100, 40)]
    assert table(grid, "eng") == "A1\tB1\nA2\tB2"


def test_a_sparse_row_keeps_its_empty_column() -> None:
    grid = [cell("A1", 0, 0), cell("B1", 100, 0), cell("B2", 100, 40)]
    assert table(grid, "eng") == "A1\tB1\n\tB2"


def test_a_one_pixel_gap_or_overlap_keeps_rows_and_columns_apart() -> None:
    assert table([cell("A1", 0, 0), cell("A2", 0, 21)], "eng") == "A1\nA2"
    assert table([cell("A1", 0, 0), cell("B1", 41, 0)], "eng") == "A1\tB1"
    assert table([cell("A1", 0, 0), cell("A2", 0, 19)], "eng") == "A1\nA2"
    assert table([cell("A1", 0, 0), cell("B1", 39, 0)], "eng") == "A1\tB1"


def test_chinese_and_japanese_cells_join_without_spaces() -> None:
    assert table([cell("你", 0, 0), cell("好", 10, 0)], "chi_sim") == "你好"
    assert table([cell("你", 0, 0), cell("好", 10, 0)], "jpn") == "你好"


def test_no_cells_no_table() -> None:
    assert table([], "eng") == ""


def test_a_tesseract_line_splits_into_cells_at_wide_gaps() -> None:
    row = line(("Name", 0), ("of", 34), ("it", 68), ("42", 200))
    assert [c.text for c in cells([row])] == ["Name of it", "42"]
    rows = [row, line(("Other", 0), ("7", 200), y=40)]
    assert table(cells(rows), "eng") == "Name of it\t42\nOther\t7"


def test_the_document_reads_line_by_line() -> None:
    lines = [line(("Hello", 0), ("there", 40)), line(("again", 0), y=30)]
    assert document(lines, "hun") == "Hello there\nagain"
    assert single_line(lines, "hun") == "Hello there again"


def test_one_line_drops_repeated_spaces() -> None:
    lines = [line(("a", 0)), line(("  b", 0), y=30)]
    assert single_line(lines, "eng") == "a b"


def test_cjk_words_join_tight_but_latin_ones_spaced() -> None:
    def words(*texts: str) -> list[Word]:
        return [Word(text, Box(0, 0, 1, 1)) for text in texts]

    assert join_words(words("你", "好")) == "你好"
    assert join_words(words("Windows", "11")) == "Windows 11"
    assert join_words(words("你好", "Windows")) == "你好 Windows"
    assert join_words(words("(", "x", ")")) == "(x)"
    assert join_words(words("x", ",", "y")) == "x, y"
    assert join_words(words("你好", "。", "再见")) == "你好。再见"


def test_a_click_finds_its_word() -> None:
    lines = [line(("one", 0), ("two", 40))]
    assert word_at(lines, 45, 10) == "two"
    assert word_at(lines, 35, 10) == ""
