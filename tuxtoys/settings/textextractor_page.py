"""Text Extractor's page, as PowerToys has it: whether it is on, a note that it reads only
the languages installed for it, its keyboard shortcut, and the preferred language. The
settings go through the daemon; the shortcut's keys are read from Cinnamon, where the
user may have changed them, and the languages from tesseract.
"""

from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.shortcut import CustomShortcut  # noqa: E402
from tuxtoys.modules.textextractor import tesseract  # noqa: E402
from tuxtoys.modules.textextractor.module import extractor_command  # noqa: E402
from tuxtoys.modules.textextractor.options import (  # noqa: E402
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.settings.colorpicker_page import keys_label  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.screenruler_page import with_detail  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402
from tuxtoys.settings.widgets import open_keyboard_settings  # noqa: E402


def open_extractor(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(extractor_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


def language_choices(languages: Sequence[str] | None) -> list[tuple[str, str]]:
    """Each installed language by its own name; one line saying so when there is none."""
    if not languages:
        return [("", _("No language installed"))]
    return [(code, tesseract.name(code)) for code in languages]


def languages_note(languages: Sequence[str] | None) -> str:
    if languages is None:
        return _(
            "Text Extractor reads the screen with tesseract, which is not installed."
            " Install it with: sudo apt install tesseract-ocr tesseract-ocr-hun"
        )
    return _(
        "Text Extractor reads only the languages whose tesseract data is installed. Add"
        " one with its package, such as: sudo apt install tesseract-ocr-deu"
    )


class TextExtractorPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_extractor,
        shortcut: CustomShortcut | None = None,
        languages: Callable[[], list[str] | None] = tesseract.installed,
    ) -> None:
        """The tests hand in an opener, a shortcut and the languages of their own."""
        self._opener = opener
        self._shortcut = shortcut or CustomShortcut(SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS)
        self._loading = False
        self.languages = languages()
        super().__init__(
            client,
            show_error,
            "textextractor",
            _("Text Extractor"),
            _("Copies the text in any part of the screen."),
            _("Use Text Extractor"),
            [
                _(
                    "Press the shortcut and drag over the text: it is copied. A click copies"
                    " the one word under it. At the top of the screen, choose the language,"
                    " or have the text copied on one line or as a table."
                ),
                languages_note(self.languages),
            ],
        )
        self.keys_section = self.add_section(
            _("Activation"),
            _("Change its keys in the Keyboard settings, under TuxToys: Text Extractor."),
        )
        self.shortcut = Switch(_("Extract text with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_shortcut)
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        # python3-xapp's ComboBox needs its choices from the start.
        self.language = ComboBox(_("Preferred language"), language_choices(self.languages))
        with_detail(self.language, _("The language it reads in when it opens."))
        self.language.content_widget.connect("changed", self._on_language)
        self.keys_section.add_row(self.language)
        self.keys_section.add_row(
            Button(_("Extract text now"), lambda *_a: self._opener(show_error))
        )
        self.sections = (self.keys_section,)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("textextractor")
        if settings is not None:
            self.show_settings(settings)
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)
        self.language.set_sensitive(bool(self.languages))

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = Options.read(settings)
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.keys.set_text(self._keys_text(options.shortcut))
            self.language.content_widget.set_active_id(
                tesseract.pick(options.language, self.languages or [])
            )
        finally:
            self._loading = False

    def _keys_text(self, wanted: bool) -> str:
        """The keys as the Keyboard settings name them, or why there are none."""
        if not wanted or self._shown_enabled is not True:
            return ""
        try:
            keys = self._shortcut.current_keys()
        except Exception:  # Cinnamon's settings missing: nothing to show
            return ""
        if keys:
            return keys_label(keys)
        return _(
            "{keys} is in use already. Give Text Extractor other keys in the Keyboard settings."
        ).format(keys=keys_label(SHORTCUT_KEYS))

    def _on_shortcut(self, switch: Gtk.Switch, _spec: object) -> None:
        if not self._loading:
            self._save({"shortcut": switch.get_active()})

    def _on_language(self, combo: Gtk.ComboBox) -> None:
        if not self._loading and combo.get_active_id():
            self._save({"language": combo.get_active_id()})

    def _save(self, changes: Mapping[str, object]) -> None:
        try:
            self._client.set_module_settings("textextractor", changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
