"""File Locksmith's words, free of GTK, for its window."""

import posixpath
from collections.abc import Sequence

from minttoys.core.i18n import _, ngettext


def heading(targets: Sequence[str]) -> str:
    """What the window is about: one file or folder by name, several by count."""
    if len(targets) == 1:
        name = posixpath.basename(posixpath.normpath(targets[0])) or targets[0]
        # TRANSLATORS: the heading of File Locksmith's window; {name} is a file or a folder.
        return _("What is using {name}").format(name=name)
    # TRANSLATORS: the heading of File Locksmith's window for several files and folders.
    return ngettext(
        "What is using {count} item", "What is using {count} items", len(targets)
    ).format(count=len(targets))


def held(paths: Sequence[str], targets: Sequence[str]) -> str:
    """What a process holds, as the list shows it: within a chosen folder, the path from
    that folder; otherwise the name of the file.
    """
    shown = []
    for path in paths:
        relative = path
        for target in targets:
            folder = posixpath.normpath(target)
            if path.startswith(folder.rstrip("/") + "/"):
                relative = posixpath.relpath(path, folder)
                break
        else:
            relative = posixpath.basename(path) or path
        shown.append(relative)
    return ", ".join(shown)


def nothing() -> str:
    return _("Nothing of yours is using it right now.")


def hidden() -> str:
    return _("Processes of other users, the system's among them, cannot be shown.")
