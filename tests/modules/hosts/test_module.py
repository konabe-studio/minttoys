from dataclasses import replace
from pathlib import Path

import pytest

from tuxtoys.core import menu_entry as menu_entry_module
from tuxtoys.core.nemo_action import INSTALLED_ROOT
from tuxtoys.modules.base import Context
from tuxtoys.modules.hosts.module import HostsFileEditor, editor_command, menu_entry


def here(tmp_path: Path) -> HostsFileEditor:
    return HostsFileEditor(
        lambda entry: replace(
            entry, folder=lambda: tmp_path / "applications", package_root=tmp_path
        )
    )


def test_the_menu_entry_is_there_while_it_is_on(tmp_path: Path) -> None:
    module = here(tmp_path)
    module.enable(Context(None, HostsFileEditor.read_settings({})))
    text = module.entry.path.read_text(encoding="utf-8")
    assert module.entry.path.name == "io.github.konabe_studio.TuxToys.HostsEditor.desktop"
    assert "Name=Hosts File Editor\n" in text
    assert "-m tuxtoys.hostseditor\n" in text
    assert "TryExec=" not in text  # a checkout's __main__.py is not a program
    assert "Icon=io.github.konabe_studio.TuxToys\n" in text
    assert "OnlyShowIn=X-Cinnamon;\n" in text
    module.disable()
    assert module.entry.path.exists()
    module.switched_off()
    assert not module.entry.path.exists()


def test_installed_it_hides_without_its_program(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = "/usr/libexec/tuxtoys/tuxtoys-hosts-editor"
    monkeypatch.setattr(menu_entry_module, "program", lambda *_args: (f"{launcher} ", launcher))
    text = replace(menu_entry(), package_root=INSTALLED_ROOT).text()
    assert "TryExec=/usr/libexec/tuxtoys/tuxtoys-hosts-editor\n" in text


def test_editor_command(tmp_path: Path) -> None:
    argv = editor_command(tmp_path)
    assert argv[0] == "env"
    assert argv[1] == f"PYTHONPATH={tmp_path}"
    assert argv[-2:] == ["-m", "tuxtoys.hostseditor"]


def test_off_by_default() -> None:
    assert HostsFileEditor.enabled_by_default is False


def test_settings_are_checked() -> None:
    settings = HostsFileEditor.read_settings({})
    assert settings["keep"] == "age"
    with pytest.raises(ValueError, match="keep is never"):
        HostsFileEditor.check_settings(settings, {"keep": "forever"})
