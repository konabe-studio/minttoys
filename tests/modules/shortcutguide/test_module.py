from dataclasses import dataclass, field
from pathlib import Path

from tuxtoys.modules.base import Context
from tuxtoys.modules.shortcutguide.module import ShortcutGuide, guide_command
from tuxtoys.modules.shortcutguide.options import Options


@dataclass
class Found:
    path: str
    name: str
    command: str
    binding: list[str]


@dataclass
class FakeKeybindings:
    customs: list[Found] = field(default_factory=list)
    taken: dict[str, list[str]] = field(default_factory=dict)

    def find(self, name: str, command: str) -> Found | None:
        return next((c for c in self.customs if c.name == name and c.command == command), None)

    def taken_by(self, keys: str) -> list[str]:
        return self.taken.get(keys, [])

    def add(self, name: str, command: str, keys: str) -> None:
        self.customs.append(Found(f"custom{len(self.customs)}", name, command, [keys]))

    def remove(self, path: str) -> None:
        self.customs = [c for c in self.customs if c.path != path]


def test_the_shortcut_is_kept_while_on() -> None:
    bindings = FakeKeybindings()
    module = ShortcutGuide(lambda: bindings)
    module.enable(Context(None, ShortcutGuide.read_settings({})))
    assert [(c.name, c.command, c.binding) for c in bindings.customs] == [
        ("TuxToys: Shortcut Guide", "tuxtoys shortcutguide", ["<Shift><Super>slash"])
    ]
    module.apply_settings(Options(shortcut=False).settings())
    assert bindings.customs == []
    module.apply_settings(Options().settings())
    module.disable()
    assert len(bindings.customs) == 1
    module.switched_off()
    assert bindings.customs == []


def test_keys_in_use_are_left_alone() -> None:
    bindings = FakeKeybindings(taken={"<Shift><Super>slash": ["someone"]})
    module = ShortcutGuide(lambda: bindings)
    module.enable(Context(None, ShortcutGuide.read_settings({})))
    assert bindings.customs == []
    assert module.shortcut.problem == "taken"


def test_settings_are_checked_all_or_none() -> None:
    settings = ShortcutGuide.read_settings({})
    assert ShortcutGuide.check_settings(settings, {"position": "center"})["position"] == "center"


def test_guide_command(tmp_path: Path) -> None:
    assert guide_command(tmp_path)[-2:] == ["-m", "tuxtoys.shortcutguide"]
