"""A page for a tool with nothing to set: whether it is on, and how to use it."""

from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk  # noqa: E402
from xapp.SettingsWidgets import SettingsPage, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleInfo, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402


class SimplePage(SettingsPage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        module_id: str,
        title: str,
        description: str,
        switch_label: str,
        how_to: Sequence[str],
    ) -> None:
        super().__init__()
        self._client = client
        self._show_error = show_error
        self._module_id = module_id
        self._shown_enabled: bool | None = None
        self._loading = False

        self.problem = Gtk.Label(wrap=True, xalign=0)
        self.problem.get_style_context().add_class("dim-label")
        self.problem.set_no_show_all(True)
        self.pack_start(self.problem, False, False, 0)

        section = self.add_section(title, description)
        self.enabled = Switch(switch_label)
        self.enabled.content_widget.connect("notify::active", self._on_enabled)
        section.add_row(self.enabled)

        # TRANSLATORS: the heading over the steps that tell how to use a tool.
        steps = self.add_section(_("How to use it"))
        for line in how_to:
            steps.add_row(Text(line))
        self.refresh()

    def refresh(self) -> None:
        info: ModuleInfo | None = None
        problem = ""
        try:
            info = next((i for i in self._client.modules() if i.id == self._module_id), None)
        except NotRunning:
            problem = _("TuxToys is not running.")
        except Refused as error:
            problem = _("TuxToys refused: {reason}").format(reason=error)
        if info is None and not problem:
            problem = _(
                "The TuxToys service running now does not have this tool. Log out and back"
                " in to start the new one."
            )
        if info and info.state == "failed":
            problem = _("Could not be switched on: {error}").format(error=info.error)
        self._shown_enabled = info.state == "on" if info else None
        self._loading = True
        try:
            self.enabled.set_sensitive(info is not None)
            self.enabled.content_widget.set_active(bool(self._shown_enabled))
        finally:
            self._loading = False
        self.problem.set_text(problem)
        self.problem.set_visible(bool(problem))

    def show_settings(self, settings: object) -> None:
        """A tool with nothing to set has nothing to show; here for the window's sake."""

    def _on_enabled(self, switch: Gtk.Switch, _spec: object) -> None:
        enabled = switch.get_active()
        if self._loading or self._shown_enabled is None or enabled == self._shown_enabled:
            return
        try:
            self._client.set_module_enabled(self._module_id, enabled)
        except NotRunning:
            pass  # refresh() says so
        except Refused as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
