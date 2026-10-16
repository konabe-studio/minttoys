"""Shortcut Guide's window with made-up sheets: the tab it opens on, search, pins and
Escape. Needs a display; CI gives it one.
"""

from types import SimpleNamespace

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gdk, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.modules.shortcutguide.reading import Row, Section  # noqa: E402
from tuxtoys.shortcutguide.window import SEARCH, Guide, Tab  # noqa: E402

TABS = [
    Tab(
        "cinnamon",
        "Cinnamon",
        "cinnamon-symbolic",
        [
            Section(
                "Windows",
                (
                    Row("cinnamon/close", "Close window", "", (("Alt", "F4"),)),
                    Row("cinnamon/max", "Maximize window", "", (("Super", "↑"),)),
                ),
            )
        ],
    ),
    Tab(
        "nemo",
        "Nemo",
        "system-file-manager-symbolic",
        [Section("File", (Row("nemo/NewTab", "New Tab", "", (("Ctrl", "T"),)),))],
    ),
]


def make(first: str = "nemo", pins: tuple[str, ...] = ()) -> tuple[Guide, list[tuple]]:
    saved: list[tuple] = []
    guide = Guide(None, TABS, first, pins, (0, 0, 400, 600), saved.append, lambda: None)
    return guide, saved


def labels(widget: Gtk.Widget) -> list[str]:
    found = []
    if isinstance(widget, Gtk.Label):
        found.append(widget.get_text())
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            found.extend(labels(child))
    return found


def test_it_opens_on_the_active_app_s_sheet() -> None:
    guide, _saved = make()
    assert guide.stack.get_visible_child_name() == "nemo"
    assert "New Tab" in labels(guide._pages["nemo"])
    assert "No pinned shortcuts" in labels(guide._pages["nemo"])
    guide.destroy()


def test_an_unknown_first_sheet_opens_the_first_one() -> None:
    guide, _saved = make("gimp")
    assert guide.stack.get_visible_child_name() == "cinnamon"
    guide.destroy()


def test_search_looks_through_every_sheet() -> None:
    guide, _saved = make()
    guide.search.set_text("new")
    guide._on_search(guide.search)
    assert guide.stack.get_visible_child_name() == SEARCH
    found = labels(guide._pages[SEARCH])
    assert "New Tab" in found
    assert "Close window" not in found
    guide.search.set_text("nothing like it")
    guide._on_search(guide.search)
    assert "No shortcuts found." in labels(guide._pages[SEARCH])
    guide.search.set_text("")
    guide._on_search(guide.search)
    assert guide.stack.get_visible_child_name() == "nemo"
    guide.destroy()


def test_a_pinned_row_comes_first_and_is_saved() -> None:
    guide, saved = make("cinnamon")
    guide._toggle(TABS[0].sections[0].rows[1])
    guide._refill()
    assert saved == [("cinnamon/max",)]
    page = labels(guide._pages["cinnamon"])
    assert page.index("Maximize window") < page.index("Windows")
    guide.destroy()


def test_escape_clears_the_search_first_then_closes() -> None:
    guide, _saved = make()
    closed = []
    guide.connect("delete-event", lambda *_args: closed.append(True) or True)
    escape = SimpleNamespace(keyval=Gdk.KEY_Escape)
    guide.search.set_text("tab")
    assert guide._on_key(guide, escape)
    assert guide.search.get_text() == ""
    assert not closed
    guide._on_key(guide, escape)
    while Gtk.events_pending():
        Gtk.main_iteration()
    assert closed
    guide.destroy()
