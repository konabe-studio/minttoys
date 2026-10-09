"""The Overview: every tool with a switch and a line on what it does, the way PowerToys'
dashboard lists them. On the first open it also greets the user, which makes it the
onboarding too.
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk  # noqa: E402
from xapp.SettingsWidgets import SettingsPage, SettingsWidget  # noqa: E402

from minttoys.api import ModuleInfo, NotRunning, Refused  # noqa: E402
from minttoys.core.i18n import _  # noqa: E402
from minttoys.settings.lightswitch_page import Client  # noqa: E402


class ToolRow(SettingsWidget):
    """A tool's name and what it does, with the switch that turns it on or off."""

    def __init__(self) -> None:
        super().__init__()
        self.name = Gtk.Label(xalign=0)
        self.description = Gtk.Label(xalign=0, wrap=True)
        self.description.get_style_context().add_class("dim-label")
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        texts.pack_start(self.name, False, False, 0)
        texts.pack_start(self.description, False, False, 0)
        self.content_widget = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.pack_start(texts, True, True, 0)
        self.pack_end(self.content_widget, False, False, 0)

    def show_info(self, info: ModuleInfo) -> None:
        self.name.set_text(info.name)
        text = info.description
        if info.state == "failed":
            # TRANSLATORS: under a tool's description in the Overview, when it failed.
            text += "\n" + _("Could not be switched on: {error}").format(error=info.error)
        self.description.set_text(text)
        self.content_widget.set_active(info.state == "on")


class OverviewPage(SettingsPage):
    def __init__(self, client: Client, show_error: Callable[[str], None], *, welcome: bool) -> None:
        super().__init__()
        self._client = client
        self._show_error = show_error
        self._loading = False
        self.rows: dict[str, ToolRow] = {}

        self.welcome = Gtk.Label(wrap=True, xalign=0)
        self.welcome.set_text(
            _(
                "Welcome to MintToys. Switch on the tools you want to use. Each one has a"
                " page of its own in the sidebar."
            )
        )
        self.welcome.set_no_show_all(True)
        self.welcome.set_visible(welcome)
        self.pack_start(self.welcome, False, False, 0)

        self.problem = Gtk.Label(wrap=True, xalign=0)
        self.problem.get_style_context().add_class("dim-label")
        self.problem.set_no_show_all(True)
        self.pack_start(self.problem, False, False, 0)

        self.tools = self.add_section(_("Tools"))
        self.refresh()

    def refresh(self) -> None:
        """Lists the tools as the daemon has them. Without the daemon the switches go grey
        and the page says why.
        """
        try:
            infos = self._client.modules()
        except (NotRunning, Refused) as error:
            if isinstance(error, NotRunning):
                problem = _("MintToys is not running.")
            else:
                problem = _("MintToys refused: {reason}").format(reason=error)
            self._set_problem(problem)
            for row in self.rows.values():
                row.set_sensitive(False)
            return
        self._set_problem("")
        self._loading = True
        try:
            for info in infos:
                row = self.rows.get(info.id)
                if row is None:
                    row = self.rows[info.id] = ToolRow()
                    row.content_widget.connect("notify::active", self._on_switch, info.id)
                    self.tools.add_row(row)
                    row.show_all()
                row.show_info(info)
                row.set_sensitive(True)
        finally:
            self._loading = False

    def _set_problem(self, text: str) -> None:
        self.problem.set_text(text)
        self.problem.set_visible(bool(text))

    def _on_switch(self, switch: Gtk.Switch, _spec: object, module_id: str) -> None:
        if self._loading:
            return
        try:
            self._client.set_module_enabled(module_id, switch.get_active())
        except NotRunning:
            pass  # refresh() below says so
        except Refused as error:
            self._show_error(_("MintToys refused: {reason}").format(reason=error))
        self.refresh()
