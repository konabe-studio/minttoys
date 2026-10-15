"""Hosts File Editor's page: whether it is on, a button to open it, and its settings as
PowerToys has them: the warning at the start, loopback addresses as duplicates, and the
backups. The settings go through the daemon.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import (  # noqa: E402
    Button,
    ComboBox,
    SettingsLabel,
    SettingsWidget,
    Switch,
    Text,
)

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.hosts.module import editor_command  # noqa: E402
from tuxtoys.modules.hosts.options import MOST_COUNT, MOST_DAYS  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402
from tuxtoys.settings.widgets import CommandRow  # noqa: E402

# A number typed in is saved once typing pauses this long.
SAVE_AFTER_MS = 400


def keeps() -> list[tuple[str, str]]:
    """PowerToys' choices for deleting old backups, as (keep, label)."""
    return [
        ("never", _("Never")),
        ("count", _("Based on count")),
        ("age", _("Based on age and count")),
    ]


def open_editor(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(editor_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


class NumberRow(SettingsWidget):
    """A label, a line under it that says what the number does, and a spin button."""

    def __init__(self, label: str, detail: str, most: int) -> None:
        super().__init__()
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.pack_start(SettingsLabel(label), False, False, 0)
        small = Gtk.Label(label=detail, xalign=0, wrap=True, max_width_chars=60)
        small.get_style_context().add_class("dim-label")
        labels.pack_start(small, False, False, 0)
        self.content_widget = Gtk.SpinButton.new_with_range(0, most, 1)
        self.content_widget.set_valign(Gtk.Align.CENTER)
        self.pack_start(labels, True, True, 0)
        self.pack_end(self.content_widget, False, False, 0)


class HostsPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_editor,
    ) -> None:
        """The tests hand in an opener of their own."""
        self._opener = opener
        self._save_timer = 0
        self._pending: dict[str, object] = {}
        super().__init__(
            client,
            show_error,
            "hosts",
            _("Hosts File Editor"),
            _("Edits /etc/hosts, which maps names to addresses on this computer."),
            _("Use Hosts File Editor"),
            [
                _(
                    "Open it with the button below, from the applications menu, or with"
                    " tuxtoys hosts."
                ),
                _(
                    "Changes stay in its window until you save them. Saving asks for an"
                    " administrator's password."
                ),
            ],
        )
        # TRANSLATORS: the heading over the button that opens the tool and its command.
        self.open_section = self.add_section(_("Open"))
        self.open_section.add_row(Button(_("Open Hosts File Editor"), self._on_open))
        self.open_section.add_row(CommandRow(_("Command"), "tuxtoys hosts"))

        self.behaviour = self.add_section(_("Behavior"))
        self.show_warning = Switch(_("Show a warning at startup"))
        self.show_warning.content_widget.connect("notify::active", self._on_flag, "show_warning")
        self.behaviour.add_row(self.show_warning)
        self.loopback = Switch(_("Consider loopback addresses as duplicates"))
        self.loopback.content_widget.connect("notify::active", self._on_flag, "loopback_duplicates")
        self.behaviour.add_row(self.loopback)
        loopback = Text(_("Such as 127.0.0.1 and ::1."))
        loopback.content_widget.get_style_context().add_class("dim-label")
        self.behaviour.add_row(loopback)

        self.backups = self.add_section(
            _("Backup"), _("Into /var/backups/tuxtoys, before the first save of a session.")
        )
        self.backup = Switch(_("Back up the hosts file"))
        self.backup.content_widget.connect("notify::active", self._on_flag, "backup")
        self.backups.add_row(self.backup)
        self.keep = ComboBox(_("Automatically delete backups"), keeps())
        self.keep.content_widget.connect("changed", self._on_keep)
        self.backups.add_row(self.keep)
        self.count = NumberRow(
            _("Backup count"),
            _("How many of the newest backups are always kept."),
            MOST_COUNT,
        )
        self.days = NumberRow(
            _("Days"),
            _("Backups older than this are deleted, but never the newest ones counted above."),
            MOST_DAYS,
        )
        self.count_revealer = self.backups.add_reveal_row(self.count)
        self.days_revealer = self.backups.add_reveal_row(self.days)
        for key, row in (("count", self.count), ("days", self.days)):
            row.content_widget.connect("value-changed", self._on_number, key)
        self.sections = (self.open_section, self.behaviour, self.backups)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("hosts")
        if settings is not None:
            self.show_settings(settings)
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping) or self._save_timer:
            return
        self._loading = True
        try:
            self.show_warning.content_widget.set_active(bool(settings.get("show_warning")))
            self.loopback.content_widget.set_active(bool(settings.get("loopback_duplicates")))
            self.backup.content_widget.set_active(bool(settings.get("backup")))
            keep = str(settings.get("keep", "age"))
            self.keep.content_widget.set_active_id(keep)
            self.count.content_widget.set_value(int(settings.get("count", 5)))
            self.days.content_widget.set_value(int(settings.get("days", 15)))
            self._reveal(keep, bool(settings.get("backup")))
        finally:
            self._loading = False

    def _reveal(self, keep: str, backup: bool) -> None:
        self.keep.set_sensitive(backup)
        self.count_revealer.set_reveal_child(backup and keep in ("count", "age"))
        self.days_revealer.set_reveal_child(backup and keep == "age")

    def _on_open(self, *_args: object) -> None:
        self._opener(self._show_error)

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        if self._loading:
            return
        self._save({key: switch.get_active()})

    def _on_keep(self, combo: Gtk.ComboBox) -> None:
        if self._loading:
            return
        self._save({"keep": combo.get_active_id()})

    def _on_number(self, field: Gtk.SpinButton, key: str) -> None:
        if self._loading:
            return
        self._pending[key] = field.get_value_as_int()
        if self._save_timer:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(SAVE_AFTER_MS, self._save_numbers)

    def _save_numbers(self) -> bool:
        self._save_timer = 0
        pending, self._pending = self._pending, {}
        self._save(pending)
        return False

    def _save(self, changes: Mapping[str, object]) -> None:
        try:
            self._client.set_module_settings("hosts", changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
