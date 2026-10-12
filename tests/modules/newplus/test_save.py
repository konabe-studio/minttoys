from dataclasses import replace
from pathlib import Path

import pytest

from minttoys.modules.base import Context
from minttoys.modules.newplus.module import NewPlus
from minttoys.modules.newplus.options import Options
from minttoys.newplus.main import config_home, save


def here(tmp_path: Path) -> NewPlus:
    return NewPlus(
        lambda action: replace(action, folder=lambda: tmp_path / "actions", package_root=tmp_path)
    )


def test_the_action_is_offered_on_files(tmp_path: Path) -> None:
    module = here(tmp_path)
    module.enable(Context(None, {}))
    text = module.action.path.read_text(encoding="utf-8")
    assert "Name=Save as template\n" in text
    assert "Extensions=nodirs;\n" in text
    module.disable()
    assert module.action.path.exists()
    module.switched_off()
    assert not module.action.path.exists()


def test_new_from_template_is_offered_on_folders_and_the_background(tmp_path: Path) -> None:
    module = here(tmp_path)
    module.enable(Context(None, NewPlus.read_settings({})))
    path = module.create_action(Options()).path
    text = path.read_text(encoding="utf-8")
    assert "Name=New from template…\n" in text
    assert "Selection=any\n" in text
    assert "Extensions=dir;\n" in text
    assert "-m minttoys.newitem %P %F\n" in text
    module.switched_off()
    assert not path.exists()


def test_its_settings_reach_the_window_through_the_action(tmp_path: Path) -> None:
    module = here(tmp_path)
    module.enable(Context(None, NewPlus.read_settings({})))
    settings = NewPlus.check_settings(
        NewPlus.read_settings({}), {"replace_variables": True, "hide_digits": True}
    )
    module.apply_settings(settings)
    text = module.create_action(Options()).path.read_text(encoding="utf-8")
    assert "-m minttoys.newitem --variables --hide-digits %P %F\n" in text


def test_its_settings_are_checked() -> None:
    assert NewPlus.read_settings({"hide_digits": "yes"}) == {
        "replace_variables": False,
        "hide_digits": False,
    }
    with pytest.raises(ValueError, match="true or false"):
        NewPlus.check_settings(NewPlus.read_settings({}), {"hide_digits": 1})
    with pytest.raises(ValueError, match="unknown setting"):
        NewPlus.check_settings(NewPlus.read_settings({}), {"colour": True})


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
