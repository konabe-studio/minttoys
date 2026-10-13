"""/etc/hosts as Hosts File Editor sees it: entries among other lines. Free of GTK and of
the file system.

A line is an entry when its first word is an IP address and one or more host names
follow, with an optional "# comment" after them. An entry commented out with "#" is an
inactive one, as PowerToys has it, but only when it reads as an entry through and
through, so a comment in prose stays a comment. Every other line, blank or not, is kept
as it is.

Editing changes only the lines it touches: the rest of the file stays byte for byte, in
its place, unlike PowerToys, which writes the file anew. A new entry goes after the
comments the file starts with, at the top of the entries, since the first match for a
name is the one that counts.
"""

import ipaddress
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace

# A host name as the resolver takes one: labels of letters, digits, "-" and "_", with
# dots between them and an optional one at the end.
_LABEL = r"[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?"
_HOST = re.compile(rf"{_LABEL}(?:\.{_LABEL})*\.?")
MOST_HOST = 253


def is_address(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def is_host(text: str) -> bool:
    return len(text) <= MOST_HOST and _HOST.fullmatch(text) is not None


@dataclass(frozen=True)
class Entry:
    address: str
    hosts: tuple[str, ...]
    comment: str = ""
    active: bool = True

    @property
    def valid_address(self) -> bool:
        return is_address(self.address)

    @property
    def valid_hosts(self) -> bool:
        return bool(self.hosts) and all(is_host(host) for host in self.hosts)

    @property
    def valid(self) -> bool:
        return self.valid_address and self.valid_hosts

    def line(self) -> str:
        """The entry as a line of its own."""
        text = f"{self.address}\t{' '.join(self.hosts)}"
        if self.comment:
            text += f"\t# {self.comment}"
        return text if self.active else f"# {text}"


@dataclass(frozen=True)
class Line:
    text: str  # as it is in the file, without its line end
    entry: Entry | None = None


def parse_line(text: str) -> Line:
    body = text.strip()
    active = not body.startswith("#")
    if not active:
        body = body.lstrip("#").strip()
    data, hash_mark, comment = body.partition("#")
    words = data.split()
    if len(words) < 2 or not is_address(words[0]):
        return Line(text)
    entry = Entry(words[0], tuple(words[1:]), comment.strip() if hash_mark else "", active)
    if not active and not entry.valid_hosts:
        return Line(text)  # a comment that starts with an address, not an entry
    return Line(text, entry)


class HostsFile:
    """The lines of a hosts file, edited in place."""

    def __init__(self, text: str) -> None:
        self.ends_with_newline = text.endswith("\n") or not text
        self.lines = [parse_line(line) for line in text.splitlines()]

    def text(self) -> str:
        joined = "\n".join(line.text for line in self.lines)
        return joined + "\n" if self.lines and self.ends_with_newline else joined

    def entries(self) -> Iterator[tuple[int, Entry]]:
        """Each entry with the number of its line."""
        for index, line in enumerate(self.lines):
            if line.entry is not None:
                yield index, line.entry

    def set(self, index: int, entry: Entry) -> None:
        """Changes the entry on line `index`. Switching it on or off alone keeps the rest
        of the line as it was written.
        """
        old = self.lines[index].entry
        if old is None:
            raise ValueError(f"line {index} is not an entry")
        if replace(old, active=entry.active) == entry and old.active != entry.active:
            text = self.lines[index].text
            if entry.active:
                stripped = text.lstrip()
                new = stripped.lstrip("#").lstrip()
            else:
                new = f"# {text.lstrip()}"
            self.lines[index] = Line(new, entry)
            return
        self.lines[index] = Line(entry.line(), entry)

    def add(self, entry: Entry) -> int:
        """Puts a new entry after the comments and blank lines the file starts with; the
        number of its line.
        """
        index = 0
        while index < len(self.lines) and self.lines[index].entry is None:
            index += 1
        if index == len(self.lines):
            index = _end_of_header(self.lines)
        self.lines.insert(index, Line(entry.line(), entry))
        return index

    def remove(self, index: int) -> None:
        if self.lines[index].entry is None:
            raise ValueError(f"line {index} is not an entry")
        del self.lines[index]

    def move(self, index: int, up: bool) -> int:
        """Swaps an entry with the one above or below it, past other lines; the number of
        its line afterwards, the same when there is none to swap with.
        """
        numbers = [number for number, _entry in self.entries()]
        place = numbers.index(index)
        other = place - 1 if up else place + 1
        if not 0 <= other < len(numbers):
            return index
        target = numbers[other]
        self.lines[index], self.lines[target] = self.lines[target], self.lines[index]
        return target


def _end_of_header(lines: list[Line]) -> int:
    """With no entry at all: after the comments and blank lines at the top."""
    index = 0
    while index < len(lines) and (
        not lines[index].text.strip() or lines[index].text.lstrip().startswith("#")
    ):
        index += 1
    return index


def duplicates(hosts: HostsFile, loopback: bool = False) -> set[int]:
    """The lines of active entries that share a host name with another active entry of
    the same kind of address, IPv4 or IPv6. Loopback addresses (127.0.0.1, ::1) count
    only with `loopback`, as PowerToys' setting of that name has it.
    """
    seen: dict[tuple[int, str], set[int]] = {}
    for index, entry in hosts.entries():
        if not entry.active or not entry.valid_address:
            continue
        address = ipaddress.ip_address(entry.address)
        if address.is_loopback and not loopback:
            continue
        for host in entry.hosts:
            seen.setdefault((address.version, host.casefold().rstrip(".")), set()).add(index)
    return {index for lines in seen.values() if len(lines) > 1 for index in lines}
