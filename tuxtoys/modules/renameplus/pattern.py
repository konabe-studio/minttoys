"""What Rename+ makes of one name, as PowerToys' PowerRename does it. Free of GTK and of
the file system.

- Search for plain text or a regular expression (Python's), in any case or the same case,
  the first match or every one.
- Replace with text that can hold: the date and time variables ($YYYY, $MM, $DD, $hh and
  the others New+ knows), filled from each item's own time; counters, ${} with start=,
  increment= and padding=, counting the items that match; random text,
  ${rstringalnum=9}, ${rstringalpha=9}, ${rstringdigit=9} and ${ruuidv4}; and with a
  regular expression, $1 to $9 for its groups, $0 or $& for the whole match, $$ for "$".
- The search looks at the name, the name without its extension, or the extension alone.
- Then the result can be put in lowercase, uppercase, title case or every word
  capitalized, by PowerRename's own rules.
"""

import re
import string
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from random import Random

from tuxtoys.modules.newplus.names import expand_dates, has_dates, split_extension

APPLY_TO = ("both", "name", "extension")
TEXT_CASES = ("", "lower", "upper", "title", "words")
MOST_RANDOM = 255

# Words title case leaves in lowercase unless first or last, as PowerRename has them.
_SMALL_WORDS = frozenset(
    "a an to the at by for in of on up and as but or nor".split()  # noqa: SIM905
)
_TOKEN = re.compile(r"\$\{(.*?)\}")
_START = re.compile(r"start=(-?\d+)")
_INCREMENT = re.compile(r"increment=(-?\d+)")
_PADDING = re.compile(r"padding=(\d+)")
_RANDOM = re.compile(r"rstring(alnum|alpha|digit)=(\d+)")
_GROUP = re.compile(r"\$(\$|&|\d)")
_ALPHABETS = {
    "alnum": string.ascii_letters + string.digits,
    "alpha": string.ascii_letters,
    "digit": string.digits,
}


class PatternError(ValueError):
    """The search is not a regular expression. The message is Python's, in English."""


@dataclass(frozen=True)
class Rules:
    search: str = ""
    replace: str = ""
    regex: bool = False
    match_all: bool = False
    case_sensitive: bool = False
    apply_to: str = "both"
    text_case: str = ""
    enumerate: bool = True
    randomize: bool = False

    def compile(self) -> re.Pattern[str] | None:
        """The search, or None when there is none. PatternError for a bad expression."""
        if not self.search:
            return None
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            return re.compile(self.search if self.regex else re.escape(self.search), flags)
        except re.error as error:
            raise PatternError(str(error)) from error

    def uses_time(self) -> bool:
        return has_dates(self.replace)


def fill(
    template: str,
    rules: Rules,
    index: int,
    when: datetime | None,
    random: Random,
) -> str:
    """The replace text for the item with counter `index`: its dates, counters and random
    text filled in. Without the box for counters or random text ticked, ${...} stays as
    typed; a ${...} that is both is random text.
    """
    if when is not None:
        template = expand_dates(template, when)

    def token(match: re.Match[str]) -> str:
        inside = match[1]
        if rules.randomize:
            made = _random_text(inside, random)
            if made is not None:
                return made
        if rules.enumerate:
            return _counter(inside, index)
        return match[0]

    return _TOKEN.sub(token, template)


def _counter(inside: str, index: int) -> str:
    start = int(found[1]) if (found := _START.search(inside)) else 0
    increment = int(found[1]) if (found := _INCREMENT.search(inside)) else 1
    padding = min(int(found[1]), MOST_RANDOM) if (found := _PADDING.search(inside)) else 0
    return f"{start + index * increment:0{padding}d}"


def _random_text(inside: str, random: Random) -> str | None:
    if "ruuidv4" in inside:
        return str(uuid.UUID(int=random.getrandbits(128), version=4))
    found = _RANDOM.search(inside)
    if not found:
        return None
    length = min(int(found[2]), MOST_RANDOM)
    alphabet = _ALPHABETS[found[1]]
    return "".join(random.choice(alphabet) for _ in range(length))


