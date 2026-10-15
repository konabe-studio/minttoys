"""How Environment Variables asks for /etc/environment to be saved: the pkexec command for
its root helper. Free of GTK; see tuxtoys.core.pkexec. Its backups are kept as Hosts File
Editor's are by default: 15 days, the newest 5 always.
"""

from pathlib import Path

from tuxtoys.core import pkexec
from tuxtoys.core.nemo_action import PACKAGE_ROOT

LAUNCHER = "tuxtoys-environment-save"


def command(expect: str, backup: bool, package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The command that saves, given the SHA-256 of the file as it was read; with a
    backup on the first save of a session.
    """
    arguments = ["--expect", expect]
    if backup:
        arguments += ["--backup", "--keep", "age", "--count", "5", "--days", "15"]
    return pkexec.command(LAUNCHER, "tuxtoys.modules.envvars.save", arguments, package_root)
