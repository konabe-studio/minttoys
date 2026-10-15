"""How Hosts File Editor asks for /etc/hosts to be saved: the pkexec command for its root
helper, with the backup settings. Free of GTK; see tuxtoys.core.pkexec.
"""

from pathlib import Path

from tuxtoys.core import pkexec
from tuxtoys.core.nemo_action import PACKAGE_ROOT
from tuxtoys.core.pkexec import DISMISSED, NOT_ALLOWED, outcome
from tuxtoys.modules.hosts.options import Options

LAUNCHER = "tuxtoys-hosts-save"

__all__ = ["DISMISSED", "LAUNCHER", "NOT_ALLOWED", "command", "outcome"]


def command(
    expect: str, options: Options, backup: bool, package_root: Path = PACKAGE_ROOT
) -> list[str]:
    """The command that saves, given the SHA-256 of the file as it was read."""
    arguments = ["--expect", expect]
    if backup and options.backup:
        arguments += [
            "--backup",
            "--keep",
            options.keep,
            "--count",
            str(options.count),
            "--days",
            str(options.days),
        ]
    return pkexec.command(LAUNCHER, "tuxtoys.modules.hosts.save", arguments, package_root)
