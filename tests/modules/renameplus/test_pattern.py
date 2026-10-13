from datetime import datetime
from random import Random
from zoneinfo import ZoneInfo

import pytest

from tuxtoys.modules.renameplus.pattern import (
    PatternError,
    Rules,
    change_case,
    fill,
    put_back,
    replaced,
    source_part,
)

WHEN = datetime(2020, 11, 2, 9, 5, 7, 123000, tzinfo=ZoneInfo("Europe/Budapest"))


def run(name: str, rules: Rules, index: int = 0, is_folder: bool = False) -> str | None:
    pattern = rules.compile()
    assert pattern is not None
    part = source_part(name, is_folder, rules.apply_to)
    new = replaced(part, pattern, rules, fill(rules.replace, rules, index, WHEN, Random(1)))
    return None if new is None else put_back(name, is_folder, rules.apply_to, new)


def test_match_all_occurrences_as_in_powertoys_docs() -> None:
    name = "powertoys-powerrename.txt"
    assert run(name, Rules("power", "super")) == "supertoys-powerrename.txt"
    assert run(name, Rules("power", "super", match_all=True)) == "supertoys-superrename.txt"


def test_case() -> None:
    assert run("Photo.jpg", Rules("photo", "pic")) == "pic.jpg"
    assert run("Photo.jpg", Rules("photo", "pic", case_sensitive=True)) is None


def test_plain_text_is_not_a_pattern() -> None:
    assert run("a.b(c)$1.txt", Rules(".b(c)$1", "x")) == "ax.txt"
    assert run("abc.txt", Rules("b", r"\1$0")) == r"a\1$0c.txt"


def test_regular_expression_groups() -> None:
    rules = Rules(r"(\d\d)-(\d\d)-(\d{4})", "$3-$2-$1", regex=True, match_all=True)
    assert run("29-03-2020 notes.txt", rules) == "2020-03-29 notes.txt"
    assert run("ab.txt", Rules("b", "[$0|$&|$$|$7]", regex=True)) == "a[b|b|$|$7].txt"
    assert run("abc.txt", Rules("^(.{1})(.*)", "$1foo$2", regex=True, apply_to="name")) == (
        "afoobc.txt"
    )


def test_bad_expression() -> None:
    with pytest.raises(PatternError):
        Rules("(", regex=True).compile()
    assert Rules("(").compile() is not None
    assert Rules("").compile() is None


def test_name_or_extension() -> None:
    assert run("txt.txt", Rules("txt", "NewName", apply_to="name")) == "NewName.txt"
    assert run("txt.txt", Rules("txt", "New", apply_to="extension")) == "txt.New"
    assert run("README", Rules("READ", "x", apply_to="extension")) is None
    assert run("a.tar.gz", Rules("tar", "zip", apply_to="name")) == "a.zip.gz"
    assert run(".bashrc", Rules("bash", "zsh", apply_to="name")) == ".zshrc"
    assert run("my.folder", Rules("folder", "x", apply_to="name"), is_folder=True) == "my.x"


def test_counters_as_in_powertoys_docs() -> None:
    rules = Rules("a", "Image_${padding=4;increment=2;start=10}_")
    made = [run(name, rules, index) for index, name in enumerate(["a.jpg", "ab.jpg", "abc.jpg"])]
    assert made == ["Image_0010_.jpg", "Image_0012_b.jpg", "Image_0014_bc.jpg"]
    assert run("a.jpg", Rules("a", "${}-${start=5}", enumerate=True), index=3) == "3-8.jpg"
    assert run("a.jpg", Rules("a", "${}", enumerate=False)) == "${}.jpg"
    assert run("a.jpg", Rules("a", "${start=-1;padding=3}"), index=0) == "-01.jpg"


def test_random_text() -> None:
    rules = Rules("a", "${rstringalnum=9}|${rstringalpha=4}|${rstringdigit=3}", randomize=True)
    made = run("a.txt", rules)
    assert made is not None
    alnum, alpha, digit = made.removesuffix(".txt").split("|")
    assert len(alnum) == 9
    assert alnum.isalnum()
    assert alnum.isascii()
    assert len(alpha) == 4
    assert alpha.isalpha()
    assert len(digit) == 3
    assert digit.isdigit()
    uuid = run("a.txt", Rules("a", "{${ruuidv4}}", randomize=True))
    assert uuid is not None
    assert len(uuid) == len("{12345678-1234-4234-8234-123456789012}.txt")
    assert uuid[15] == "4"
    # Without the box ticked it stays as typed, or counts when counters are on.
    assert run("a.txt", Rules("a", "${ruuidv4}", randomize=False, enumerate=False)) == (
        "${ruuidv4}.txt"
    )
    assert run("a.txt", Rules("a", "${ruuidv4}", randomize=False), index=2) == "2.txt"


def test_dates_as_in_powertoys_docs() -> None:
    assert run("powertoys.png", Rules("powertoys", "$MMM-$DD-$YY-powertoys")) == (
        "Nov-02-20-powertoys.png"
    )
    assert run("a.png", Rules("a", "$YYYY$MM$DD-$hh$mm$ss.$fff")) == "20201102-090507.123.png"
    # Dates come first, so $D is a date and not a group.
    assert run("ab.txt", Rules("(b)", "$1$D", regex=True)) == "ab2.txt"


@pytest.mark.parametrize(
    ("name", "text_case", "apply_to", "made"),
    [
        ("My File.TXT", "lower", "both", "my file.txt"),
        ("My File.TXT", "lower", "name", "my file.TXT"),
        ("My File.TXT", "upper", "extension", "My File.TXT"),
        ("My File.txt", "upper", "extension", "My File.TXT"),
        ("README", "lower", "extension", "readme"),
        ("the lord of the rings.txt", "title", "both", "The Lord of the Rings.txt"),
        ("a tale of two cities", "title", "both", "A Tale of Two Cities"),
        ("ends with of", "title", "both", "Ends With Of"),
        ("the lord of the rings.txt", "words", "both", "The Lord Of The Rings.txt"),
        ("don't stop-me now.txt", "words", "both", "Don't Stop-Me Now.txt"),
        ("'quoted' word", "words", "both", "'Quoted' Word"),
        ("mIxEd.TXT", "words", "extension", "mIxEd.TXT"),
        ("árvíztűrő tükörfúrógép", "words", "both", "Árvíztűrő Tükörfúrógép"),
    ],
)
def test_change_case(name: str, text_case: str, apply_to: str, made: str) -> None:
    assert change_case(name, text_case, False, apply_to) == made


def test_a_folder_is_one_name() -> None:
    assert change_case("my.photos", "words", True, "name") == "My.Photos"
    assert change_case("My.Photos", "lower", True, "name") == "my.photos"
