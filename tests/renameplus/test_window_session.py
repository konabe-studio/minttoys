"""Rename+'s window with real GTK, real files and a stand-in for the daemon. Needs a display:
xvfb in CI, the desktop otherwise.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.api import NotRunning  # noqa: E402
from tuxtoys.modules.renameplus import files  # noqa: E402
from tuxtoys.modules.renameplus.options import Options  # noqa: E402
from tuxtoys.renameplus.window import NEW, RenameWindow, local_paths  # noqa: E402


class FakeClient:
    def __init__(self, settings: dict | None = None, running: bool = True) -> None:
        self.settings = settings if settings is not None else Options().settings()
        self.saved: list[dict] = []
        self.running = running

    def module_settings(self, module_id: str) -> dict:
        if not self.running:
            raise NotRunning
        return dict(self.settings)

    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None:
        if not self.running:
            raise NotRunning
        self.saved.append(dict(changes))


class Renamer:
    def __init__(self, fail: Sequence[files.Failure] = ()) -> None:
        self.moves: list[files.Move] = []
        self.fail = list(fail)

    def __call__(self, moves: Sequence[files.Move]) -> tuple[list, list]:
        self.moves = list(moves)
        return list(moves), self.fail


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    for name in ("a1.txt", "a2.txt", "b.txt"):
        (tmp_path / name).write_text(name)
    (tmp_path / "album").mkdir()
    (tmp_path / "album" / "a3.jpg").write_text("")
    return tmp_path


def open_window(
    folder: Path, client: FakeClient | None = None, renamer: Renamer | None = None
) -> RenameWindow:
    chosen = sorted(folder.iterdir())
    return RenameWindow(
        None,
        chosen,
        client if client is not None else FakeClient(),
        renamer or Renamer(),
        when=lambda path: None,
        in_background=False,
    )


def test_the_preview_follows_the_search(folder: Path) -> None:
    window = open_window(folder)
    assert window.summary.get_text() == "0 of 5 items will be renamed."
    assert not window.rename_button.get_sensitive()
    window.search.set_text("a")
    window.replace.set_text("x${start=1}")
    window.refresh()
    assert window.summary.get_text() == "4 of 5 items will be renamed."
    names = {
        item.name: outcome.new_name
        for item, outcome in zip(window.items, window.outcomes, strict=True)
    }
    # Folders first, then what is inside them, then the files, in name order.
    assert names == {
        "album": "x1lbum",
        "a3.jpg": "x23.jpg",
        "a1.txt": "x31.txt",
        "a2.txt": "x42.txt",
        "b.txt": "",
    }
    assert window.rename_button.get_sensitive()


def test_rename_and_remember(folder: Path) -> None:
    client, renamer = FakeClient(), Renamer()
    window = open_window(folder, client, renamer)
    window.search.set_text("txt")
    window.replace.set_text("md")
    window.apply_to.set_active_id("extension")
    window.start()
    assert sorted((move.old, move.new) for move in renamer.moves) == [
        ("a1.txt", "a1.md"),
        ("a2.txt", "a2.md"),
        ("b.txt", "b.md"),
    ]
    saved = client.saved[0]
    assert saved["apply_to"] == "extension"
    assert saved["recent_search"] == ["txt"]
    assert saved["recent_replace"] == ["md"]


def test_really_renaming(folder: Path) -> None:
    window = RenameWindow(None, [folder / "a1.txt"], None, when=lambda path: None)
    window.search.set_text("1")
    window.replace.set_text("one")
    window._in_background = False
    window.start()
    assert (folder / "aone.txt").read_text() == "a1.txt"


def test_a_cleared_box_leaves_an_item_out(folder: Path) -> None:
    window = open_window(folder)
    window.search.set_text("a")
    window.replace.set_text("z")
    window.refresh()
    before = sum(outcome.status == "rename" for outcome in window.outcomes)
    window._on_toggled(Gtk.CellRendererToggle(), "0")  # the album folder
    assert sum(outcome.status == "rename" for outcome in window.outcomes) == before - 1


def test_a_bad_expression_is_shown_on_the_field(folder: Path) -> None:
    window = open_window(folder)
    window.regex.set_active(True)
    window.search.set_text("(")
    window.refresh()
    assert window.search.get_icon_name(Gtk.EntryIconPosition.SECONDARY)
    assert "not a regular expression" in window.search.get_icon_tooltip_text(
        Gtk.EntryIconPosition.SECONDARY
    )
    assert not window.rename_button.get_sensitive()


def test_only_items_that_change(folder: Path) -> None:
    window = open_window(folder)
    window.search.set_text("3")
    window.replace.set_text("4")
    window.only_changing.set_active(True)
    # The album stays in view, as a3.jpg inside it changes.
    shown = []
    window.filtered.foreach(lambda model, _path, row: shown.append(model[row][NEW]) and False)
    assert shown == ["", "a4.jpg"]


def test_clashes_are_not_renamed(folder: Path) -> None:
    window = open_window(folder)
    window.search.set_text(r"\d")
    window.regex.set_active(True)
    window.include_folders.set_active(False)
    window.include_subfolders.set_active(False)
    window.refresh()
    statuses = {
        item.name: outcome.status
        for item, outcome in zip(window.items, window.outcomes, strict=True)
    }
    assert statuses["a1.txt"] == "clash"
    assert statuses["a2.txt"] == "clash"


def test_failures_are_listed(folder: Path) -> None:
    renamer = Renamer([files.Failure(str(folder), "a1.txt", "Permission denied")])
    window = open_window(folder, renamer=renamer)
    window.search.set_text("a")
    window.replace.set_text("c")
    window.start()
    assert window.stack.get_visible_child_name() == "done"
    assert "a1.txt: Permission denied" in window.failures.get_text()


def test_flags_and_recent_text(folder: Path) -> None:
    settings = Options(
        regex=True, recent_search=("old",), recent_replace=("new",), show_recent=True
    ).settings()
    window = open_window(folder, FakeClient(settings))
    assert window.regex.get_active()
    assert window.search.get_text() == "old"
    assert window.replace.get_text() == "new"
    settings = Options(regex=True, restore_flags=False).settings()
    window = open_window(folder, FakeClient(settings))
    assert not window.regex.get_active()
    assert window.search.get_text() == ""


def test_insert_a_variable(folder: Path) -> None:
    window = open_window(folder)
    window.replace.set_text("ab")
    window.replace.set_position(1)
    window.insert("$YYYY")
    assert window.replace.get_text() == "a$YYYYb"


def test_without_the_daemon(folder: Path) -> None:
    window = open_window(folder, FakeClient(running=False))
    window.search.set_text("b")
    window.replace.set_text("c")
    window.start()
    assert window.failed == []


def test_local_paths(tmp_path: Path) -> None:
    uri = (tmp_path / "a b.txt").as_uri()
    paths, elsewhere = local_paths([uri, str(tmp_path / "c.txt"), "sftp://host/x"])
    assert paths == [tmp_path / "a b.txt", tmp_path / "c.txt"]
    assert elsewhere == ["sftp://host/x"]
