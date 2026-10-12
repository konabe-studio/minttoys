"""The Nemo action File Locksmith adds to the right-click menu: what the file says, and where
the program it runs is. Free of GTK.

Nemo reads actions from ~/.local/share/nemo/actions and watches the folder, so a file put
there shows at once. With an absolute path in Dependencies, Nemo shows the action only
while that file exists (nemo-action.c), so removing the package hides it on its own.
"""

import os
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path

ACTION_NAME = "io.github.konabe_studio.MintToys.locksmith.nemo_action"
INSTALLED_ROOT = Path("/usr/lib/minttoys")
INSTALLED_PROGRAM = Path("/usr/libexec/minttoys/minttoys-locksmith")
ICON = "changes-prevent-symbolic"


def actions_dir(environ: Mapping[str, str] = os.environ) -> Path:
    data_home = environ.get("XDG_DATA_HOME", "")
    root = Path(data_home) if os.path.isabs(data_home) else Path.home() / ".local" / "share"
    return root / "nemo" / "actions"


def program(package_root: Path) -> tuple[str, str]:
    """The command the action runs, and the file it depends on: the installed launcher, or
    the checkout's module when MintToys runs from a checkout.
    """
    if package_root == INSTALLED_ROOT and INSTALLED_PROGRAM.exists():
        return f"{INSTALLED_PROGRAM} %F", str(INSTALLED_PROGRAM)
    main = package_root / "minttoys" / "locksmith" / "__main__.py"
    command = (
        f"env PYTHONPATH={shlex.quote(str(package_root))} "
        f"{shlex.quote(sys.executable)} -m minttoys.locksmith %F"
    )
    return command, str(main)


def render(
    names: Mapping[str, str], comments: Mapping[str, str], command: str, dependency: str
) -> str:
    """The action file. `names` and `comments` map a language code to the text, "" to the
    English one.
    """
    lines = ["[Nemo Action]"]
    for key, texts in (("Name", names), ("Comment", comments)):
        lines.append(f"{key}={texts['']}")
        lines.extend(f"{key}[{lang}]={text}" for lang, text in sorted(texts.items()) if lang)
    lines += [
        f"Exec={command}",
        f"Icon-Name={ICON}",
        "Selection=Any",
        "Extensions=any;",
        "Quote=double",
        f"Dependencies={dependency};",
    ]
    return "\n".join(lines) + "\n"
