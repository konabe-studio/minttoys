"""File Locksmith's window with real GTK, a stand-in for /proc and for signals. Needs a
display: xvfb in CI, the desktop otherwise.
"""

import signal
from collections.abc import Callable, Sequence

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.locksmith import window as window_module  # noqa: E402
from tuxtoys.locksmith.window import LocksmithWindow  # noqa: E402
from tuxtoys.modules.locksmith.scan import Holder, Scan  # noqa: E402

REPORT = "/home/ben/report.odt"


class World:
    def __init__(self) -> None:
        self.holders = [Holder(4242, "soffice.bin", (REPORT,))]
        self.some_hidden = True
        self.signals: list[tuple[int, int]] = []
        self.refuse = False
        self.stubborn = False

    def find(self, targets: Sequence[str]) -> Scan:
        return Scan(list(self.holders), self.some_hidden)

    def kill(self, pid: int, number: int) -> None:
        if self.refuse:
            raise PermissionError
        self.signals.append((pid, number))
        if number == signal.SIGKILL or not self.stubborn:
            self.holders = [holder for holder in self.holders if holder.pid != pid]

    def alive(self, pid: int) -> bool:
        return any(holder.pid == pid for holder in self.holders)


@pytest.fixture
def world() -> World:
    return World()


def open_window(world: World, targets: Sequence[str] = (REPORT,)) -> LocksmithWindow:
    return LocksmithWindow(None, targets, world.find, world.kill, world.alive)


def test_lists_what_holds_the_file(world: World) -> None:
    shown = open_window(world)
    assert shown.heading.get_text() == "What is using report.odt"
    assert [tuple(row) for row in shown.store] == [(4242, "soffice.bin", "report.odt")]
    assert shown.stack.get_visible_child_name() == "list"
    assert shown.hidden.get_visible()
    assert not shown.end.get_sensitive()  # nothing chosen yet
    shown.destroy()


def test_nothing_holding_it_says_so(world: World) -> None:
    world.holders, world.some_hidden = [], False
    shown = open_window(world)
    assert shown.stack.get_visible_child_name() == "nothing"
    assert not shown.hidden.get_visible()
    shown.destroy()


def choose_first(shown: LocksmithWindow) -> None:
    shown.list.get_selection().select_path(Gtk.TreePath.new_first())


def test_ending_asks_the_process_to_stop(
    world: World, pump: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window_module, "GRACE_MS", 10)
    shown = open_window(world)
    choose_first(shown)
    assert shown.end.get_sensitive()
    shown.end.clicked()
    assert world.signals == [(4242, signal.SIGTERM)]
    assert pump(lambda: shown.stack.get_visible_child_name() == "nothing")
    shown.destroy()


def test_a_stubborn_process_can_be_forced(
    world: World, pump: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window_module, "GRACE_MS", 10)
    monkeypatch.setattr(LocksmithWindow, "_ask_force", lambda self, name: True)
    world.stubborn = True
    shown = open_window(world)
    choose_first(shown)
    shown.end.clicked()
    assert pump(lambda: len(world.signals) == 2)
    assert world.signals == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]
    shown.destroy()


def test_a_process_one_may_not_end_says_so(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    told: list[str] = []
    monkeypatch.setattr(LocksmithWindow, "_tell", lambda self, message: told.append(message))
    world.refuse = True
    shown = open_window(world)
    choose_first(shown)
    shown.end.clicked()
    assert told == ["You may not end soffice.bin."]
    shown.destroy()
