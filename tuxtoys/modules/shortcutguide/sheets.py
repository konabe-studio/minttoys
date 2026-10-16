"""What Shortcut Guide lists, as data: sheets (a tab each in the window), their groups, and
in each group the shortcuts, each with its label and either its keys or the setting that
holds them.

A label is a message in some gettext domain: TuxToys' own, or the program's whose shortcut
it is (Cinnamon's, Nemo's), so that it reads as that program's own menus and settings do in
the user's language. Free of GTK, so it tests anywhere.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Text:
    msgid: str
    # The gettext domain it is translated in; "" for TuxToys' own.
    domain: str = ""


@dataclass(frozen=True)
class Setting:
    """A GSettings key holding a shortcut's keys: a list of them, or one ("disabled" for
    none), as the schema has it.
    """

    schema: str
    key: str
    # For a relocatable schema, where its settings are; "" for a schema that has a path.
    path: str = ""


@dataclass(frozen=True)
class Item:
    # Unique within its sheet, kept across versions: pins refer to it.
    id: str
    label: Text
    # The keys as GSettings writes them, "<Primary>c"; fixed ones, when there is no setting.
    keys: tuple[str, ...] = ()
    setting: Setting | None = None
    # A line under the label saying when the shortcut applies.
    note: Text | None = None


@dataclass(frozen=True)
class Group:
    title: Text
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Sheet:
    id: str
    # The program's name, which is not translated.
    name: str
    # Icons from the theme, the first one it has: a symbolic one first, so the rail
    # matches the theme's colors, then the app's own.
    icons: tuple[str, ...]
    groups: tuple[Group, ...]
    # The windows it is the sheet for, by the class part of WM_CLASS, lower-cased.
    wm_classes: tuple[str, ...] = ()
