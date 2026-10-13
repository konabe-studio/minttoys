from pathlib import Path

import pytest

from tuxtoys.modules.renameplus import files
from tuxtoys.modules.renameplus.files import Move, gather, rename_all
from tuxtoys.modules.renameplus.options import FLAGS, MOST_RECENT, Options, remember
from tuxtoys.modules.renameplus.pattern import PatternError, Rules
from tuxtoys.modules.renameplus.plan import (
    CLASH,
    INVALID,
    RENAME,
    SKIPPED,
    TOO_LONG,
    UNCHANGED,
    Include,
    Item,
    Outcome,
    count,
    plan,
)


def items(*names: str, folder: str = "/f") -> list[Item]:
    return [Item(folder, name, name.endswith("/")) for name in names]


def test_counters_count_the_items_that_match() -> None:
    chosen = items("a1.txt", "b.txt", "a2.txt")
    made = plan(chosen, Rules("a", "x${start=1}"), Include())
    assert made == [Outcome(RENAME, "x11.txt"), Outcome(UNCHANGED), Outcome(RENAME, "x22.txt")]
    assert count(made) == 2


def test_no_search_changes_nothing_but_the_case() -> None:
    assert plan(items("A.txt"), Rules(), Include()) == [Outcome(UNCHANGED)]
    assert plan(items("A.txt"), Rules(text_case="lower"), Include()) == [Outcome(RENAME, "a.txt")]


def test_what_is_left_out() -> None:
    chosen = [
        Item("/f", "file.txt", False),
        Item("/f", "folder.txt", True),
        Item("/f/folder.txt", "inner.txt", False, depth=1),
        Item("/f", "off.txt", False, selected=False),
    ]
    rules = Rules("txt", "md", apply_to="extension")
    assert [o.status for o in plan(chosen, rules, Include())] == [
        RENAME,
        SKIPPED,  # a folder has no extension
        RENAME,
        SKIPPED,
    ]
    rules = Rules("txt", "md")
    assert [o.status for o in plan(chosen, rules, Include(files=False))] == [
        SKIPPED,
        RENAME,
        SKIPPED,
        SKIPPED,
    ]
    assert [o.status for o in plan(chosen, rules, Include(subfolders=False))] == [
        RENAME,
        RENAME,
        SKIPPED,
        SKIPPED,
    ]


def test_bad_names() -> None:
    long = "x" * 256
    made = plan(items("a.txt", "c.txt"), Rules("^[ab]", "", regex=True), Include())
    assert made[0] == Outcome(RENAME, ".txt")
    assert plan(items("a"), Rules("a", "/"), Include()) == [Outcome(INVALID, "/")]
    assert plan(items("a"), Rules("a", " .. "), Include()) == [Outcome(INVALID, "..")]
    assert plan(items("a"), Rules("a", long), Include()) == [Outcome(TOO_LONG, long)]
    assert plan(items("a"), Rules("a", "á" * 128), Include())[0].status == TOO_LONG
    assert plan(items("a"), Rules("a", "  b  "), Include()) == [Outcome(RENAME, "b")]


def test_clashes() -> None:
    # Two items to one name, and a name an item keeps.
    made = plan(items("a1", "a2", "b"), Rules(r"\d", "", regex=True), Include())
    assert [o.status for o in made] == [CLASH, CLASH, UNCHANGED]
    made = plan(items("a", "b"), Rules("a", "b"), Include())
    assert [o.status for o in made] == [CLASH, UNCHANGED]
    # A swap is fine, and so is taking a name another item leaves.
    made = plan(items("a", "b"), Rules("^(a|b)$", "x$1", regex=True), Include())
    assert [o.status for o in made] == [RENAME, RENAME]
    made = plan(items("a", "ab"), Rules("a", "", regex=False), Include())
    assert made == [Outcome(INVALID, ""), Outcome(RENAME, "b")]
    # Something in the folder that is not chosen.
    on_disk = {("/f", "z")}
    made = plan(items("a"), Rules("a", "z"), Include(), lambda f, n, own: (f, n) in on_disk)
    assert made == [Outcome(CLASH, "z")]
    # The same name in different folders is no clash.
    two = [Item("/f", "a", False), Item("/g", "a", False)]
    assert count(plan(two, Rules("a", "b"), Include())) == 2


