"""The settings window: an XApp.PreferencesWindow with a page per module. Its sidebar
shows itself once there are two pages.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("XApp", "1.0")

from gi.repository import Gio, Gtk, XApp  # noqa: E402

from minttoys import APP_ID, BUS_NAME  # noqa: E402
from minttoys.api import AWAKE_INTERFACE, AWAKE_PATH  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.settings.awake_page import AwakePage, Client  # noqa: E402


class SettingsWindow(XApp.PreferencesWindow):
    def __init__(
        self, application: Gtk.Application, bus: Gio.DBusConnection, client: Client
    ) -> None:
        super().__init__(application=application)
        self.set_title(_("MintToys"))
        self.set_icon_name(APP_ID)
        self.set_default_size(640, 560)
        self.awake = AwakePage(client, self._error)
        # Scrolls rather than grows when a translation makes the page longer.
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add(self.awake)
        self.add_page(scroller, "awake", _("Awake"))

        bus.signal_subscribe(
            BUS_NAME,
            AWAKE_INTERFACE,
            "SettingsChanged",
            AWAKE_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            lambda *arguments: self.awake.show_settings(arguments[5].unpack()[0]),
        )
        # Follows the daemon leaving and coming back, so the page never shows settings
        # that are not there any more.
        self._watch = Gio.bus_watch_name_on_connection(
            bus,
            BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            lambda *_: self.awake.refresh(),
            lambda *_: self.awake.refresh(),
        )

    def _error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=message,
        )
        dialog.run()
        dialog.destroy()
