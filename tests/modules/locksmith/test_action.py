import shlex
from pathlib import Path

from minttoys.modules.base import Context
from minttoys.modules.locksmith import action
from minttoys.modules.locksmith.module import FileLocksmith


def test_actions_dir_follows_xdg_data_home(tmp_path: Path) -> None:
    folder = action.actions_dir({"XDG_DATA_HOME": str(tmp_path)})
    assert folder == tmp_path / "nemo" / "actions"


def test_actions_dir_ignores_a_relative_data_home() -> None:
    folder = action.actions_dir({"XDG_DATA_HOME": "relative"})
    assert folder == Path.home() / ".local" / "share" / "nemo" / "actions"


def test_render() -> None:
    text = action.render(
        {"": "What is using this?", "hu": "Mi használja ezt?"},
        {"": "Shows the processes.", "hu": "Megmutatja a folyamatokat."},
        "/usr/libexec/minttoys/minttoys-locksmith %F",
        "/usr/libexec/minttoys/minttoys-locksmith",
    )
    assert text.splitlines() == [
        "[Nemo Action]",
        "Name=What is using this?",
        "Name[hu]=Mi használja ezt?",
        "Comment=Shows the processes.",
        "Comment[hu]=Megmutatja a folyamatokat.",
        "Exec=/usr/libexec/minttoys/minttoys-locksmith %F",
        "Icon-Name=changes-prevent-symbolic",
        "Selection=notnone",
        "Extensions=any;",
        "Quote=double",
        "Dependencies=/usr/libexec/minttoys/minttoys-locksmith;",
    ]


def test_a_checkout_runs_its_own_module(tmp_path: Path) -> None:
    command, dependency = action.program(tmp_path)
    assert command.endswith(" -m minttoys.locksmith %F")
    assert f"PYTHONPATH={shlex.quote(str(tmp_path))} " in command
    assert dependency == str(tmp_path / "minttoys" / "locksmith" / "__main__.py")


def module(tmp_path: Path) -> FileLocksmith:
    return FileLocksmith(folder=lambda: tmp_path / "actions", package_root=tmp_path)


def test_on_writes_the_action(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    text = locksmith.path.read_text(encoding="utf-8")
    assert text.startswith("[Nemo Action]\nName=What is using this?\n")
    assert list((tmp_path / "actions").iterdir()) == [locksmith.path]  # no temporary left


def test_the_end_of_a_session_keeps_it(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    locksmith.disable()
    assert locksmith.path.exists()


def test_switching_off_takes_it_away(tmp_path: Path) -> None:
    locksmith = module(tmp_path)
    locksmith.enable(Context(None, {}))
    locksmith.switched_off()
    assert not locksmith.path.exists()
    locksmith.switched_off()  # a second time does no harm


def test_off_by_default() -> None:
    assert FileLocksmith.enabled_by_default is False