def _with_groups(template: str) -> Callable[[re.Match[str]], str]:
    """A regular expression's replacement as PowerRename writes it: $1 to $9, $0 or $&,
    and $$; a group the expression does not have is left as typed.
    """

    def replacement(match: re.Match[str]) -> str:
        def group(found: re.Match[str]) -> str:
            what = found[1]
            if what == "$":
                return "$"
            if what in ("&", "0"):
                return match[0]
            number = int(what)
            if number > (match.re.groups or 0):
                return found[0]
            return match[number] or ""

        return _GROUP.sub(group, template)

    return replacement


def source_part(name: str, is_folder: bool, apply_to: str) -> str:
    """The part of a name the search looks at: a folder's whole name, always."""
    if is_folder or apply_to == "both":
        return name
    stem, extension = split_extension(name)
    return stem if apply_to == "name" else extension.removeprefix(".")


def put_back(name: str, is_folder: bool, apply_to: str, part: str) -> str:
    """The whole name with its searched part changed to `part`. A name with no extension
    keeps it that way when only the extension is searched.
    """
    if is_folder or apply_to == "both":
        return part
    stem, extension = split_extension(name)
    if apply_to == "name":
        return part + extension
    return f"{stem}.{part}" if extension else name


def replaced(part: str, pattern: re.Pattern[str], rules: Rules, filled: str) -> str | None:
    """`part` with the search replaced, or None when it does not match."""
    if not pattern.search(part):
        return None
    replacement = _with_groups(filled) if rules.regex else (lambda _match: filled)
    return pattern.sub(replacement, part, count=0 if rules.match_all else 1)


def change_case(name: str, text_case: str, is_folder: bool, apply_to: str) -> str:
    """The name in the case asked for, by PowerRename's rules: lowercase and uppercase go
    to the part searched, title case and capitalized words to the name without its
    extension, never to the extension alone.
    """
    if not text_case:
        return name
    if text_case in ("lower", "upper"):
        change = str.lower if text_case == "lower" else str.upper
        if is_folder or apply_to == "both":
            return change(name)
        stem, extension = split_extension(name)
        if apply_to == "name":
            return change(stem) + extension
        return stem + change(extension) if extension else change(name)
    if apply_to == "extension" and not is_folder:
        return name
    stem, extension = (name, "") if is_folder else split_extension(name)
    return _words(stem, title=text_case == "title") + extension


def _is_mark(character: str) -> bool:
    return not character.isalnum() and not character.isspace()


def _words(stem: str, title: bool) -> str:
    """Every word with a capital first letter and the rest small; in title case, the
    small words of _SMALL_WORDS stay small unless they are first or last. A letter after
    an apostrophe inside a word ("don't") is not a word of its own.
    """
    end = len(stem)
    while end and (stem[end - 1].isspace() or _is_mark(stem[end - 1])):
        end -= 1
    letters = list(stem)
    first = True
    index = 0
    while index < end:
        before = stem[index - 1] if index else ""
        starts = (
            not index
            or before.isspace()
            or (_is_mark(before) and not _inside_word_quote(stem, index))
        )
        if not starts or stem[index].isspace() or _is_mark(stem[index]):
            if starts:
                index += 1
                continue
            letters[index] = stem[index].lower()
            index += 1
            continue
        length = 0
        while index + length < end and not (
            stem[index + length].isspace() or _is_mark(stem[index + length])
        ):
            length += 1
        word = stem[index : index + length].lower()
        last = index + length == end
        small = title and not first and not last and word in _SMALL_WORDS
        letters[index] = stem[index].lower() if small else stem[index].upper()
        for inner in range(index + 1, index + length):
            letters[inner] = stem[inner].lower()
        first = False
        index += length
    return "".join(letters)


def _inside_word_quote(stem: str, index: int) -> bool:
    """An apostrophe with a letter before it, as in "don't": what follows is not a word."""
    return stem[index - 1] == "'" and index >= 2 and stem[index - 2].isalnum()
