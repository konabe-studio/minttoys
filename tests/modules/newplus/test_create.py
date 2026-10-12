import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.newplus import names
from minttoys.modules.newplus.create import Naming, check, make, ordered
from minttoys.modules.newplus.templates import BadName, EmptyName, TakenName, Template

NOW = datetime(2026, 3, 5, 7, 8, 9, 123456, tzinfo=ZoneInfo("Europe/Budapest"))


def template(folder: Path, name: str, content: str = "x") -> Template:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Template(name, path, False)


@pytest.mark.parametrize(
    ("text", "made"),
    [
        ("$YYYY-$MM-$DD $hh.$mm.$ss", "2026-03-05 07.08.09"),
        ("$YY $Y $M $D $h $m $s", "26 6 3 5 7 8 9"),
        ("$fff $ff $f", "123 12 1"),
        ("$MMMM $MMM $DDDD $DDD", "March Mar Thursday Thu"),
        ("in $PARENT_FOLDER_NAME", "in Work"),
        ("by %USER%, %user%", "by ben, ben"),
        ("%NOT_SET% and $yyyy", "%NOT_SET% and $yyyy"),
        ("%PATHLIKE%", "a b"),
    ],
)
def test_expand(text: str, made: str) -> None:
    environ = {"USER": "ben", "PATHLIKE": "a/b"}
    assert names.expand(text, NOW, "Work", environ) == made


def test_a_value_put_in_is_not_read_again() -> None:
    assert names.expand("%X%", NOW, "Work", {"X": "$YYYY"}) == "$YYYY"


@pytest.mark.parametrize(
    ("name", "folder", "shown"),
    [
        # PowerToys' own table, from its template_item.cpp.
        ("01. First entry.txt", False, "First entry.txt"),
        ("02. Second entry", True, "Second entry"),
        ("03 Third entry", True, "Third entry"),
        ("04 Fourth entry.txt", False, "Fourth entry.txt"),
        ("05.Fifth entry.txt", False, "Fifth entry.txt"),
        ("001231", True, "001231"),
        ("001231.txt", False, "001231.txt"),
        ("13. 0123456789012345.txt", False, "0123456789012345.txt"),
        # And a few more.
        ("0123.Name", True, "Name"),
        ("01 .Name.txt", False, "Name.txt"),
        ("01Name.txt", False, "Name.txt"),
        ("02 - Invoice.ods", False, "- Invoice.ods"),
        ("Plain.txt", False, "Plain.txt"),
    ],
)
def test_without_leading_digits(name: str, folder: bool, shown: str) -> None:
    assert names.without_leading_digits(name, folder) == shown


def test_order_folders_first_numbers_by_value(tmp_path: Path) -> None:
    found = [
        Template("10. Invoice.ods", tmp_path, False),
        Template("2. Letter.odt", tmp_path, False),
        Template("b.txt", tmp_path, False),
        Template("Project", tmp_path, True),
    ]
    assert [t.name for t in ordered(found)] == [
        "Project",
        "2. Letter.odt",
        "10. Invoice.ods",
        "b.txt",
    ]


def test_the_name_offered(tmp_path: Path) -> None:
    letter = Template("1. Letter $YYYY.odt", tmp_path, False)
    target = tmp_path / "Work"
    assert Naming().offered(letter, target) == "1. Letter $YYYY.odt"
    assert Naming(hide_digits=True).offered(letter, target) == "Letter $YYYY.odt"
    both = Naming(variables=True, hide_digits=True, now=NOW, environ={})
    assert both.offered(letter, target) == "Letter 2026.odt"


def test_check(tmp_path: Path) -> None:
    (tmp_path / "taken.txt").write_text("", encoding="utf-8")
    assert check(tmp_path, "  new.txt ") == "new.txt"
    with pytest.raises(EmptyName):
        check(tmp_path, " ")
    with pytest.raises(BadName):
        check(tmp_path, "a/b")
    with pytest.raises(BadName):
        check(tmp_path, "..")
    with pytest.raises(TakenName):
        check(tmp_path, "taken.txt")


def test_make_a_file(tmp_path: Path) -> None:
    letter = template(tmp_path / "Templates", "Letter.odt", "dear")
    target = tmp_path / "Work"
    target.mkdir()
    made = make(letter, target, "To Anna.odt", Naming())
    assert made == target / "To Anna.odt"
    assert made.read_text(encoding="utf-8") == "dear"
    assert sorted(os.listdir(target)) == ["To Anna.odt"]  # nothing hidden left behind


def test_make_never_overwrites(tmp_path: Path) -> None:
    letter = template(tmp_path / "Templates", "Letter.odt", "dear")
    target = tmp_path / "Work"
    (target / "Letter.odt").parent.mkdir()
    (target / "Letter.odt").write_text("mine", encoding="utf-8")
    with pytest.raises(TakenName):
        make(letter, target, "Letter.odt", Naming())
    assert (target / "Letter.odt").read_text(encoding="utf-8") == "mine"
    assert sorted(os.listdir(target)) == ["Letter.odt"]


def test_make_a_folder_with_its_names_replaced(tmp_path: Path) -> None:
    source = tmp_path / "Templates" / "Project"
    (source / "notes $PARENT_FOLDER_NAME").mkdir(parents=True)
    (source / "notes $PARENT_FOLDER_NAME" / "$YYYY.txt").write_text("n", encoding="utf-8")
    (source / "README for $PARENT_FOLDER_NAME.md").write_text("r", encoding="utf-8")
    project = Template("Project", source, True)
    target = tmp_path / "Work"
    target.mkdir()
    naming = Naming(variables=True, now=NOW, environ={})
    made = make(project, target, "Garden", naming)
    assert (made / "README for Garden.md").read_text(encoding="utf-8") == "r"
    assert (made / "notes Garden" / "2026.txt").read_text(encoding="utf-8") == "n"
    assert sorted(os.listdir(target)) == ["Garden"]


def test_a_folder_keeps_its_names_with_variables_off(tmp_path: Path) -> None:
    source = tmp_path / "Templates" / "Project"
    source.mkdir(parents=True)
    (source / "$YYYY.txt").write_text("", encoding="utf-8")
    target = tmp_path / "Work"
    target.mkdir()
    made = make(Template("Project", source, True), target, "Project", Naming())
    assert os.listdir(made) == ["$YYYY.txt"]


def test_a_folder_is_not_put_over_another(tmp_path: Path) -> None:
    source = tmp_path / "Templates" / "Project"
    source.mkdir(parents=True)
    target = tmp_path / "Work"
    (target / "Project").mkdir(parents=True)
    with pytest.raises(TakenName):
        make(Template("Project", source, True), target, "Project", Naming())
    assert sorted(os.listdir(target)) == ["Project"]
