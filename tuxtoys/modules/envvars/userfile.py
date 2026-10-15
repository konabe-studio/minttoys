"""The user's variables as a file the session reads, and the lines that load it. Free of
the file system.

Debian's /etc/X11/Xsession, which LightDM runs on LMDE, and Ubuntu's lightdm-session on
Linux Mint 22 both read ~/.xsessionrc before Cinnamon starts; ~/.bashrc is read by every
new terminal. One marked line in each loads ~/.config/tuxtoys/environment, which
TuxToys writes from its settings: the user's variables, then the applied profile's.

The file is plain sh, read by dash and bash alike. It sets the variables once per
version of itself: a terminal opened inside the session that read it does not add
"$HOME/bin" to PATH a second time, but one opened after a change picks the change up.
"""

import hashlib

from tuxtoys.modules.envvars.variables import Variables, shell_quoted

MARK = "# TuxToys: Environment Variables"
_GUARD = "TUXTOYS_ENVIRONMENT"
HEADER = (
    "# Written by TuxToys from its Environment Variables settings: a change made here is replaced."
)


def render(user: Variables, profile: Variables) -> str:
    lines = [f"{name}={shell_quoted(value)}" for name, value in (*user, *profile)]
    names = list(dict.fromkeys(name for name, _value in (*user, *profile)))
    version = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]
    body = [f"    {line}" for line in lines]
    if names:
        body.append(f"    export {' '.join(names)}")
    body.append(f"    export {_GUARD}={version}")
    return "\n".join(
        [
            HEADER,
            f'if [ "${{{_GUARD}-}}" != "{version}" ]; then',
            *body,
            "fi",
            "",
        ]
    )


def hook(path: str) -> str:
    """The line that loads the file at `path`, if it is there."""
    quoted = shell_quoted(path)
    return f"[ -r {quoted} ] && . {quoted}  {MARK}"


def with_hook(text: str, line: str) -> str:
    """`text` with the loading line at its end, once, replacing an older one."""
    kept = [old for old in text.splitlines() if not old.endswith(MARK)]
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join([*kept, "", line] if kept else [line]) + "\n"


def without_hook(text: str) -> str:
    """`text` without the loading line, and without the blank line put in before it."""
    lines = text.splitlines()
    kept = []
    for index, line in enumerate(lines):
        if line.endswith(MARK):
            if kept and not kept[-1].strip() and index == len(lines) - 1:
                kept.pop()
            continue
        kept.append(line)
    return "\n".join(kept) + "\n" if kept else ""
