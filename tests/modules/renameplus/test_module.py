from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.renameplus.module import RenamePlus


class FakeNemo:
    def __init__(self, command: str = "bulky") -> None:
        self.command = command

    def get(self) -> str:
        return self.command

    def set(self, command: str) -> None:
        self.command = command


class Daemon:
    """Saves settings and hands them back, as the daemon's set_settings does."""

    def __init__(self, module: RenamePlus, settings: Mapping[str, Any]) -> None:
        self.module = module
        self.settings = RenamePlus.read_settings(settings)

    def context(self) -> Context:
        return Context(None, self.settings, self.set_settings)

    def set_settings(self, changes: Mapping[str, Any]) -> None:
        self.settings = RenamePlus.check_settings(self.settings, changes)
        self.module.apply_settings(self.settings)


def here(tmp_path: Path, nemo: FakeNemo) -> RenamePlus:
    return RenamePlus(
        lambda action: replace(action, folder=lambda: tmp_path / "actions", package_root=tmp_path),
        tool=lambda: nemo,
    )


def test_the_action_is_offered_on_anything(tmp_path: Path) -> None:
    nemo = FakeNemo()
    module = here(tmp_path, nemo)
    module.enable(Context(None, RenamePlus.read_settings({})))
    text = module.action.path.read_text(encoding="utf-8")
    assert "Name=Rename with Rename+\n" in text
    assert "Selection=notnone\n" in text
    assert "Extensions=any;\n" in text
    assert "-m tuxtoys.renameplus %F\n" in text
    assert nemo.command == "bulky"  # Nemo's Rename is left alone by default
    module.disable()
    assert module.action.path.exists()
    module.switched_off()
    assert not module.action.path.exists()
    assert nemo.command == "bulky"


def test_nemo_rename_is_taken_over_and_given_back(tmp_path: Path) -> None:
    nemo = FakeNemo()
    module = here(tmp_path, nemo)
    daemon = Daemon(module, {})
    module.enable(daemon.context())
    daemon.set_settings({"nemo_rename": True})
    assert nemo.command == module.command
    assert nemo.command.endswith("-m tuxtoys.renameplus")
    assert daemon.settings["previous_tool"] == "bulky"
    # The end of a session leaves it; the next start keeps it, remembering bulky.
    module.disable()
    assert nemo.command == module.command
    module.enable(daemon.context())
    assert daemon.settings["previous_tool"] == "bulky"
    daemon.set_settings({"nemo_rename": False})
    assert nemo.command == "bulky"


def test_switching_off_gives_it_back(tmp_path: Path) -> None:
    nemo = FakeNemo("")
    module = here(tmp_path, nemo)
    daemon = Daemon(module, {"nemo_rename": True, "previous_tool": "old"})
    module.enable(daemon.context())
    assert nemo.command == module.command
    assert daemon.settings["previous_tool"] == ""
    module.switched_off()
    assert nemo.command == ""


def test_an_older_command_of_its_own_is_not_remembered(tmp_path: Path) -> None:
    nemo = FakeNemo("env PYTHONPATH=/old python3 -m tuxtoys.renameplus")
    module = here(tmp_path, nemo)
    daemon = Daemon(module, {"nemo_rename": True, "previous_tool": "bulky"})
    module.enable(daemon.context())
    assert nemo.command == module.command
    assert daemon.settings["previous_tool"] == "bulky"


def test_what_the_user_set_since_is_left_alone(tmp_path: Path) -> None:
    nemo = FakeNemo()
    module = here(tmp_path, nemo)
    daemon = Daemon(module, {"nemo_rename": True})
    module.enable(daemon.context())
    nemo.set("thunar --bulk-rename")
    module.switched_off()
    assert nemo.command == "thunar --bulk-rename"


def test_without_nemo_the_action_still_works(tmp_path: Path) -> None:
    def missing() -> FakeNemo:
        raise RuntimeError("needs Cinnamon: no org.nemo.preferences settings")

    module = RenamePlus(
        lambda action: replace(action, folder=lambda: tmp_path / "actions", package_root=tmp_path),
        tool=missing,
    )
    module.enable(Context(None, RenamePlus.read_settings({"nemo_rename": True})))
    assert module.action.path.exists()
    module.switched_off()


def test_off_by_default() -> None:
    assert RenamePlus.enabled_by_default is False


def test_settings_are_checked() -> None:
    settings = RenamePlus.read_settings({})
    assert settings["apply_to"] == "both"
    assert settings["recent_search"] == []
    with pytest.raises(ValueError, match="text_case is one of"):
        RenamePlus.check_settings(settings, {"text_case": "loud"})
