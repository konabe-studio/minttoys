"""New+, as the daemon runs it: it keeps its Nemo action, Save as template, in place (see
core.nemo_action). The templates themselves are managed on its page in the settings
window, and the action runs a program of its own (minttoys.newplus); neither needs the
daemon.
"""

from typing import ClassVar

from minttoys.core.i18n import N_, _
from minttoys.core.nemo_action import NemoAction
from minttoys.modules.base import Context, Module


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


class NewPlus(Module):
    id: ClassVar[str] = "newplus"
    name: ClassVar[str] = _("New+")
    description: ClassVar[str] = _(
        "Manages the templates Nemo offers under Create New Document, and saves files as templates."
    )

    def __init__(self, action: NemoAction | None = None) -> None:
        """The daemon uses the default; the tests hand in one with a folder of their own."""
        self.action = action or menu_item()

    def enable(self, context: Context) -> None:
        self.action.write()

    def disable(self) -> None:
        pass  # the action stays across sessions; see switched_off()

    def switched_off(self) -> None:
        self.action.remove()
