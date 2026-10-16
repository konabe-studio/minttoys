from dataclasses import dataclass, field

from tuxtoys.modules.shortcutguide import cinnamon, reading
from tuxtoys.modules.shortcutguide.reading import (
    Row,
    Section,
    cinnamon_sections,
    pinned,
    plain,
    read,
    search,
    toggle_pin,
    tuxtoys_sections,
)
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Setting, Sheet, Text


@dataclass
class Custom:
    name: str
    command: str
    binding: list[str] = field(default_factory=list)


def english(text: Text) -> str:
    return plain(text.msgid)


def settings(values: dict[tuple[str, str], list[str] | str]) -> reading.Lookup:
    return lambda setting: values.get((setting.schema, setting.key))


def test_a_menu_label_loses_its_mnemonics_and_dots() -> None:
    assert plain("_Rename...") == "Rename"
    assert plain("Save _As…") == "Save As"
    assert plain("Cu_t") == "Cut"
    assert plain("New Window(_N)") == "New Window"
    assert plain("Show __private") == "Show _private"


def test_a_translation_comes_from_the_label_s_own_domain() -> None:
    # Without Nemo's catalogue, as on this machine, its label stays English.
    assert reading.translate(Text("New _Window", "nemo")) == "New Window"
    assert reading.translate(Text("Pick a color")) == "Pick a color"


SHEET = Sheet(
    "test",
    "Test",
    "icon",
    (
        Group(
            Text("Windows"),
            (
                Item("close", Text("_Close"), ("<Alt>F4",)),
                Item("max", Text("Maximize"), setting=Setting("wm", "toggle-maximized")),
                Item("unset", Text("Unset"), setting=Setting("wm", "unset")),
                Item("gone", Text("Not installed"), setting=Setting("other", "key")),
            ),
        ),
        Group(Text("Empty"), (Item("off", Text("Off"), setting=Setting("wm", "off")),)),
    ),
)


def test_a_sheet_reads_its_keys_and_leaves_out_shortcuts_without_any() -> None:
    lookup = settings(
        {
            ("wm", "toggle-maximized"): ["<Super>Up", "<Alt>F10"],
            ("wm", "unset"): [],
            ("wm", "off"): "disabled",
        }
    )
    assert read(SHEET, lookup, english) == [
        Section(
            "Windows",
            (
                Row("test/close", "Close", "", (("Alt", "F4"),)),
                Row("test/max", "Maximize", "", (("Super", "↑"), ("Alt", "F10"))),
            ),
        )
    ]


def test_a_single_string_setting_is_one_shortcut() -> None:
    lookup = settings({("wm", "toggle-maximized"): "<Primary><Shift>t"})
    rows = read(SHEET, lookup, english)[0].rows
    assert rows[1].keys == (("Ctrl", "Shift", "T"),)


def test_cinnamon_s_sheet_has_its_groups_the_common_ones_and_the_user_s_own() -> None:
    lookup = settings(
        {
            (cinnamon.WM, "show-desktop"): ["<Super>d"],
            (cinnamon.WM, "toggle-above"): ["<Primary><Super>t"],
        }
    )
    customs = [
        Custom("Backup", "deja-dup --backup", ["<Super>b"]),
        Custom("TuxToys: Screen Ruler", "tuxtoys screenruler", ["<Primary><Shift><Super>m"]),
        Custom("Nothing", "true"),
    ]
    sections = cinnamon_sections(lookup, customs, english)
    titles = [section.title for section in sections]
    assert titles == ["General", "Windows", "Most applications", "Custom Shortcuts"]
    assert sections[0].rows == (
        Row("cinnamon/show-desktop", "Show desktop", "", (("Super", "D"),)),
    )
    assert sections[-1].rows == (
        Row("cinnamon/custom:Backup", "Backup", "deja-dup --backup", (("Super", "B"),)),
    )


def test_the_tuxtoys_sheet_lists_our_tools_by_their_commands() -> None:
    customs = [
        Custom("Backup", "deja-dup --backup", ["<Super>b"]),
        Custom("TuxToys: Color Picker", "tuxtoys colorpicker", ["<Shift><Super>c"]),
        Custom("My renamed one", "tuxtoys screenruler", ["<Primary><Shift><Super>m"]),
        Custom("TuxToys: Something new", "tuxtoys something", ["<Super>F2"]),
        Custom("TuxToys: Light Switch", "tuxtoys lightswitch toggle", []),
    ]
    [section] = tuxtoys_sections(customs, ["<Primary><Super>t"], english)
    assert section.title == "General"
    assert [(row.label, row.note) for row in section.rows] == [
        ("Always on Top", "Pin the window"),
        ("Color Picker", "Pick a color"),
        ("Screen Ruler", "Start measuring"),
        ("Something new", ""),
    ]
    assert section.rows[0].id == "tuxtoys/toggle-above"
    assert section.rows[1].id == "tuxtoys/tuxtoys colorpicker"


def test_no_tuxtoys_shortcuts_no_section() -> None:
    assert tuxtoys_sections([Custom("Backup", "deja-dup", ["<Super>b"])], [], english) == []


SECTIONS = [
    Section(
        "Windows",
        (
            Row("c/close", "Close window", "", (("Alt", "F4"),)),
            Row("c/max", "Maximize window", "Twice restores it", (("Super", "↑"),)),
        ),
    ),
    Section("Files", (Row("c/copy", "Copy", "", (("Ctrl", "C"),)),)),
]


def test_search_looks_at_labels_notes_and_keys_and_drops_empty_sections() -> None:
    assert search(SECTIONS, "WINDOW") == [SECTIONS[0]]
    assert search(SECTIONS, "restores") == [Section("Windows", (SECTIONS[0].rows[1],))]
    assert search(SECTIONS, "ctrl c") == [SECTIONS[1]]
    assert search(SECTIONS, "alt maximize") == []
    assert search(SECTIONS, "") == SECTIONS


def test_pins_keep_their_order_and_skip_what_is_not_there() -> None:
    rows = pinned(SECTIONS, ["c/copy", "gone/away", "c/close"])
    assert [row.id for row in rows] == ["c/copy", "c/close"]


def test_a_pin_toggles() -> None:
    assert toggle_pin((), "c/copy") == ("c/copy",)
    assert toggle_pin(("c/close", "c/copy"), "c/close") == ("c/copy",)
