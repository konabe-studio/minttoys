"""New+, as the daemon runs it: it keeps its two Nemo actions in place (see
core.nemo_action). Save as template copies a file into the templates folder; New from
template opens a window that makes a file or a folder from one. The templates themselves
are managed on its page in the settings window. Neither action needs the daemon: the
window is told New+'s settings in the action's command, which is written again when they
change.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from minttoys.api import NEWPLUS_SETTINGS
from minttoys.core.i18n import N_, _
from minttoys.core.nemo_action import NemoAction
from minttoys.modules.base import Context, Module
from minttoys.modules.newplus.options import Options


def menu_item() -> NemoAction:
    return NemoAction(
        file_name="io.github.konabe_studio.MintToys.newplus.nemo_action",
        # TRANSLATORS: New+'s item in Nemo's right-click menu.
        name=N_("Save as template"),
        # TRANSLATORS: the tooltip of New+'s item in Nemo's right-click menu.
        comment=N_("Copies it to your templates, offered under Create New Document."),
        launcher="minttoys-save-template",
        module="minttoys.newplus",
        icon="document-new-symbolic",
        # Nemo offers files as templates; a folder there is a submenu, not a template.
        extensions="nodirs;",
    )


def create_item(options: Options) -> NemoAction:
    return NemoAction(
        file_name="io.github.konabe_studio.MintToys.newplus-create.nemo_action",
        # TRANSLATORS: New+'s item in Nemo's right-click menu, on a folder or its background.
        name=N_("New from template…"),
        # TRANSLATORS: the tooltip of New from template in Nemo's right-click menu.
        comment=N_("Makes a file or a folder from one of your templates."),
        launcher="minttoys-new-from-template",
        module="minttoys.newitem",
        icon="list-add-symbolic",
        # On the background of a folder, where nothing is chosen, and on chosen folders.
        selection="any",
        extensions="dir;",
        arguments=" ".join([*options.arguments(), "%P", "%F"]),
    )


class NewPlus(Module):
    id: ClassVar[str] = "newplus"
    name: ClassVar[str] = _("New+")
    description: ClassVar[str] = _(
        "Makes files and folders from your templates, and saves files as templates."
    )
    settings_types: ClassVar[Mapping[str, str]] = NEWPLUS_SETTINGS

    def __init__(self, adapt: Callable[[NemoAction], NemoAction] = lambda action: action) -> None:
        """The daemon writes the actions where Nemo reads them; the tests `adapt` each to a
        folder of their own.
        """
        self._adapt = adapt
        self.action = adapt(menu_item())

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def create_action(self, options: Options) -> NemoAction:
        return self._adapt(create_item(options))

    def enable(self, context: Context) -> None:
        self.action.write()
        self.create_action(Options.read(context.settings)).write()

    def disable(self) -> None:
        pass  # the actions stay across sessions; see switched_off()

    def switched_off(self) -> None:
        self.action.remove()
        self.create_action(Options()).remove()

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        self.create_action(Options.read(settings)).write()
