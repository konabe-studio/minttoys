import shlex
from pathlib import Path

from tuxtoys.core import nemo_action
from tuxtoys.core.nemo_action import NemoAction


def test_actions_dir_follows_xdg_data_home(tmp_path: Path) -> None:
    folder = nemo_action.actions_dir({"XDG_DATA_HOME": str(tmp_path)})
    assert folder == tmp_path / "nemo" / "actions"


def test_actions_dir_ignores_a_relative_data_home() -> None:
    folder = nemo_action.actions_dir({"XDG_DATA_HOME": "relative"})
    assert folder == Path.home() / ".local" / "share" / "nemo" / "actions"


def test_render() -> None:
    text = nemo_action.render(
        {"": "What is using this?", "hu": "Mi használja ezt?"},
        {"": "Shows the processes.", "hu": "Megmutatja a folyamatokat."},
        "/usr/libexec/tuxtoys/tuxtoys-locksmith %F",
        "/usr/libexec/tuxtoys/tuxtoys-locksmith",
        "changes-prevent-symbolic",
    )
    assert text.splitlines() == [
        "[Nemo Action]",
        "Name=What is using this?",
        "Name[hu]=Mi használja ezt?",
        "Comment=Shows the processes.",
        "Comment[hu]=Megmutatja a folyamatokat.",
        "Exec=/usr/libexec/tuxtoys/tuxtoys-locksmith %F",
        "Icon-Name=changes-prevent-symbolic",
        "Selection=notnone",
        "Extensions=any;",
        "Quote=double",
        "Dependencies=/usr/libexec/tuxtoys/tuxtoys-locksmith;",
    ]


def test_a_checkout_runs_its_own_module(tmp_path: Path) -> None:
    command, dependency = nemo_action.program(tmp_path, "tuxtoys-thing", "tuxtoys.thing")
    assert command.endswith(" -m tuxtoys.thing %F")
    assert f"PYTHONPATH={shlex.quote(str(tmp_path))} " in command
    assert dependency == str(tmp_path / "tuxtoys" / "thing" / "__main__.py")


def action(tmp_path: Path) -> NemoAction:
    return NemoAction(
        "test.nemo_action",
        "Do it",
        "Does it.",
        "tuxtoys-thing",
        "tuxtoys.thing",
        "document-new-symbolic",
        extensions="nodirs;",
        folder=lambda: tmp_path / "actions",
        package_root=tmp_path,
    )


def test_write_puts_it_in_place_in_one_step(tmp_path: Path) -> None:
    item = action(tmp_path)
    item.write()
    text = item.path.read_text(encoding="utf-8")
    assert text.startswith("[Nemo Action]\nName=Do it\n")
    assert "Extensions=nodirs;\n" in text
    assert list((tmp_path / "actions").iterdir()) == [item.path]  # no temporary left


def test_remove_twice_does_no_harm(tmp_path: Path) -> None:
    item = action(tmp_path)
    item.write()
    item.remove()
    item.remove()
    assert not item.path.exists()
