"""Asking a root helper to save a system file, from a tool's window: the pkexec command,
running it with the new content on its standard input, and what its exit status means.
The helpers themselves are in tuxtoys.core.rootfile.

Installed, pkexec runs a helper by its own path, which its polkit action names, so the
password dialog says what it is for. From a checkout it runs the checkout's helper
through env and Python, under polkit's general "run a program as administrator" instead.
GIO is imported only to run the command, so the rest is free of it.
"""

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from tuxtoys.core.nemo_action import INSTALLED_ROOT, LIBEXEC, PACKAGE_ROOT
from tuxtoys.core.rootfile import BAD, CHANGED, FAILED, SAVED

# pkexec's own: the password dialog was dismissed, or the user may not do it.
DISMISSED = 126
NOT_ALLOWED = 127

type Done = Callable[[int, str], None]


def command(
    launcher: str, module: str, arguments: Sequence[str], package_root: Path = PACKAGE_ROOT
) -> list[str]:
    """pkexec, the helper, and its arguments."""
    helper = LIBEXEC / launcher
    if package_root == INSTALLED_ROOT and helper.exists():
        program = [str(helper)]
    else:
        program = ["env", f"PYTHONPATH={package_root}", sys.executable, "-m", module]
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


def run(argv: list[str], content: bytes, done: Done) -> None:
    """Runs the command with `content` on its standard input, in the background, and
    hands its exit status and what it said on standard error to `done`.
    """
    from gi.repository import Gio, GLib

    try:
        process = Gio.Subprocess.new(
            argv, Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        )
    except GLib.Error as error:
        done(FAILED, error.message)
        return

    def finished(process: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            _ok, _out, err = process.communicate_finish(result)
        except GLib.Error as error:
            done(FAILED, error.message)
            return
        reason = err.get_data().decode("utf-8", "replace").strip() if err else ""
        done(process.get_exit_status(), reason)

    process.communicate_async(GLib.Bytes.new(content), None, finished)
