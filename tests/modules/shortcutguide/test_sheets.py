"""The shipped lists themselves: what a typo in them would break."""

import pytest

from tuxtoys.core import accel
from tuxtoys.modules.shortcutguide import apps, cinnamon
from tuxtoys.modules.shortcutguide.sheets import Sheet

SHEETS = (cinnamon.SHEET, *apps.APPS)


@pytest.mark.parametrize("sheet", SHEETS, ids=lambda sheet: sheet.id)
def test_item_ids_are_unique_in_a_sheet(sheet: Sheet) -> None:
    ids = [item.id for group in sheet.groups for item in group.items]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("sheet", SHEETS, ids=lambda sheet: sheet.id)
def test_every_fixed_key_parses_and_every_item_has_keys_or_a_setting(sheet: Sheet) -> None:
    for group in sheet.groups:
        assert group.items
        for item in group.items:
            assert bool(item.keys) != bool(item.setting), item.id
            for keys in item.keys:
                assert accel.parse(keys) is not None, (item.id, keys)


def test_the_common_group_parses_too() -> None:
    ids = [item.id for item in apps.COMMON.items]
    assert len(ids) == len(set(ids))
    assert all(accel.parse(keys) for item in apps.COMMON.items for keys in item.keys)


def test_cinnamon_s_table_reads_its_own_schemas_in_its_own_domain() -> None:
    schemas = {cinnamon.WM, cinnamon.MEDIA, cinnamon.CINNAMON}
    for group in cinnamon.SHEET.groups:
        assert group.title.domain == "cinnamon"
        for item in group.items:
            assert item.setting is not None
            assert item.setting.schema in schemas
            assert item.setting.key == item.id
            assert item.label.domain == "cinnamon"
    titles = [group.title.msgid for group in cinnamon.SHEET.groups]
    assert titles[:2] == ["General", "Pointer"]
    assert "Tiling and Snapping" in titles


def test_the_terminal_reads_its_keys_from_its_relocatable_schema() -> None:
    for group in apps.TERMINAL.groups:
        for item in group.items:
            assert item.setting is not None
            assert item.setting.schema == apps.TERMINAL_SCHEMA
            assert item.setting.path == apps.TERMINAL_PATH


def test_each_window_class_has_at_most_one_sheet() -> None:
    classes = [wm_class for sheet in apps.APPS for wm_class in sheet.wm_classes]
    assert len(classes) == len(set(classes))
    assert all(wm_class == wm_class.lower() for wm_class in classes)


@pytest.mark.parametrize(
    ("wm_class", "sheet"),
    [("Nemo", "nemo"), ("nemo-desktop", "nemo"), ("Xed", "xed"), ("firefox", "firefox")],
)
def test_a_window_finds_its_sheet_by_class(wm_class: str, sheet: str) -> None:
    found = apps.for_window(wm_class)
    assert found is not None
    assert found.id == sheet


def test_a_window_without_a_list_finds_none() -> None:
    assert apps.for_window("Gimp") is None
