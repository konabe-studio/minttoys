"""Always on Top's module on a D-Bus daemon of the test's own, with stand-ins for Muffin's
keys and for the frame helper.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio

from minttoys.modules.alwaysontop.module import AlwaysOnTop, helper_command
from minttoys.modules.alwaysontop.options import Options
from minttoys.modules.base import Context

KEYS = "<Primary><Super>t"


@dataclass
class Custom:
    path: str
    name: str
    command: str
    binding: list[str]


@dataclass
class FakeKeybindings:
    wm: dict[str, list[str]] = field(default_factory=lambda: {"toggle-above": []})
    taken: dict[str, list[str]] = field(default_factory=dict)
    customs: list[Custom] = field(default_factory=list)

    def find(self, name: str, command: str) -> Custom | None:
        return next((c for c in self.customs if (c.name, c.command) == (name, command)), None)

    def add(self, name: str, command: str, keys: str) -> None:
        self.customs.append(Custom(f"custom{len(self.customs)}", name, command, [keys]))

    def remove(self, path: str) -> None:
        self.customs = [c for c in self.customs if c.path != path]

    def wm_keys(self, action: str) -> list[str]:
        return list(self.wm[action])

    def set_wm_keys(self, action: str, keys: list[str]) -> None:
        self.wm[action] = list(keys)

    def taken_by(self, keys: str) -> list[str]:
        return self.taken.get(keys, [])


class FakeHelper:
    def __init__(self, command: list[str], started: list) -> None:
        self.command = command
        self.running = True
        started.append(self)

    def poll(self) -> int | None:
        return None if self.running else 0

    def terminate(self) -> None:
        self.running = False

    def wait(self, timeout: float | None = None) -> int:
        return 0


@dataclass
class Harness:
    module: AlwaysOnTop
    keys: FakeKeybindings
    started: list[FakeHelper]
    bus: Gio.DBusConnection
    config: dict = field(default_factory=dict)

    def enable(self, settings: dict | None = None) -> None:
        self.config = dict(settings or {})
        self.module.enable(
            Context(self.bus, AlwaysOnTop.read_settings(self.config), self.set_settings)
        )

    def set_settings(self, changes: dict) -> None:
        updated = AlwaysOnTop.check_settings(AlwaysOnTop.read_settings(self.config), changes)
        self.config.update({key: updated[key] for key in changes})
        self.module.apply_settings(updated)

    def running(self) -> list[FakeHelper]:
        return [helper for helper in self.started if helper.running]


@pytest.fixture
def harness(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> Iterator[Harness]:
    keys = FakeKeybindings()
    started: list[FakeHelper] = []
    module = AlwaysOnTop(lambda: keys, lambda command: FakeHelper(command, started))
    shown = Harness(module, keys, started, private_bus[0])
    yield shown
    module.disable()


def test_on_gives_toggle_above_its_keys_and_starts_the_frame(harness: Harness) -> None:
    harness.enable()
    assert harness.keys.wm["toggle-above"] == [KEYS]
    assert len(harness.running()) == 1
    assert harness.module.state() == {
        "shortcut": KEYS,
        "shortcut_problem": "",
        "opacity_problem": "",
    }


def test_keys_of_the_users_own_are_kept(harness: Harness) -> None:
    harness.keys.wm["toggle-above"] = ["<Super>F12"]
    harness.enable()
    harness.module.switched_off()
    assert harness.keys.wm["toggle-above"] == ["<Super>F12"]


def test_taken_keys_give_no_shortcut_and_say_so(harness: Harness) -> None:
    harness.keys.taken[KEYS] = ["My script"]
    harness.enable()
    assert harness.keys.wm["toggle-above"] == []
    assert harness.module.state()["shortcut_problem"] == "taken"


def test_the_end_of_a_session_keeps_the_keys_but_stops_the_frame(harness: Harness) -> None:
    harness.enable()
    harness.module.disable()
    assert harness.keys.wm["toggle-above"] == [KEYS]
    assert harness.running() == []


def test_switching_off_takes_the_keys_back(harness: Harness) -> None:
    harness.enable()
    harness.module.switched_off()
    assert harness.keys.wm["toggle-above"] == []


def test_the_shortcut_setting(harness: Harness) -> None:
    harness.enable()
    harness.set_settings({"shortcut": False})
    assert harness.keys.wm["toggle-above"] == []
    harness.set_settings({"shortcut": True})
    assert harness.keys.wm["toggle-above"] == [KEYS]


def test_no_border_no_helper(harness: Harness) -> None:
    harness.enable({"border": False})
    assert harness.started == []


def test_a_new_frame_restarts_the_helper(harness: Harness) -> None:
    harness.enable()
    harness.set_settings({"border_color": "#ff8000", "border_width": 6, "sound": True})
    (helper,) = harness.running()
    assert helper.command[3:] == [
        "--width",
        "6",
        "--opacity",
        "100",
        "--radius",
        "8",
        "--color",
        "#ff8000",
        "--sound",
    ]
    assert len(harness.started) == 2


def test_other_settings_leave_the_helper_alone(harness: Harness) -> None:
    harness.enable()
    harness.set_settings({"shortcut": False})
    assert len(harness.started) == 1


def test_a_checkout_runs_the_helper_as_a_module(tmp_path: Path) -> None:
    command = helper_command(Options(excluded="firefox\nvlc"), tmp_path)
    assert command[1:] == [
        "-m",
        "minttoys.alwaysontop",
        "--width",
        "4",
        "--opacity",
        "100",
        "--radius",
        "8",
        "--exclude",
        "firefox",
        "--exclude",
        "vlc",
    ]


def opacity_shortcuts(harness: Harness) -> list[tuple[str, list[str]]]:
    return [(custom.command, custom.binding) for custom in harness.keys.customs]


def test_on_adds_the_opacity_shortcuts(harness: Harness) -> None:
    harness.enable()
    assert opacity_shortcuts(harness) == [
        ("minttoys alwaysontop opacity up", ["<Primary><Super>Page_Up"]),
        ("minttoys alwaysontop opacity down", ["<Primary><Super>Page_Down"]),
    ]


def test_taken_opacity_keys_say_so(harness: Harness) -> None:
    harness.keys.taken["<Primary><Super>Page_Up"] = ["My script"]
    harness.enable()
    assert [command for command, _ in opacity_shortcuts(harness)] == [
        "minttoys alwaysontop opacity down"
    ]
    assert harness.module.state()["opacity_problem"] == "taken"


def test_switching_off_takes_the_opacity_shortcuts_away(harness: Harness) -> None:
    harness.enable()
    harness.module.switched_off()
    assert opacity_shortcuts(harness) == []


def test_the_opacity_shortcuts_setting(harness: Harness) -> None:
    harness.enable()
    harness.set_settings({"opacity_shortcuts": False})
    assert opacity_shortcuts(harness) == []
    harness.set_settings({"opacity_shortcuts": True})
    assert len(opacity_shortcuts(harness)) == 2
