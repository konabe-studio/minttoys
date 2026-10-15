"""Color Picker as one program: the picker and the editor, and what passes between them.

The shortcut opens the picker or the editor first, as the activation setting says. A
picked color is copied in the default format and joins the history; then, as the mouse
button's setting says, the editor opens, or everything closes. The editor's Pick hides
it, picks, and brings it back. The history and the settings go through the daemon when
it is there; without it, they last until the program ends.
"""

from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol

from tuxtoys.api import ModuleOff, NotRunning, Refused
from tuxtoys.modules.colorpicker.colors import Color, format_color
from tuxtoys.modules.colorpicker.options import Options

# The editor hides before the screen is captured; this long for the compositor to redraw.
HIDE_MS = 250


class Client(Protocol):
    def set_module_settings(self, module_id: str, changes: dict) -> None: ...


class Ui(Protocol):
    """What the program shows, as GTK does it in main.py; the tests hand in their own."""

    def picker(self, options: Options, done: Callable[[Color | None, str], None]) -> bool: ...
    def editor(self, app: "ColorPickerApp") -> Any: ...  # noqa: ANN401
    def copy(self, text: str) -> None: ...
    def later(self, milliseconds: int, call: Callable[[], None]) -> None: ...
    def quit(self) -> None: ...


class ColorPickerApp:
    def __init__(self, client: Client | None, options: Options, ui: Ui) -> None:
        self._client = client
        self.options = options
        self._ui = ui
        self._editor: Any = None

    @property
    def history(self) -> list[Color]:
        return [Color.from_hex(text) for text in self.options.history]

    @property
    def formats(self) -> list[tuple[str, str]]:
        return [(name, template) for name, template, shown in self.options.formats if shown]

    def start(self) -> None:
        if self.options.activation == "editor":
            self.open_editor()
        else:
            self.open_picker()

    def open_picker(self) -> None:
        if not self._ui.picker(self.options, self._picked):
            self._closed_all()

    def open_editor(self) -> None:
        if self._editor is None:
            self._editor = self._ui.editor(self)
        else:
            self._editor.show_colors()
            self._editor.present()

    def editor_closed(self) -> None:
        self._editor = None
        self.quit()

    def pick_again(self) -> None:
        """The editor's Pick: out of the way first, so it is not in the picture."""
        if self._editor is not None:
            self._editor.hide()
        self._ui.later(HIDE_MS, self.open_picker)

    def _picked(self, color: Color | None, action: str) -> None:
        if color is not None:
            self.copy(format_color(color, self.options.template(self.options.default_format)))
            self._remember(self.options.picked(color))
        if action == "pick-editor" or (self._editor is not None and action != "pick-close"):
            self.open_editor()
        else:
            self._closed_all()

    def _closed_all(self) -> None:
        if self._editor is not None:
            self._editor.destroy()
            self._editor = None
        self.quit()

    def quit(self) -> None:
        self._ui.quit()

    def choose(self, color: Color) -> None:
        """A color from the editor's bar or its fine-tuning: shown, and in the history."""
        self._remember(self.options.picked(color))
        if self._editor is not None:
            self._editor.show_colors(color)

    def remove(self, color: Color) -> None:
        history = [text for text in self.options.history if text != color.hex]
        self._remember(self.options.update({"history": history}))
        if self._editor is not None:
            self._editor.show_colors()

    def copy(self, text: str) -> None:
        self._ui.copy(text)

    def _remember(self, options: Options) -> None:
        self.options = options
        if self._client is not None:
            with suppress(NotRunning, ModuleOff, Refused):
                self._client.set_module_settings("colorpicker", {"history": list(options.history)})
