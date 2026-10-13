"""The preview: what each chosen item would be renamed to, and why not when it would not.
Free of GTK; the file system only through the `taken` it is handed.

The items come in the order they are shown, which is the order counters count in. A
renamed name never takes one that is already there: neither another item's new name in
the same folder, nor a name in the folder that is not itself being renamed away.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from random import Random

from tuxtoys.modules.renameplus.pattern import (
    Rules,
    change_case,
    fill,
    put_back,
    replaced,
    source_part,
)

# Linux's own limit for one name, in bytes.
MOST_BYTES = 255


@dataclass(frozen=True)
class Item:
    folder: str  # the folder it is in, as it is now
    name: str
    is_folder: bool
    depth: int = 0  # 0 for an item chosen in Nemo, 1 and on for what is inside one
    when: datetime | None = None  # for the date variables
    selected: bool = True  # its box in the preview


@dataclass(frozen=True)
class Include:
    files: bool = True
    folders: bool = True
    subfolders: bool = True


# What becomes of an item:
UNCHANGED = "unchanged"  # the search does not match, or the name comes out the same
RENAME = "rename"
SKIPPED = "skipped"  # its box is cleared, or the kind of item is left out
INVALID = "invalid"  # empty, ".", "..", or holding "/"
TOO_LONG = "too-long"
CLASH = "clash"  # the new name is taken


@dataclass(frozen=True)
class Outcome:
    status: str
    new_name: str = ""


def plan(
    items: Sequence[Item],
    rules: Rules,
    include: Include,
    taken: Callable[[str, str, str], bool] = lambda folder, name, own: False,
    random: Random | None = None,
) -> list[Outcome]:
    """One outcome per item. `taken(folder, name, own)` tells whether `name` is in use in
    `folder` by something other than the item now called `own`. PatternError for a search
    that is not a regular expression.
    """
    pattern = rules.compile()
    random = random or Random()  # names, not secrets
    uses_time = rules.uses_time()
    outcomes = []
    counter = 0
    for item in items:
        if not _included(item, include, rules):
            outcomes.append(Outcome(SKIPPED))
            continue
        part = source_part(item.name, item.is_folder, rules.apply_to)
        new_part = None
        if pattern is not None and part:
            filled = fill(rules.replace, rules, counter, item.when if uses_time else None, random)
            new_part = replaced(part, pattern, rules, filled)
            if new_part is not None:
                counter += 1
        if new_part is None:
            if not rules.text_case:
                outcomes.append(Outcome(UNCHANGED))
                continue
            new_part = part
        new_name = put_back(item.name, item.is_folder, rules.apply_to, new_part).strip()
        new_name = change_case(new_name, rules.text_case, item.is_folder, rules.apply_to)
        outcomes.append(_judge(item, new_name))
    return _clashes(items, outcomes, taken)


def _included(item: Item, include: Include, rules: Rules) -> bool:
    if not item.selected:
        return False
    if item.is_folder and (not include.folders or rules.apply_to == "extension"):
        return False
    if not item.is_folder and not include.files:
        return False
    return item.depth == 0 or include.subfolders


def _judge(item: Item, new_name: str) -> Outcome:
    if new_name == item.name:
        return Outcome(UNCHANGED)
    if new_name in ("", ".", "..") or "/" in new_name or "\0" in new_name:
        return Outcome(INVALID, new_name)
    if len(new_name.encode("utf-8", "surrogateescape")) > MOST_BYTES:
        return Outcome(TOO_LONG, new_name)
    return Outcome(RENAME, new_name)


def _clashes(
    items: Sequence[Item],
    outcomes: list[Outcome],
    taken: Callable[[str, str, str], bool],
) -> list[Outcome]:
    """Marks a new name as a clash when another item ends up with it in the same folder,
    or when something already there keeps it.
    """
    final: dict[tuple[str, str], list[int]] = {}
    leaving: set[tuple[str, str]] = set()
    staying: set[tuple[str, str]] = set()
    for index, (item, outcome) in enumerate(zip(items, outcomes, strict=True)):
        if outcome.status == RENAME:
            final.setdefault((item.folder, outcome.new_name), []).append(index)
            leaving.add((item.folder, item.name))
        else:
            staying.add((item.folder, item.name))
    result = list(outcomes)
    for (folder, name), indexes in final.items():
        clash = len(indexes) > 1 or (folder, name) in staying
        if not clash and (folder, name) not in leaving:
            own = items[indexes[0]].name
            clash = taken(folder, name, own)
        if clash:
            for index in indexes:
                result[index] = Outcome(CLASH, outcomes[index].new_name)
    return result


def count(outcomes: Sequence[Outcome]) -> int:
    """How many items would be renamed."""
    return sum(outcome.status == RENAME for outcome in outcomes)