def test_bad_expression() -> None:
    with pytest.raises(PatternError):
        plan(items("a"), Rules("[", regex=True), Include())


def test_options() -> None:
    options = Options()
    assert options.enumerate
    assert options.restore_flags
    assert not options.randomize
    assert not options.nemo_rename
    assert not options.show_recent
    changed = options.update({"regex": True, "apply_to": "name", "recent_search": ["x"]})
    assert Options.read(changed.settings()) == changed
    assert set(changed.flags()) == set(FLAGS)
    assert changed.rules("s", "r") == Rules("s", "r", regex=True, apply_to="name")
    for bad, message in (
        ({"apply_to": "all"}, "apply_to is one of"),
        ({"regex": 1}, "regex is true or false"),
        ({"recent_search": ["x"] * 11}, "at most 10"),
        ({"x": 1}, "unknown setting"),
    ):
        with pytest.raises(ValueError, match=message):
            options.update(bad)
    assert Options.read({"text_case": "shout", "match_all": True}) == Options(match_all=True)


def test_remember() -> None:
    assert remember(["b", "a"], "a") == ["a", "b"]
    assert remember(["a"], "") == ["a"]
    assert len(remember([str(n) for n in range(MOST_RECENT)], "new")) == MOST_RECENT


def test_gather(tmp_path: Path) -> None:
    (tmp_path / "Photos").mkdir()
    (tmp_path / "Photos" / "10.jpg").write_text("")
    (tmp_path / "Photos" / "2.jpg").write_text("")
    (tmp_path / "Photos" / "Old").mkdir()
    (tmp_path / "Photos" / "Old" / "x.jpg").write_text("")
    (tmp_path / "b.txt").write_text("")
    found, cut = gather([tmp_path / "b.txt", tmp_path / "Photos"], when=lambda path: None)
    assert [(i.name, i.depth, i.is_folder) for i in found] == [
        ("Photos", 0, True),
        ("Old", 1, True),
        ("x.jpg", 2, False),
        ("2.jpg", 1, False),
        ("10.jpg", 1, False),
        ("b.txt", 0, False),
    ]
    assert found[1].folder == str(tmp_path / "Photos")
    assert not cut
    found, cut = gather([tmp_path / "Photos"], when=lambda path: None, most=2)
    assert len(found) == 2
    assert cut
    assert files.file_time(tmp_path / "b.txt") is not None
    assert files.file_time(tmp_path / "missing") is None


def test_rename_deepest_first(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "a.txt").write_text("a")
    done, failed = rename_all(
        [
            Move(str(tmp_path), "old", "new", 0),
            Move(str(tmp_path / "old"), "a.txt", "b.txt", 1),
        ]
    )
    assert not failed
    assert len(done) == 2
    assert (tmp_path / "new" / "b.txt").read_text() == "a"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["new"]


def test_rename_swaps_and_never_overwrites(tmp_path: Path) -> None:
    (tmp_path / "a").write_text("a")
    (tmp_path / "b").write_text("b")
    (tmp_path / "c").write_text("c")
    (tmp_path / "d").write_text("d")
    done, failed = rename_all(
        [
            Move(str(tmp_path), "a", "b", 0),
            Move(str(tmp_path), "b", "a", 0),
            Move(str(tmp_path), "c", "d", 0),  # d is taken and stays
        ]
    )
    assert len(done) == 2
    assert [(f.name, f.reason, f.left_as) for f in failed] == [("c", "", "")]
    assert {p.name: p.read_text() for p in tmp_path.iterdir()} == {
        "a": "b",
        "b": "a",
        "c": "c",
        "d": "d",
    }


def test_rename_reports_a_missing_item(tmp_path: Path) -> None:
    done, failed = rename_all([Move(str(tmp_path), "gone", "x", 0)])
    assert not done
    assert failed[0].name == "gone"
    assert failed[0].reason


def test_taken(tmp_path: Path) -> None:
    (tmp_path / "a").write_text("")
    (tmp_path / "b").write_text("")
    assert files.taken(str(tmp_path), "b", "a")
    assert not files.taken(str(tmp_path), "c", "a")
    assert not files.taken(str(tmp_path), "a", "a")
