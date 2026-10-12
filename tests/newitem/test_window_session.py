"""New from template's window with real GTK, on folders of the test's own. Needs a display:
xvfb in CI, the desktop otherwise.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from minttoys.modules.newplus.create import Naming  # noqa: E402
from minttoys.newitem.window import NewItemWindow, TemplateRow  # noqa: E402

NOW = datetime(2026, 3, 5, 7, 8, 9, tzinfo=ZoneInfo("Europe/Budapest"))


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    templates = tmp_path / "Templates"
    (templates / "Project").mkdir(parents=True)
    (templates / "Project" / "README.md").write_text("r", encoding="utf-8")
    (templates / "2. Note $YYYY.txt").write_text("n", encoding="utf-8")
    (templates / "10. Letter.odt").write_text("l", encoding="utf-8")
    target = tmp_path / "Work"
    target.mkdir()
    return templates, target


def open_window(
    folders: tuple[Path, Path], naming: Naming | None = None
) -> tuple[NewItemWindow, list[Path]]:
    made: list[Path] = []
    templates, target = folders
    window = NewItemWindow(None, target, templates, naming or Naming(), made.append)
    return window, made


def shown(window: NewItemWindow) -> list[str]:
    return [row.template.name for row in window.list.get_children() if isinstance(row, TemplateRow)]


def test_folders_first_then_by_number(folders: tuple[Path, Path]) -> None:
    window, _made = open_window(folders)
    assert shown(window) == ["Project", "2. Note $YYYY.txt", "10. Letter.odt"]
    assert window.entry.get_text() == "Project"
    assert window.create.get_sensitive()


def test_the_name_offered_follows_the_settings(folders: tuple[Path, Path]) -> None:
    naming = Naming(variables=True, hide_digits=True, now=NOW, environ={})
    window, _made = open_window(folders, naming)
    window.list.select_row(window.list.get_row_at_index(1))
    assert window.entry.get_text() == "Note 2026.txt"


def test_create_a_file(folders: tuple[Path, Path]) -> None:
    window, made = open_window(folders)
    window.list.select_row(window.list.get_row_at_index(2))
    window.entry.set_text("Dear Anna.odt")
    window.make()
    _templates, target = folders
    assert made == [target / "Dear Anna.odt"]
    assert (target / "Dear Anna.odt").read_text(encoding="utf-8") == "l"


def test_a_taken_name_is_said_and_not_overwritten(folders: tuple[Path, Path]) -> None:
    _templates, target = folders
    (target / "Mine.txt").write_text("mine", encoding="utf-8")
    window, made = open_window(folders)
    window.entry.set_text("Mine.txt")
    assert not window.create.get_sensitive()
    assert "Mine.txt" in window.problem.get_text()
    window.make()
    assert made == []
    assert (target / "Mine.txt").read_text(encoding="utf-8") == "mine"


def test_a_free_name_is_offered_when_the_template_name_is_taken(
    folders: tuple[Path, Path],
) -> None:
    _templates, target = folders
    (target / "Project").mkdir()
    window, _made = open_window(folders)
    assert window.entry.get_text() == "Project (2)"


def test_without_a_templates_folder_it_says_so(tmp_path: Path) -> None:
    window = NewItemWindow(None, tmp_path, None, Naming())
    assert shown(window) == []
    assert "no templates folder" in window.nothing.get_text()
    assert not window.create.get_sensitive()
