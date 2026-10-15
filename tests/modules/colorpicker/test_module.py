from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.colorpicker.colors import Color
from tuxtoys.modules.colorpicker.module import ColorPicker, picker_command
from tuxtoys.modules.colorpicker.options import MOST_HISTORY, Options


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
    module = ColorPicker(lambda: bindings)
    module.enable(Context(None, ColorPicker.read_settings({})))
    assert [(c.name, c.command, c.binding) for c in bindings.customs] == [
        ("TuxToys: Color Picker", "tuxtoys colorpicker", ["<Shift><Super>c"])
    ]
    module.enable(Context(None, ColorPicker.read_settings({})))
    assert len(bindings.customs) == 1
    module.apply_settings(Options(shortcut=False).settings())
    assert bindings.customs == []
    module.apply_settings(Options().settings())
    module.disable()
    assert len(bindings.customs) == 1
    module.switched_off()
    assert bindings.customs == []


def test_keys_in_use_are_left_alone() -> None:
    bindings = FakeKeybindings(taken={"<Shift><Super>c": ["screensaver"]})
    module = ColorPicker(lambda: bindings)
    module.enable(Context(None, ColorPicker.read_settings({})))
    assert bindings.customs == []
    assert module.shortcut.problem == "taken"


def test_without_cinnamon() -> None:
    def missing() -> FakeKeybindings:
        raise RuntimeError("needs Cinnamon")

    module = ColorPicker(missing)
    module.enable(Context(None, ColorPicker.read_settings({})))
    assert module.shortcut.problem == "missing"
    module.switched_off()


def test_options() -> None:
    options = Options()
    assert options.default_format == "HEX"
    assert [name for name, _t, shown in options.formats if shown] == [
        "HEX",
        "RGB",
        "HSL",
        "HSV",
        "CMYK",
    ]
    assert Options.read(options.settings()) == options
    assert options.template("RGB") == "rgb(%Re, %Gr, %Bl)"
    picked = options
    for value in range(MOST_HISTORY + 3):
        picked = picked.picked(Color(value, 0, 0))
    assert len(picked.history) == MOST_HISTORY
    assert picked.history[0] == "#160000"
    assert picked.picked(Color(21, 0, 0)).history[:2] == ("#150000", "#160000")
    for bad, message in (
        ({"default_format": "LAB"}, "no format"),
        ({"formats": []}, "1 to"),
        ({"formats": [["A", "x", True], ["A", "y", True]]}, "same name"),
        ({"history": ["nope"]}, "not a color"),
        ({"other": 1}, "unknown setting"),
    ):
        with pytest.raises(ValueError, match=message):
            options.update(bad)
    assert options.update({"formats": [["Mine", "%Re", True]]}).default_format == "Mine"


def test_picker_command(tmp_path: Path) -> None:
    assert picker_command(tmp_path)[-2:] == ["-m", "tuxtoys.colorpicker"]
