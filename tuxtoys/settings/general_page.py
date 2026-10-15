"""The General page, as PowerToys has one: the version and where to read more or report a
problem, whether the panel icon starts with the session, a backup of every tool's
settings, and a word on privacy.

Left out on purpose: checking for updates (the Update Manager does it for the package),
the language and the theme (TuxToys follows Linux Mint's), running as administrator
(only what needs it asks for a password), and diagnostic data (there is none).
"""

import os
import shlex
import signal
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, SettingsPage, SettingsWidget, Switch, Text  # noqa: E402

from tuxtoys import APP_ID, VERSION  # noqa: E402
from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.nemo_action import PACKAGE_ROOT, program  # noqa: E402
from tuxtoys.settings import backup, startup  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402

PROJECT = "https://github.com/konabe-studio/tuxtoys"
TRAY_NAME = f"{APP_ID}.Tray"


class Tray(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class TrayProcess:
    """The panel icon's own process: started like autostart does, stopped with SIGTERM,
    which it takes as a request to quit.
    """

    def __init__(self, bus: Gio.DBusConnection | None) -> None:
        self._bus = bus

    def start(self) -> None:
        command = shlex.split(program(PACKAGE_ROOT, "tuxtoys-tray", "tuxtoys.tray", "")[0])
        with suppress(GLib.Error):
            Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)

    def stop(self) -> None:
        if self._bus is None:
            return
        try:
            (pid,) = self._bus.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "GetConnectionUnixProcessID",
                GLib.Variant("(s)", (TRAY_NAME,)),
                GLib.VariantType("(u)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            ).unpack()
        except GLib.Error:
            return  # not running
        with suppress(OSError):
            os.kill(pid, signal.SIGTERM)


class Links(SettingsWidget):
    """The project's links in a row, as PowerToys has them under its name."""

    def __init__(self) -> None:
        super().__init__()
        box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4)
        self.links = {}
        for key, label, uri in (
            ("docs", _("Documentation"), f"{PROJECT}#readme"),
            ("code", _("GitHub repository"), PROJECT),
            ("bug", _("Report a bug"), f"{PROJECT}/issues/new?labels=bug"),
            ("idea", _("Request a feature"), f"{PROJECT}/issues/new?labels=enhancement"),
        ):
            link = Gtk.LinkButton(uri=uri, label=label)
            self.links[key] = link
            box.add(link)
        self.pack_start(box, True, True, 0)


class GeneralPage(SettingsPage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        tray: Tray,
        autostart: Callable[[], Path] = startup.autostart_dir,
        choose: Callable[[bool], Path | None] | None = None,
    ) -> None:
        """The tests hand in a panel icon, an autostart folder and a file chooser of
        their own.
        """
        super().__init__()
        self._client = client
        self._show_error = show_error
        self._tray = tray
        self._autostart = autostart
        self._choose = choose or self._choose_file
        self._loading = False

        about = self.add_section(_("TuxToys"), _("Power-user utilities for Linux Mint Cinnamon."))
        version = Text(_("Version {version}").format(version=VERSION))
        about.add_row(version)
        self.links = Links()
        about.add_row(self.links)

        start = self.add_section(_("Startup"))
        self.panel_icon = Switch(_("Show the panel icon"))
        self.panel_icon.content_widget.connect("notify::active", self._on_panel_icon)
        start.add_row(self.panel_icon)
        note = Text(
            _(
                "It starts with your session. The service the tools run in always starts,"
                " with or without it."
            )
        )
        note.content_widget.get_style_context().add_class("dim-label")
        start.add_row(note)

        self.backups = self.add_section(
            _("Backup and restore"),
            _("Every tool's settings, and whether it is on, in one file."),
        )
        self.backups.add_row(Button(_("Back up the settings…"), self._on_back_up))
        self.backups.add_row(Button(_("Restore the settings…"), self._on_restore))

        privacy = self.add_section(_("Privacy"))
        privacy.add_row(
            Text(
                _(
                    "TuxToys collects no data about you or your computer, and sends nothing"
                    " anywhere."
                )
            )
        )
        self.refresh()

    def refresh(self) -> None:
        self._loading = True
        try:
            self.panel_icon.content_widget.set_active(startup.starts(self._autostart()))
        finally:
            self._loading = False

    def show_settings(self, settings: object) -> None:
        """The General page shows no tool's settings; here for the window's sake."""

    def _on_panel_icon(self, switch: Gtk.Switch, _spec: object) -> None:
        if self._loading:
            return
        enabled = switch.get_active()
        try:
            startup.set_starts(self._autostart(), enabled)
        except OSError as error:
            self._show_error(error.strerror or str(error))
            self.refresh()
            return
        if enabled:
            self._tray.start()
        else:
            self._tray.stop()

    # Backup and restore.

    def _choose_file(self, saving: bool) -> Path | None:
        dialog = Gtk.FileChooserNative(
            title=_("Back up the settings") if saving else _("Restore the settings"),
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.SAVE if saving else Gtk.FileChooserAction.OPEN,
        )
        if saving:
            dialog.set_do_overwrite_confirmation(True)
            dialog.set_current_name("tuxtoys-settings.json")
        json_files = Gtk.FileFilter()
        json_files.set_name(_("TuxToys settings"))
        json_files.add_pattern("*.json")
        dialog.add_filter(json_files)
        chosen = None
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            chosen = Path(dialog.get_filename())
        dialog.destroy()
        return chosen

    def _on_back_up(self, *_args: object) -> None:
        path = self._choose(True)
        if path is None:
            return
        try:
            infos = self._client.modules()
            settings = {}
            for info in infos:
                with suppress(ModuleOff, Refused):
                    settings[info.id] = self._client.module_settings(info.id)
            path.write_text(backup.export(infos, settings), encoding="utf-8")
        except NotRunning:
            self._show_error(_("TuxToys is not running."))
        except (Refused, OSError) as error:
            self._show_error(getattr(error, "strerror", None) or str(error))

    def _on_restore(self, *_args: object) -> None:
        path = self._choose(False)
        if path is None:
            return
        try:
            restores, unknown = backup.read(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            self._show_error(getattr(error, "strerror", None) or str(error))
            return
        except backup.NotABackup:
            self._show_error(_("This is not a file of TuxToys settings."))
            return
        refused = []
        try:
            for restore in restores:
                try:
                    # Only what differs: a value a tool keeps but takes no part in setting,
                    # such as Light Switch's day mode before it is first switched on, is
                    # left alone rather than refused.
                    current: dict = {}
                    with suppress(ModuleOff, Refused):
                        current = self._client.module_settings(restore.tool)
                    changes = {
                        key: value
                        for key, value in restore.settings.items()
                        if current.get(key) != value
                    }
                    if changes:
                        self._client.set_module_settings(restore.tool, changes)
                    if restore.enabled is not None:
                        self._client.set_module_enabled(restore.tool, restore.enabled)
                except (ModuleOff, Refused) as error:
                    refused.append(f"{restore.tool}: {error}")
        except NotRunning:
            self._show_error(_("TuxToys is not running."))
            return
        lines = []
        if unknown:
            lines.append(
                _("This version of TuxToys does not have these tools: {tools}").format(
                    tools=", ".join(unknown)
                )
            )
        if refused:
            lines.append(_("These could not be restored: {what}").format(what="; ".join(refused)))
        if lines:
            self._show_error("\n".join(lines))
