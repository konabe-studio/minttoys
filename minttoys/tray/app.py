"""The panel icon itself: an XApp.StatusIcon, Linux Mint's own, with a GTK menu.

A left click toggles Awake. The right-click menu starts a mode, sets whether the screen
stays on, and turns Awake off. The icon follows the daemon: it hears StateChanged, and
notices the daemon leaving and coming back.
"""

import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("XApp", "1.0")

from gi.repository import Gio, GLib, Gtk, XApp  # noqa: E402

from minttoys import BUS_NAME  # noqa: E402
from minttoys.api import AWAKE_INTERFACE, AWAKE_PATH, ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.core import clock  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.tray import view  # noqa: E402

# Where the icons are in a checkout, for running it before they are installed.
CHECKOUT_ICONS = Path(__file__).parents[2] / "data" / "icons" / "hicolor" / "symbolic" / "apps"
_hinted = False


class Client(Protocol):
    """What the icon needs from minttoys.client.Client, which is the real one."""

    def awake_state(self) -> dict: ...
    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None: ...
    def awake_stop(self) -> None: ...
    def awake_toggle(self) -> None: ...
    def awake_set_keep_screen(self, keep_screen: bool) -> None: ...


def icon(name: str) -> str:
    """The icon's name when the icon theme has it, as it does once installed, so the panel
    colours it to match; otherwise a file path to the checkout's copy.

    Cinnamon's panel applet (xapp-status) loads a file path only for a full-colour icon.
    Anything with "symbolic" in it, the path included, it looks up as a name in the theme,
    finds nothing, and shows an empty, clickable space. So until the icons are installed,
    the panel gets a copy under a name without the word, in the runtime directory, which
    goes at logout: the cup shows, though uncoloured.
    """
    if Gtk.IconTheme.get_default().has_icon(name):
        return name
    source = CHECKOUT_ICONS / f"{name}.svg"
    if not source.exists():
        return name
    global _hinted
    if not _hinted:
        _hinted = True
        print(
            "minttoys tray: the panel icons are not installed, so the panel shows them"
            " uncoloured and at full-colour size; sh scripts/dev-install.sh links them",
            file=sys.stderr,
        )
    copy = Path(GLib.get_user_runtime_dir()) / "minttoys" / f"{name.removesuffix('-symbolic')}.svg"
    content = source.read_bytes()
    if not copy.exists() or copy.read_bytes() != content:
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(content)
    return str(copy)


