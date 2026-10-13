"""Rename+'s page: whether it is on, how to use it, whether Nemo's Rename opens it, and
what its window starts from. The settings go through the daemon.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402


def dim(text: str) -> Text:
    row = Text(text)
    row.content_widget.get_style_context().add_class("dim-label")
    return row


class RenamePlusPage(SimplePage):
    def __init__(self, client: Client, show_error: Callable[[str], None]) -> None:
        super().__init__(
            client,
            show_error,
            "renameplus",
            _("Rename+"),
            _("Renames many files and folders at once, with a preview."),
            _("Use Rename+"),
            [
                _(
                    "Choose files or folders in Nemo, right-click them and choose Rename with"
                    " Rename+."
                ),
                _(
                    "Every new name shows before anything is renamed. Clear an item's box to"
                    " leave it as it is."
                ),
                _(
                    "Search for text or a regular expression. What replaces it can hold"
                    " counters, random text and the date an item was made: the + button beside"
                    " it lists them."
                ),
            ],
        )
        nemo = self.add_section(_("Nemo"))
        self.nemo_rename = Switch(_("Rename several items in Nemo with Rename+"))
        self.nemo_rename.content_widget.connect("notify::active", self._on_flag, "nemo_rename")
        nemo.add_row(self.nemo_rename)
        nemo.add_row(
            dim(
                _(
                    "Rename (F2) on more than one item opens Rename+ instead of Bulky."
                    " Switching this or Rename+ off brings back what Nemo opened before."
                )
            )
        )
        self.window = self.add_section(_("When Rename+ opens"))
        self.restore_flags = Switch(_("Start with the choices used last time"))
        self.restore_flags.content_widget.connect("notify::active", self._on_flag, "restore_flags")
        self.window.add_row(self.restore_flags)
        self.show_recent = Switch(_("Fill in the last search and replacement"))
        self.show_recent.content_widget.connect("notify::active", self._on_flag, "show_recent")
        self.window.add_row(self.show_recent)
        self.forget = Button(_("Forget the recent searches"), self._on_forget)
        self.window.add_row(self.forget)
        self.window.add_row(
            dim(_("Rename+ offers the last ten searches and replacements as you type."))
        )
        self.sections = (nemo, self.window)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("renameplus")
        if settings is not None:
            self.show_settings(settings)
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        self._loading = True
        try:
            for key in ("nemo_rename", "restore_flags", "show_recent"):
                getattr(self, key).content_widget.set_active(bool(settings.get(key)))
            recent = settings.get("recent_search") or settings.get("recent_replace")
            self.forget.set_sensitive(bool(recent))
        finally:
            self._loading = False

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        if self._loading:
            return
        self._save({key: switch.get_active()})

    def _on_forget(self, *_args: object) -> None:
        self._save({"recent_search": [], "recent_replace": []})

    def _save(self, changes: Mapping[str, object]) -> None:
        try:
            self._client.set_module_settings("renameplus", changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
