"""Environment Variables' page: whether it is on, how its variables reach the session, and
a button that opens its window, where everything is set.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib  # noqa: E402
from xapp.SettingsWidgets import Button  # noqa: E402

from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.envvars.module import editor_command  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402


def open_window(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(editor_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


class EnvVarsPage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_window,
    ) -> None:
        """The tests hand in an opener of their own."""
        self._opener = opener
        super().__init__(
            client,
            show_error,
            "envvars",
            _("Environment Variables"),
            _("Your environment variables, profiles of them, and the system's."),
            _("Use Environment Variables"),
            [
                _(
                    "Your variables are loaded by ~/.xsessionrc when you log in, and by"
                    " ~/.bashrc in every new terminal. Switching the tool off takes those"
                    " lines away again."
                ),
                _(
                    "The system's variables are /etc/environment, for every user; changing"
                    " them asks for an administrator's password."
                ),
            ],
        )
        # TRANSLATORS: the heading over the button that opens the tool.
        section = self.add_section(_("Open"))
        section.add_row(Button(_("Open Environment Variables"), self._on_open))

    def _on_open(self, *_args: object) -> None:
        self._opener(self._show_error)
