"""Color Picker's program without GTK: what follows a pick, by the settings."""

from collections.abc import Callable

from tuxtoys.colorpicker.app import ColorPickerApp
from tuxtoys.modules.colorpicker.colors import Color
from tuxtoys.modules.colorpicker.options import Options
from tuxtoys.modules.colorpicker.shades import shades

RED = Color(255, 0, 0)


class FakeEditor:
    def __init__(self) -> None:
        self.shown: list[Color | None] = []
        self.hidden = False
        self.destroyed = False

    def show_colors(self, selected: Color | None = None) -> None:
        self.shown.append(selected)

    def present(self) -> None:
        self.hidden = False

    def hide(self) -> None:
        self.hidden = True

    def destroy(self) -> None:
        self.destroyed = True


class FakeUi:
    def __init__(self, picks: list[tuple[Color | None, str]]) -> None:
        self.picks = picks
        self.copied: list[str] = []
        self.editors: list[FakeEditor] = []
        self.quits = 0

    def picker(self, options: Options, done: Callable[[Color | None, str], None]) -> bool:
        if not self.picks:
            return False
        done(*self.picks.pop(0))
        return True

    def editor(self, app: ColorPickerApp) -> FakeEditor:
        self.editors.append(FakeEditor())
        return self.editors[-1]

    def copy(self, text: str) -> None:
        self.copied.append(text)

    def later(self, milliseconds: int, call: Callable[[], None]) -> None:
        call()

    def quit(self) -> None:
        self.quits += 1


class FakeClient:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def set_module_settings(self, module_id: str, changes: dict) -> None:
        self.saved.append(changes)


def test_left_click_copies_and_opens_the_editor() -> None:
    ui, client = FakeUi([(RED, "pick-editor")]), FakeClient()
    app = ColorPickerApp(client, Options(), ui)
    app.start()
    assert ui.copied == ["ff0000"]
    assert client.saved == [{"history": ["#ff0000"]}]
    assert len(ui.editors) == 1
    assert ui.quits == 0


def test_middle_click_copies_and_closes() -> None:
    ui = FakeUi([(RED, "pick-close")])
    ColorPickerApp(None, Options(default_format="RGB"), ui).start()
    assert ui.copied == ["rgb(255, 0, 0)"]
    assert ui.editors == []
    assert ui.quits == 1


def test_right_click_closes() -> None:
    ui = FakeUi([(None, "close")])
    ColorPickerApp(None, Options(), ui).start()
    assert ui.copied == []
    assert ui.quits == 1


def test_the_editor_first_and_its_pick_button() -> None:
    ui = FakeUi([(Color(0, 0, 255), "pick-editor"), (None, "close")])
    app = ColorPickerApp(None, Options(activation="editor", history=("#ff0000",)), ui)
    app.start()
    assert len(ui.editors) == 1
    app.pick_again()
    editor = ui.editors[0]
    assert editor.hidden is False  # back after picking
    assert app.options.history == ("#0000ff", "#ff0000")
    # Picking again and leaving with a right click brings the editor back too.
    app.pick_again()
    assert editor.hidden is False
    assert len(ui.editors) == 1


def test_choose_and_remove() -> None:
    ui = FakeUi([])
    app = ColorPickerApp(None, Options(activation="editor", history=("#ff0000",)), ui)
    app.start()
    app.choose(Color(1, 2, 3))
    assert app.options.history == ("#010203", "#ff0000")
    app.remove(RED)
    assert app.options.history == ("#010203",)
    assert [name for name, _t in app.formats] == ["HEX", "RGB", "HSL", "HSV", "CMYK"]


def test_shades() -> None:
    made = shades(Color(100, 50, 50))
    assert len(made) == 5
    assert made[2] == Color(100, 50, 50)
    assert made[0] != made[4]
    assert shades(Color(255, 255, 255))[0] == Color(255, 255, 255)
