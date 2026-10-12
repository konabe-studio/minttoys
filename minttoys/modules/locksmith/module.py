"""File Locksmith, as the daemon runs it: it keeps its Nemo action in place (see
core.nemo_action). The window the action opens is a program of its own
(minttoys.locksmith) and needs no daemon.
"""

from typing import ClassVar

from minttoys.core.i18n import N_, _
from minttoys.core.nemo_action import NemoAction
from minttoys.modules.base import Context, Module


def menu_item() -> NemoAction:
    return NemoAction(
        file_name="io.github.konabe_studio.MintToys.locksmith.nemo_action",
        # TRANSLATORS: File Locksmith's item in Nemo's right-click menu.
        name=N_("What is using this?"),
        # TRANSLATORS: the tooltip of File Locksmith's item in Nemo's right-click menu.
        comment=N_("Shows the processes that hold it open, and lets you end them."),
        launcher="minttoys-locksmith",
        module="minttoys.locksmith",
        icon="changes-prevent-symbolic",
    )


class FileLocksmith(Module):
    id: ClassVar[str] = "locksmith"
    name: ClassVar[str] = _("File Locksmith")
    description: ClassVar[str] = _(
        "Shows which processes hold a file or a folder, from Nemo's right-click menu."
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
