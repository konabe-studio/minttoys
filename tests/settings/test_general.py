"""The General page's parts that need no GTK: the panel icon's autostart, and the backup
of the settings.
"""

import json
from pathlib import Path

import pytest

from tuxtoys.api import ModuleInfo
from tuxtoys.settings import backup, startup


def test_the_panel_icon_switched_off_and_on(tmp_path: Path) -> None:
    system = tmp_path / "system.desktop"
    system.write_text("[Desktop Entry]\nName=TuxToys panel icon\nX-GNOME-Autostart-enabled=true\n")
    folder = tmp_path / "autostart"
    assert startup.starts(folder)
    startup.set_starts(folder, False, system)
    text = (folder / startup.ENTRY).read_text()
    assert text.startswith(startup.MARK)
    assert text.count("X-GNOME-Autostart-enabled") == 1
    assert "X-GNOME-Autostart-enabled=false" in text
    assert not startup.starts(folder)
    startup.set_starts(folder, True, system)
    assert not (folder / startup.ENTRY).exists()
    assert startup.starts(folder)


def test_a_copy_startup_applications_wrote_is_kept(tmp_path: Path) -> None:
    folder = tmp_path / "autostart"
    folder.mkdir()
    (folder / startup.ENTRY).write_text(
        "[Desktop Entry]\nName=Mine\nX-GNOME-Autostart-enabled=false\nX-Custom=1\n"
    )
    assert not startup.starts(folder)
    startup.set_starts(folder, True)
    text = (folder / startup.ENTRY).read_text()
    assert "X-GNOME-Autostart-enabled=true" in text
    assert "X-Custom=1" in text
    assert startup.starts(folder)
    (folder / startup.ENTRY).write_text("[Desktop Entry]\nHidden=true\n")
    assert not startup.starts(folder)


def test_without_the_package_it_still_writes_an_entry(tmp_path: Path) -> None:
    folder = tmp_path / "autostart"
    startup.set_starts(folder, False, tmp_path / "missing.desktop")
    assert not startup.starts(folder)


INFOS = [
    ModuleInfo("awake", "Awake", "", "on", ""),
    ModuleInfo("locksmith", "File Locksmith", "", "off", ""),
    ModuleInfo("renameplus", "Rename+", "", "on", ""),
]


def test_export_and_read_back() -> None:
    settings = {
        "awake": {"default_minutes": 90, "keep_screen": True},
        "renameplus": {"regex": True, "previous_tool": "bulky"},
    }
    text = backup.export(INFOS, settings)
    document = json.loads(text)
    assert document["format"] == "tuxtoys-settings"
    assert document["tools"]["renameplus"]["settings"] == {"regex": True}
    assert document["tools"]["locksmith"] == {"enabled": False, "settings": {}}
    restores, unknown = backup.read(text)
    assert unknown == []
    assert backup.Restore("awake", True, {"default_minutes": 90, "keep_screen": True}) in restores
    assert backup.Restore("locksmith", False, {}) in restores


def test_reading_leaves_out_what_this_version_does_not_know() -> None:
    text = json.dumps(
        {
            "format": "tuxtoys-settings",
            "version": 1,
            "tools": {
                "awake": {"enabled": "yes", "settings": {"keep_screen": False, "colour": "red"}},
                "fancyzones": {"enabled": True, "settings": {}},
                "renameplus": {"settings": {"previous_tool": "x"}},
            },
        }
    )
    restores, unknown = backup.read(text)
    assert unknown == ["fancyzones"]
    assert restores == [
        backup.Restore("awake", None, {"keep_screen": False}),
        backup.Restore("renameplus", None, {}),
    ]


@pytest.mark.parametrize(
    "text", ["not json", "[]", '{"format": "other"}', '{"format": "tuxtoys-settings"}']
)
def test_not_a_backup(text: str) -> None:
    with pytest.raises(backup.NotABackup):
        backup.read(text)


def test_fit_makes_tuples_where_dbus_wants_them() -> None:
    assert backup.fit("a(ssdds)", [["Web", "fit", 800, 0, "px"]]) == [("Web", "fit", 800, 0, "px")]
    assert backup.fit("(sdds)", ["fit", 1, 2, "px"]) == ("fit", 1, 2, "px")
    assert backup.fit("(sa(su))", ["x", [["a", 1]]]) == ("x", [("a", 1)])
    assert backup.fit("as", ["a", "b"]) == ["a", "b"]
    assert backup.fit("(ss)", ["only one"]) == ["only one"]
    assert backup.fit("s", 5) == 5
