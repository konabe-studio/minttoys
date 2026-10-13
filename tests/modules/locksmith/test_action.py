from dataclasses import replace
from pathlib import Path

from tuxtoys.modules.base import Context
from tuxtoys.modules.locksmith.module import FileLocksmith, menu_item


def module(tmp_path: Path) -> FileLocksmith:
    action = replace(menu_item(), folder=lambda: tmp_path / "actions", package_root=tmp_path)
    return FileLocksmith(action)


def test_on_writes_the_action(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    text = locksmith.action.path.read_text(encoding="utf-8")
    assert text.startswith("[Nemo Action]\nName=What is using this?\n")
    assert "Icon-Name=changes-prevent-symbolic\n" in text


def test_the_end_of_a_session_keeps_it(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    locksmith.disable()
    assert locksmith.action.path.exists()


def test_switching_off_takes_it_away(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    locksmith.switched_off()
    assert not locksmith.action.path.exists()


def test_off_by_default() -> None:
    assert FileLocksmith.enabled_by_default is False
