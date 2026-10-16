"""The sheets turned into what the window shows: sections of rows, each row with its label
in the user's language and its keys as keycaps, for the keys the user has now. Shortcuts
with no keys are left out. Also the search, the pins, the TuxToys sheet built from our
tools' shortcuts, and the user's own shortcuts.

Free of GTK: the settings are read through a lookup the caller hands in.
"""

import gettext
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Protocol

from tuxtoys.core.i18n import N_, SYSTEM_LOCALE, translation
from tuxtoys.modules.shortcutguide import apps, cinnamon
from tuxtoys.modules.shortcutguide.keys import caps
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Setting, Sheet, Text


@dataclass(frozen=True)
class Row:
    # "sheet/item", what a pin refers to.
    id: str
    label: str
    note: str
    # One set of keycaps per shortcut: Firefox's Reload is F5 and also Ctrl+R.
    keys: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Section:
    title: str
    rows: tuple[Row, ...]


# A setting's keys: its list, or its one string, or None when the setting is not there.
Lookup = Callable[[Setting], Sequence[str] | str | None]
Translate = Callable[[Text], str]

# A mnemonic as East Asian translations write it, "New Window(_N)".
_BRACKETED = re.compile(r"\s*\(_.\)")


def plain(label: str) -> str:
    """A menu label without its mnemonic underscores and its trailing dots: "_Rename..."
    is "Rename", "Save _As…" is "Save As".
    """
    label = _BRACKETED.sub("", label)
    label = label.replace("__", "\0").replace("_", "").replace("\0", "_")
    return label.strip().removesuffix("...").removesuffix("…").strip()


@cache
def _catalogue(domain: str) -> gettext.NullTranslations:
    if not domain:
        return translation()
    return gettext.translation(domain, SYSTEM_LOCALE, fallback=True)


def translate(text: Text) -> str:
    """A label in the user's language, from its own domain; English without a catalogue."""
    return plain(_catalogue(text.domain).gettext(text.msgid))


def keys_of(item: Item, lookup: Lookup) -> list[str]:
    """The item's keys as they are now, without empty or disabled ones."""
    if item.setting is None:
        found: Iterable[str] = item.keys
    else:
        value = lookup(item.setting)
        found = [] if value is None else [value] if isinstance(value, str) else value
    return [keys for keys in found if keys and keys != "disabled"]


def _row(row_id: str, label: str, note: str, shortcuts: Iterable[str]) -> Row | None:
    keys = tuple(tuple(cap) for cap in map(caps, shortcuts) if cap)
    return Row(row_id, label, note, keys) if keys else None


def read_groups(
    sheet_id: str, groups: Iterable[Group], lookup: Lookup, translate: Translate = translate
) -> list[Section]:
    sections = []
    for group in groups:
        rows = []
        for item in group.items:
            note = translate(item.note) if item.note else ""
            row = _row(f"{sheet_id}/{item.id}", translate(item.label), note, keys_of(item, lookup))
            if row is not None:
                rows.append(row)
        if rows:
            sections.append(Section(translate(group.title), tuple(rows)))
    return sections


def read(sheet: Sheet, lookup: Lookup, translate: Translate = translate) -> list[Section]:
    return read_groups(sheet.id, sheet.groups, lookup, translate)


class Custom(Protocol):
    """One of Cinnamon's custom shortcuts, as core.keybindings reads them."""

    name: str
    command: str
    binding: list[str]


# Our tools' commands, by the command a custom shortcut runs: the tool's name, and what the
# shortcut does in it.
TOOL_COMMANDS = {
    "tuxtoys awake toggle": ("Awake", N_("Turn on or off")),
    "tuxtoys lightswitch toggle": ("Light Switch", N_("Switch between light and dark")),
    "tuxtoys alwaysontop opacity up": ("Always on Top", N_("Increase opacity")),
    "tuxtoys alwaysontop opacity down": ("Always on Top", N_("Decrease opacity")),
    "tuxtoys colorpicker": ("Color Picker", N_("Pick a color")),
    "tuxtoys screenruler": ("Screen Ruler", N_("Start measuring")),
    "tuxtoys textextractor": ("Text Extractor", N_("Start extracting text")),
    "tuxtoys shortcutguide": ("Shortcut Guide", N_("Open Shortcut Guide")),
}
TUXTOYS_PREFIX = "TuxToys: "


def ours(custom: Custom) -> bool:
    return custom.command == "tuxtoys" or custom.command.startswith("tuxtoys ")


def tuxtoys_sections(
    customs: Iterable[Custom], above: Sequence[str], translate: Translate = translate
) -> list[Section]:
    """The TuxToys sheet: Muffin's always-on-top keys, which Always on Top sets, and every
    custom shortcut that runs a `tuxtoys` command, by the tool it belongs to.
    """
    rows = []
    pin = _row(
        "tuxtoys/toggle-above", "Always on Top", translate(Text(N_("Pin the window"))), above
    )
    if pin is not None:
        rows.append(pin)
    for custom in customs:
        if not ours(custom):
            continue
        tool, note = TOOL_COMMANDS.get(custom.command, ("", ""))
        label = tool or custom.name.removeprefix(TUXTOYS_PREFIX)
        row = _row(
            f"tuxtoys/{custom.command}",
            label,
            translate(Text(note)) if note else "",
            custom.binding,
        )
        if row is not None:
            rows.append(row)
    # TRANSLATORS: the heading of Shortcut Guide's TuxToys list, PowerToys' "General".
    return [Section(translate(Text(N_("General"))), tuple(rows))] if rows else []


def cinnamon_sections(
    lookup: Lookup, customs: Iterable[Custom], translate: Translate = translate
) -> list[Section]:
    """The Cinnamon sheet: its own shortcuts, the ones most applications share, and the
    user's own custom shortcuts, those that run a TuxToys command left to the TuxToys sheet.
    """
    sections = read_groups(
        cinnamon.SHEET.id, (*cinnamon.SHEET.groups, apps.COMMON), lookup, translate
    )
    rows = []
    for custom in customs:
        if ours(custom):
            continue
        row = _row(f"cinnamon/custom:{custom.name}", custom.name, custom.command, custom.binding)
        if row is not None:
            rows.append(row)
    if rows:
        sections.append(Section(translate(cinnamon.CUSTOM_TITLE), tuple(rows)))
    return sections


def matches(row: Row, query: str) -> bool:
    """Whether every word of the query is in the row's label, note or keys."""
    text = " ".join([row.label, row.note, *(" ".join(cap) for cap in row.keys)]).casefold()
    return all(word in text for word in query.casefold().split())


def search(sections: Iterable[Section], query: str) -> list[Section]:
    found = []
    for section in sections:
        rows = tuple(row for row in section.rows if matches(row, query))
        if rows:
            found.append(Section(section.title, rows))
    return found


def pinned(sections: Iterable[Section], pins: Sequence[str]) -> list[Row]:
    """The pinned rows among these, in the order they were pinned."""
    by_id = {row.id: row for section in sections for row in section.rows}
    return [by_id[pin] for pin in pins if pin in by_id]


def toggle_pin(pins: Sequence[str], row_id: str) -> tuple[str, ...]:
    """The pins with this row pinned, or no longer pinned if it was."""
    if row_id in pins:
        return tuple(pin for pin in pins if pin != row_id)
    return (*pins, row_id)
