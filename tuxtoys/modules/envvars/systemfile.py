"""/etc/environment as Environment Variables sees it: variables among other lines. Free of
GTK and of the file system.

pam_env reads it at every login, the desktop, a console and SSH alike: "NAME=value" a
line, an optional "export " in front, the value optionally in double or single quotes,
which it takes off, and no references to other variables. Lines that are not a variable,
comments among them, are kept as they are, and so is every line that is not changed,
as Hosts File Editor does with /etc/hosts.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from tuxtoys.modules.envvars.variables import is_name

_LINE = re.compile(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)")


def unquoted(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


@dataclass(frozen=True)
class Line:
    text: str
    name: str = ""  # empty for a line that is not a variable
    value: str = ""


def parse_line(text: str) -> Line:
    if text.lstrip().startswith("#"):
        return Line(text)
    found = _LINE.fullmatch(text)
    if not found:
        return Line(text)
    return Line(text, found[1], unquoted(found[2]))


def line(name: str, value: str) -> str:
    """A variable as a line of its own, in double quotes unless its value has one."""
    if not is_name(name):
        raise ValueError(f"not a variable name: {name!r}")
    if '"' in value and "'" in value:
        raise ValueError("a value in /etc/environment cannot hold both kinds of quotes")
    return f"{name}='{value}'" if '"' in value else f'{name}="{value}"'


class SystemFile:
    """The lines of /etc/environment, edited in place."""

    def __init__(self, text: str) -> None:
        self.ends_with_newline = text.endswith("\n") or not text
        self.lines = [parse_line(text) for text in text.splitlines()]

    def text(self) -> str:
        joined = "\n".join(line.text for line in self.lines)
        return joined + "\n" if self.lines and self.ends_with_newline else joined

    def variables(self) -> Iterator[tuple[int, str, str]]:
        """Each variable with the number of its line. pam_env takes the last of a name."""
        for index, entry in enumerate(self.lines):
            if entry.name:
                yield index, entry.name, entry.value

    def set(self, index: int, name: str, value: str) -> None:
        if not self.lines[index].name:
            raise ValueError(f"line {index} is not a variable")
        self.lines[index] = Line(line(name, value), name, value)

    def add(self, name: str, value: str) -> int:
        """Puts a new variable at the end; the number of its line."""
        self.lines.append(Line(line(name, value), name, value))
        return len(self.lines) - 1

    def remove(self, index: int) -> None:
        if not self.lines[index].name:
            raise ValueError(f"line {index} is not a variable")
        del self.lines[index]