class Tray:
    def __init__(
        self,
        bus: Gio.DBusConnection,
        client: Client,
        now: Callable[[], datetime] = clock.now,
    ) -> None:
        self._client = client
        self._now = now
        self._state: dict | None = None
        self._problem = _("MintToys is not running.")
        self._refresh = 0

        self.status_icon = XApp.StatusIcon()
        self.status_icon.set_name("minttoys")
        self.status_icon.connect("activate", self._on_activate)
        self.menu = self._build_menu()
        self.status_icon.set_secondary_menu(self.menu)

        bus.signal_subscribe(
            BUS_NAME,
            AWAKE_INTERFACE,
            "StateChanged",
            AWAKE_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_state_changed,
        )
        self._watch = Gio.bus_watch_name_on_connection(
            bus, BUS_NAME, Gio.BusNameWatcherFlags.NONE, self._on_appeared, self._on_vanished
        )
        self._render()

    def update(self, state: dict | None, problem: str = "") -> None:
        """Shows `state`, or `problem` when there is none."""
        self._state = state
        self._problem = problem
        self._render()

    def _render(self) -> None:
        now = self._now()
        shown = view.present(self._state, now, self._problem)
        # Kept, since XApp.StatusIcon has setters but, in the XApp of Ubuntu 24.04, no getters.
        self.icon_name = icon(shown.icon)
        self.tooltip = shown.status
        self.status_icon.set_icon_name(self.icon_name)
        self.status_icon.set_tooltip_text(self.tooltip)
        self._status.set_label(shown.status)
        for item in self._actions:
            item.set_sensitive(shown.available)
        self._turn_off.set_sensitive(shown.on)
        self._keep_screen.handler_block(self._keep_screen_handler)
        self._keep_screen.set_active(shown.keep_screen)
        self._keep_screen.handler_unblock(self._keep_screen_handler)

        if self._refresh:
            GLib.source_remove(self._refresh)
            self._refresh = 0
        wait = view.refresh_in(self._state, now)
        if wait is not None:
            self._refresh = GLib.timeout_add_seconds(wait, self._on_refresh)

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()
        self._status = Gtk.MenuItem(label="")
        self._status.set_sensitive(False)
        menu.append(self._status)
        menu.append(Gtk.SeparatorMenuItem())

        self._actions: list[Gtk.MenuItem] = []

        def add(label: str, action: Callable[[], None]) -> Gtk.MenuItem:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item: self._run(action))
            menu.append(item)
            self._actions.append(item)
            return item

        add(_("Until turned off"), lambda: self._start("indefinite", 0, ""))
        for minutes in view.QUICK_MINUTES:
            add(
                view.quick_label(minutes),
                lambda minutes=minutes: self._start("duration", minutes, ""),
            )
        add(_("For a custom time…"), self._ask_duration)
        add(_("Until a time of day…"), self._ask_until)
        menu.append(Gtk.SeparatorMenuItem())

        self._keep_screen = Gtk.CheckMenuItem(label=_("Keep the screen on"))
        self._keep_screen_handler = self._keep_screen.connect(
            "toggled",
            lambda item: self._run(lambda: self._client.awake_set_keep_screen(item.get_active())),
        )
        menu.append(self._keep_screen)
        self._actions.append(self._keep_screen)
        menu.append(Gtk.SeparatorMenuItem())

        self._turn_off = add(_("Turn off"), self._client.awake_stop)
        menu.show_all()
        return menu

    def _start(self, mode: str, minutes: int, until: str) -> None:
        keep_screen = bool(self._state and self._state["keep_screen"])
        self._client.awake_start(mode, minutes, until, keep_screen)

    def _run(self, action: Callable[[], None]) -> None:
        """Runs a menu action; the new state comes back through StateChanged."""
        try:
            action()
        except NotRunning:
            self.update(None, _("MintToys is not running."))
        except ModuleOff:
            self.update(None, _("Awake is switched off in MintToys."))
        except Refused as error:
            self._error(_("MintToys refused: {reason}").format(reason=error))
            self._render()  # puts the check box back if the change did not happen

    def _on_activate(self, status_icon: XApp.StatusIcon, button: int, time: int) -> None:
        if button == 1 and self._state is not None:
            self._run(self._client.awake_toggle)

    def _on_state_changed(self, *arguments: object) -> None:
        parameters = arguments[5]
        assert isinstance(parameters, GLib.Variant)
        (state,) = parameters.unpack()
        self.update(state)

    def _on_appeared(self, connection: Gio.DBusConnection, name: str, owner: str) -> None:
        try:
            self.update(self._client.awake_state())
        except NotRunning:
            self.update(None, _("MintToys is not running."))
        except ModuleOff:
            self.update(None, _("Awake is switched off in MintToys."))

    def _on_vanished(self, connection: Gio.DBusConnection, name: str) -> None:
        self.update(None, _("MintToys is not running."))

    def _on_refresh(self) -> bool:
        self._refresh = 0
        self._render()
        return GLib.SOURCE_REMOVE

    def _ask_duration(self) -> None:
        dialog, hours, minutes = _time_dialog(
            _("Keep the computer awake for"), 1, 0, 99, wrap=False
        )
        if dialog.run() == Gtk.ResponseType.OK:
            total = hours.get_value_as_int() * 60 + minutes.get_value_as_int()
            if total > 0:
                self._start("duration", total, "")
        dialog.destroy()

    def _ask_until(self) -> None:
        hour, minute = view.next_full_hour(self._now())
        dialog, hours, minutes = _time_dialog(
            _("Keep the computer awake until"), hour, minute, 23, wrap=True
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self._start(
                "until", 0, f"{hours.get_value_as_int():02}:{minutes.get_value_as_int():02}"
            )
        dialog.destroy()

    def _error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text=message
        )
        dialog.run()
        dialog.destroy()


def _time_dialog(
    title: str, hour: int, minute: int, most_hours: int, *, wrap: bool
) -> tuple[Gtk.Dialog, Gtk.SpinButton, Gtk.SpinButton]:
    """A small dialog with an hours and a minutes field. With `wrap`, it is a time of day:
    both fields go round and show two digits.
    """
    dialog = Gtk.Dialog(title=title)
    dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Start"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)
    hours = Gtk.SpinButton.new_with_range(0, most_hours, 1)
    minutes = Gtk.SpinButton.new_with_range(0, 59, 1 if wrap else 5)
    hours.set_value(hour)
    minutes.set_value(minute)
    row = Gtk.Box(spacing=6, margin=12)
    if wrap:
        for field in (hours, minutes):
            field.set_wrap(True)
            field.connect("output", _two_digits)
        row.pack_start(hours, False, False, 0)
        row.pack_start(Gtk.Label(label=":"), False, False, 0)
        row.pack_start(minutes, False, False, 0)
    else:
        row.pack_start(hours, False, False, 0)
        row.pack_start(Gtk.Label(label=_("h")), False, False, 0)
        row.pack_start(minutes, False, False, 0)
        row.pack_start(Gtk.Label(label=_("min")), False, False, 0)
    for field in (hours, minutes):
        field.set_activates_default(True)
    dialog.get_content_area().add(row)
    dialog.show_all()
    return dialog, hours, minutes


def _two_digits(field: Gtk.SpinButton) -> bool:
    field.set_text(f"{field.get_value_as_int():02}")
    return True
