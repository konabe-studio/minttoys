from dataclasses import dataclass, field
from pathlib import Path

from tuxtoys.modules.base import Context
from tuxtoys.modules.textextractor.module import TextExtractor, extractor_command
from tuxtoys.modules.textextractor.options import Options


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
    module = TextExtractor(lambda: bindings)
    module.enable(Context(None, TextExtractor.read_settings({})))
    assert [(c.name, c.command, c.binding) for c in bindings.customs] == [
        ("TuxToys: Text Extractor", "tuxtoys textextractor", ["<Shift><Super>t"])
    ]
    module.enable(Context(None, TextExtractor.read_settings({})))
    assert len(bindings.customs) == 1
    module.apply_settings(Options(shortcut=False).settings())
    assert bindings.customs == []
    module.apply_settings(Options().settings())
    module.disable()
    assert len(bindings.customs) == 1
    module.switched_off()
    assert bindings.customs == []


def test_keys_in_use_are_left_alone() -> None:
    bindings = FakeKeybindings(taken={"<Shift><Super>t": ["screensaver"]})
    module = TextExtractor(lambda: bindings)
    module.enable(Context(None, TextExtractor.read_settings({})))
    assert bindings.customs == []
    assert module.shortcut.problem == "taken"


def test_without_cinnamon() -> None:
    def missing() -> FakeKeybindings:
        raise RuntimeError("needs Cinnamon")

    module = TextExtractor(missing)
    module.enable(Context(None, TextExtractor.read_settings({})))
    assert module.shortcut.problem == "missing"
    module.switched_off()


def test_extractor_command(tmp_path: Path) -> None:
    assert extractor_command(tmp_path)[-2:] == ["-m", "tuxtoys.textextractor"]
