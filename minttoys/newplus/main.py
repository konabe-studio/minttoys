"""Save as template: copies the files chosen in Nemo into the templates folder, and says so
in a notification. Run by New+'s Nemo action; needs no daemon.
"""

import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from minttoys.core.i18n import _, ngettext
from minttoys.modules.newplus import templates


def config_home(environ: dict[str, str] | None = None) -> Path:
    environ = dict(os.environ) if environ is None else environ
    value = environ.get("XDG_CONFIG_HOME", "")
    return Path(value) if os.path.isabs(value) else Path.home() / ".config"


def save(sources: Sequence[str], folder: Path | None, notify: Callable[[str, str], None]) -> int:
    """Copies `sources` into `folder` and tells the user. Exit status: 0 when all were
    saved, 1 otherwise.
    """
    if folder is None:
        notify(
            _("No templates folder"),
            _("Set one up on New+'s page in MintToys, then try again."),
        )
        return 1
    saved, failed = [], []
    for source in sources:
        try:
            saved.append(templates.add(folder, Path(source)).name)
        except OSError:
            failed.append(os.path.basename(source))
    if saved:
        if len(saved) == 1:
            # TRANSLATORS: the notification after Save as template; {name} is the template.
            body = _("{name} is offered under Create New Document now.").format(name=saved[0])
        else:
            body = ngettext(
                "{count} file is offered under Create New Document now.",
                "{count} files are offered under Create New Document now.",
                len(saved),
            ).format(count=len(saved))
        notify(_("Saved as template"), body)
    if failed:
        notify(_("Could not save as template"), ", ".join(failed))
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    sources = sys.argv[1:] if argv is None else list(argv)
    if not sources:
        print(_("Usage: minttoys-save-template FILE..."), file=sys.stderr)
        return 2
    folder = templates.templates_dir(Path.home(), config_home())

    def notify(summary: str, body: str) -> None:
        try:
            from gi.repository import Gio

            from minttoys.core import notifications

            notifications.send_now(Gio.bus_get_sync(Gio.BusType.SESSION), summary, body)
        except Exception:
            print(f"{summary}: {body}", file=sys.stderr)

    return save(sources, folder, notify)
