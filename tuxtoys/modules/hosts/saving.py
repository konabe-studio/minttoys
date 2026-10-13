"""How Hosts File Editor asks for /etc/hosts to be saved: the pkexec command for the root
helper (see save.py), and what its exit status means. Free of GTK.

Installed, pkexec runs the helper by its own path, which the polkit action names, so the
password dialog says what it is for. From a checkout it runs the checkout's helper
through env and Python, under polkit's general "run a program as administrator" instead.
"""

import sys
from pathlib import Path

from tuxtoys.core.nemo_action import INSTALLED_ROOT, LIBEXEC, PACKAGE_ROOT
from tuxtoys.modules.hosts.options import Options
from tuxtoys.modules.hosts.save import BAD, CHANGED, SAVED

LAUNCHER = "tuxtoys-hosts-save"
# pkexec's own: the password dialog was dismissed, or the user may not do it.
DISMISSED = 126
NOT_ALLOWED = 127


def command(
    expect: str, options: Options, backup: bool, package_root: Path = PACKAGE_ROOT
) -> list[str]:
    """The command that saves, given the SHA-256 of the file as it was read."""
    helper = LIBEXEC / LAUNCHER
    if package_root == INSTALLED_ROOT and helper.exists():
        program = [str(helper)]
    else:
        program = [
            "env",
            f"PYTHONPATH={package_root}",
            sys.executable,
            "-m",
            "tuxtoys.modules.hosts.save",
        ]
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
    return ["pkexec", *program, *arguments]


def outcome(status: int) -> str:
    """What an exit status means: saved, changed, dismissed, not-allowed, bad or failed."""
    return {
        SAVED: "saved",
        CHANGED: "changed",
        DISMISSED: "dismissed",
        NOT_ALLOWED: "not-allowed",
        BAD: "bad",
    }.get(status, "failed")
