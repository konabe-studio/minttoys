from dataclasses import replace
from pathlib import Path

from minttoys.modules.base import Context
from minttoys.modules.newplus.module import NewPlus, menu_item
from minttoys.newplus.main import config_home, save


def test_the_action_is_offered_on_files(tmp_path: Path) -> None:
    action = replace(menu_item(), folder=lambda: tmp_path / "actions", package_root=tmp_path)
    module = NewPlus(action)
    module.enable(Context(None, {}))
    text = action.path.read_text(encoding="utf-8")
    assert "Name=Save as template\n" in text
    assert "Extensions=nodirs;\n" in text
    module.disable()
    assert action.path.exists()
    module.switched_off()
    assert not action.path.exists()


def test_off_by_default() -> None:
    assert NewPlus.enabled_by_default is False


class Told:
    def __init__(self) -> None:
        self.notices: list[tuple[str, str]] = []

    def __call__(self, summary: str, body: str) -> None:
        self.notices.append((summary, body))


def test_save_one_file(tmp_path: Path) -> None:
    source = tmp_path / "Invoice.ods"
    source.write_text("", encoding="utf-8")
    told = Told()
    assert save([str(source)], tmp_path / "Templates", told) == 0
    assert (tmp_path / "Templates" / "Invoice.ods").exists()
    assert told.notices == [
        ("Saved as template", "Invoice.ods is offered under Create New Document now.")
    ]


def test_save_several_files(tmp_path: Path) -> None:
    sources = []
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
        sources.append(str(tmp_path / name))
    told = Told()
    save(sources, tmp_path / "Templates", told)
    assert told.notices == [
        ("Saved as template", "2 files are offered under Create New Document now.")
    ]


def test_without_a_templates_folder_it_says_where_to_set_one(tmp_path: Path) -> None:
    told = Told()
    assert save([str(tmp_path / "a.txt")], None, told) == 1
    assert told.notices[0][0] == "No templates folder"


def test_a_file_that_cannot_be_copied_is_named(tmp_path: Path) -> None:
    told = Told()
    assert save([str(tmp_path / "gone.txt")], tmp_path / "Templates", told) == 1
    assert told.notices == [("Could not save as template", "gone.txt")]


def test_config_home(tmp_path: Path) -> None:
    assert config_home({"XDG_CONFIG_HOME": str(tmp_path)}) == tmp_path
    assert config_home({"XDG_CONFIG_HOME": "relative"}) == Path.home() / ".config"
