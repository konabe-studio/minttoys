"""Hosts File Editor, as the daemon runs it: it keeps its entry in the applications menu
while it is on, and serves its settings. The editor is a program of its own
(tuxtoys.hostseditor), which reads the settings through the daemon; saving goes through
pkexec, never through the daemon, which runs as the user.
"""

import shlex
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from tuxtoys import APP_ID
from tuxtoys.api import HOSTS_SETTINGS
from tuxtoys.core.i18n import N_, _
from tuxtoys.core.menu_entry import MenuEntry
from tuxtoys.core.nemo_action import PACKAGE_ROOT, program
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.hosts.options import Options

LAUNCHER = "tuxtoys-hosts-editor"
PROGRAM = "tuxtoys.hostseditor"


def menu_entry() -> MenuEntry:
    return MenuEntry(
        file_name=f"{APP_ID}.HostsEditor.desktop",
        name=N_("Hosts File Editor"),
        # TRANSLATORS: the tooltip of Hosts File Editor's entry in the applications menu.
        comment=N_("Edit the hosts file, which maps names to addresses on this computer"),
        launcher=LAUNCHER,
        module=PROGRAM,
    )


def editor_command(package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The command that opens the editor: the installed program, or the checkout's."""
    return shlex.split(program(package_root, LAUNCHER, PROGRAM, "")[0])


class HostsFileEditor(Module):
    id: ClassVar[str] = "hosts"
    name: ClassVar[str] = _("Hosts File Editor")
    description: ClassVar[str] = _("Edits /etc/hosts in a window, with a backup.")
    settings_types: ClassVar[Mapping[str, str]] = HOSTS_SETTINGS

    def __init__(self, adapt: Callable[[MenuEntry], MenuEntry] = lambda entry: entry) -> None:
        """The daemon writes the entry where the menu reads it; the tests `adapt` it to a
        folder of their own.
        """
        self.entry = adapt(menu_entry())

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self.entry.write()

    def disable(self) -> None:
        pass  # the menu entry stays across sessions; see switched_off()

    def switched_off(self) -> None:
        self.entry.remove()
