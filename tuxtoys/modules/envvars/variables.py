"""Environment variables as Environment Variables handles them. Free of GTK and of the
file system.

A name is a shell name: letters, digits and "_", not starting with a digit. A value is
one line of text. In a user's or a profile's value, $NAME and ${NAME} stand for another
variable's value, so "$HOME/bin:$PATH" puts a folder in front of the search path, as a
shell would; any other "$" is a "$". /etc/environment has no such references: pam_env
reads its values as they are.

What applies, in the order PowerToys has it, the later winning: the system's variables,
then the user's, then the applied profile's.
"""

import re
from collections.abc import Iterable, Mapping, Sequence

type Variables = Sequence[tuple[str, str]]

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# $NAME or ${NAME}; nothing else in a value is shell syntax.
_REFERENCE = re.compile(r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})")
MOST_VALUE = 32_768
# Variables whose value is a list, one item per line in the window.
LISTS = frozenset(
    {
        "PATH",
        "LD_LIBRARY_PATH",
        "MANPATH",
        "INFOPATH",
        "PKG_CONFIG_PATH",
        "PYTHONPATH",
        "XDG_DATA_DIRS",
        "XDG_CONFIG_DIRS",
        "CLASSPATH",
        "CDPATH",
    }
)


def is_name(text: str) -> bool:
    return _NAME.fullmatch(text) is not None


def is_value(text: str) -> bool:
    return len(text) <= MOST_VALUE and not any(c in text for c in "\0\n\r")


def is_list(name: str, value: str = "") -> bool:
    """Whether a variable's value is a list of folders: one of the known ones, or one
    that holds a ":" between paths.
    """
    return name in LISTS or (":" in value and value.count("/") >= 2)


def split_list(value: str) -> list[str]:
    return value.split(":") if value else []


def join_list(items: Iterable[str]) -> str:
    return ":".join(item for item in items if item)


def expand(value: str, environment: Mapping[str, str]) -> str:
    """`value` with $NAME and ${NAME} replaced from `environment`, an unknown one by
    nothing, as a shell does.
    """
    return _REFERENCE.sub(lambda m: environment.get(m[1] or m[2], ""), value)


def shell_quoted(value: str) -> str:
    """`value` in double quotes for sh: its references kept, everything else literal."""
    out = []
    index = 0
    while index < len(value):
        found = _REFERENCE.match(value, index)
        if found:
            out.append(found[0])
            index = found.end()
            continue
        character = value[index]
        out.append("\\" + character if character in '"\\`$' else character)
        index += 1
    return '"' + "".join(out) + '"'


def applied(
    system: Variables,
    user: Variables,
    profile: Variables,
    base: Mapping[str, str],
) -> dict[str, str]:
    """What applies once the session has started: `base` (what the computer sets by
    itself, such as HOME), the system's variables as they are, then the user's and the
    profile's, each expanded with what came before it.
    """
    environment = dict(base)
    environment.update(system)
    for name, value in (*user, *profile):
        environment[name] = expand(value, environment)
    return environment


def origins(system: Variables, user: Variables, profile: Variables) -> dict[str, str]:
    """Where each variable's applied value comes from: system, user or profile."""
    found: dict[str, str] = {}
    for origin, variables in (("system", system), ("user", user), ("profile", profile)):
        for name, _value in variables:
            found[name] = origin
    return found


# Debian's own, when /etc/login.defs does not say.
DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"


def login_path(login_defs: str) -> str:
    """The search path a login starts with, from /etc/login.defs's ENV_PATH line, as
    Debian's login sets it.
    """
    for line in login_defs.splitlines():
        words = line.split()
        if len(words) == 2 and words[0] == "ENV_PATH":
            return words[1].removeprefix("PATH=")
    return DEFAULT_PATH
