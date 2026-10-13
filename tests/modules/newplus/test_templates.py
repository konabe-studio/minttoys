from pathlib import Path

import pytest

from tuxtoys.modules.newplus import templates
from tuxtoys.modules.newplus.templates import BadName, EmptyName, TakenName, Template


def user_dirs(tmp_path: Path, line: str) -> tuple[Path, Path]:
    home, config = tmp_path / "home", tmp_path / "config"
    config.mkdir(parents=True)
    (config / "user-dirs.dirs").write_text(
        f'# written by xdg-user-dirs-update\nXDG_DESKTOP_DIR="$HOME/Desktop"\n{line}\n',
        encoding="utf-8",
    )
    return home, config


def test_the_folder_from_user_dirs(tmp_path: Path) -> None:
    home, config = user_dirs(tmp_path, 'XDG_TEMPLATES_DIR="$HOME/Sablonok"')
    assert templates.templates_dir(home, config) == home / "Sablonok"


def test_an_absolute_folder(tmp_path: Path) -> None:
    home, config = user_dirs(tmp_path, f'XDG_TEMPLATES_DIR="{tmp_path}/elsewhere"')
    assert templates.templates_dir(home, config) == tmp_path / "elsewhere"


def test_the_home_folder_means_none(tmp_path: Path) -> None:
    home, config = user_dirs(tmp_path, 'XDG_TEMPLATES_DIR="$HOME/"')
    assert templates.templates_dir(home, config) is None


def test_no_user_dirs_means_none(tmp_path: Path) -> None:
    assert templates.templates_dir(tmp_path, tmp_path / "nothing") is None


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    path = tmp_path / "Templates"
    path.mkdir()
    (path / "Note.txt").write_text("", encoding="utf-8")
    (path / "letter.odt").write_text("", encoding="utf-8")
    (path / ".hidden").write_text("", encoding="utf-8")
    (path / "Office").mkdir()
    return path


def test_templates_by_name_without_hidden_ones(folder: Path) -> None:
    assert [(t.name, t.folder) for t in templates.templates(folder)] == [
        ("letter.odt", False),
        ("Note.txt", False),
        ("Office", True),
    ]


def test_a_missing_folder_has_no_templates(tmp_path: Path) -> None:
    assert templates.templates(tmp_path / "missing") == []


@pytest.mark.parametrize(
    ("name", "free"),
    [
        ("new.txt", "new.txt"),
        ("Note.txt", "Note (2).txt"),
        ("Office", "Office (2)"),
        (".hidden", ".hidden (2)"),
    ],
)
def test_free_name(folder: Path, name: str, free: str) -> None:
    assert templates.free_name(folder, name) == free


def test_free_name_counts_on(folder: Path) -> None:
    (folder / "Note (2).txt").write_text("", encoding="utf-8")
    assert templates.free_name(folder, "Note.txt") == "Note (3).txt"


def test_add_copies_a_file_under_a_free_name(folder: Path, tmp_path: Path) -> None:
    source = tmp_path / "Note.txt"
    source.write_text("hello", encoding="utf-8")
    added = templates.add(folder, source)
    assert added == folder / "Note (2).txt"
    assert added.read_text(encoding="utf-8") == "hello"
    assert source.exists()


def test_add_copies_a_folder(folder: Path, tmp_path: Path) -> None:
    source = tmp_path / "Project"
    (source / "docs").mkdir(parents=True)
    added = templates.add(folder, source)
    assert (added / "docs").is_dir()


def test_add_makes_the_folder(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("", encoding="utf-8")
    assert templates.add(tmp_path / "Templates", source).exists()


def note(folder: Path) -> Template:
    return Template("Note.txt", folder / "Note.txt", False)


def test_check_name_trims(folder: Path) -> None:
    assert templates.check_name(folder, note(folder), "  Memo.txt ") == "Memo.txt"


def test_check_name_keeps_its_own(folder: Path) -> None:
    assert templates.check_name(folder, note(folder), "Note.txt") == "Note.txt"


@pytest.mark.parametrize(
    ("name", "error"),
    [("  ", EmptyName), ("a/b", BadName), ("..", BadName), ("letter.odt", TakenName)],
)
def test_check_name_refuses(folder: Path, name: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        templates.check_name(folder, note(folder), name)
