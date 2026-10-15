"""Environment Variables' window with real GTK, an /etc/environment of the test's own,
and stand-ins for the daemon and pkexec. Needs a display: xvfb in CI, the desktop
otherwise.
"""

import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.api import ModuleOff, NotRunning  # noqa: E402
from tuxtoys.envvars.window import EnvironmentWindow, VariableDialog  # noqa: E402
from tuxtoys.modules.envvars.options import Options  # noqa: E402

TEXT = '# set by the system\nPATH="/usr/local/bin:/usr/bin:/bin"\nLANG="hu_HU.UTF-8"\n'
BASE = {"HOME": "/home/b", "PATH": "/usr/bin:/bin"}


class FakeClient:
    def __init__(self, settings: dict | None = None, state: str = "on") -> None:
        self.settings = settings if settings is not None else Options().settings()
        self.state = state
        self.saved: list[dict] = []

    def module_settings(self, module_id: str) -> dict:
        if self.state == "gone":
            raise NotRunning
        if self.state == "off":
            raise ModuleOff
        return dict(self.settings)

    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None:
        self.settings = Options.read(self.settings).update(changes).settings()
        self.saved.append(dict(changes))


class Saver:
    def __init__(self, path: Path, status: int = 0) -> None:
        self.path = path
        self.status = status
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], content: bytes, done) -> None:  # noqa: ANN001
        self.calls.append(argv)
        if self.status == 0:
            self.path.write_bytes(content)
        done(self.status, "")


@pytest.fixture
def environment(tmp_path: Path) -> Path:
    path = tmp_path / "environment"
    path.write_text(TEXT, encoding="utf-8", newline="\n")
    return path


def open_window(
    environment: Path, client: FakeClient | None = None, saver: Saver | None = None
) -> EnvironmentWindow:
    return EnvironmentWindow(
        None,
        client if client is not None else FakeClient(),
        environment,
        saver or Saver(environment),
        BASE,
    )


def names(box: Gtk.ListBox) -> list[str]:
    return [row.name for row in box.get_children()]


def test_the_system_variables_and_what_applies(environment: Path) -> None:
    window = open_window(environment)
    assert names(window.system_list) == ["PATH", "LANG"]
    assert window.applied() == [
        ("PATH", "/usr/local/bin:/usr/bin:/bin", "system"),
        ("LANG", "hu_HU.UTF-8", "system"),
    ]
    assert not window.save_button.get_sensitive()
    assert window.expect == hashlib.sha256(TEXT.encode()).hexdigest()


def test_user_variables_and_a_profile(environment: Path) -> None:
    client = FakeClient(
        Options()
        .update(
            {
                "variables": [["PATH", "$HOME/bin:$PATH"], ["EDITOR", "nano"]],
                "profiles": [["Work", [["EDITOR", "vim"], ["JAVA_HOME", "/opt/jdk"]]]],
                "active_profile": "Work",
            }
        )
        .settings()
    )
    window = open_window(environment, client)
    assert names(window.user) == ["PATH", "EDITOR"]
    assert window.applied() == [
        ("PATH", "/home/b/bin:/usr/local/bin:/usr/bin:/bin", "user"),
        ("EDITOR", "vim", "profile"),
        ("JAVA_HOME", "/opt/jdk", "profile"),
        ("LANG", "hu_HU.UTF-8", "system"),
    ]
    profile_row = window.profiles.get_children()[0]
    assert profile_row.switch.get_active()
    window.apply_profile("Work", False)
    assert client.settings["active_profile"] == ""
    assert ("EDITOR", "nano", "user") in window.applied()
    window._store(window.options.update({"variables": [["EDITOR", "nano"]]}))
    assert names(window.user) == ["EDITOR"]


def test_without_the_tool_only_the_system_part_works(environment: Path) -> None:
    window = open_window(environment, FakeClient(state="off"))
    assert window.options is None
    assert not window.user.get_sensitive()
    assert not window.new_profile.get_sensitive()
    assert "Switch Environment Variables on" in window.user_problem.get_text()
    assert window.add_system.get_sensitive()
    window = open_window(environment, FakeClient(state="gone"))
    assert window.user_problem.get_text() == "TuxToys is not running."


def test_save_the_system_variables_with_a_backup_once(environment: Path) -> None:
    saver = Saver(environment)
    window = open_window(environment, saver=saver)
    window.system.add("JAVA_HOME", "/usr/lib/jvm/default")
    window._set_dirty(True)
    window.save()
    assert "--backup" in saver.calls[0]
    assert saver.calls[0][0] == "pkexec"
    assert environment.read_text() == TEXT + 'JAVA_HOME="/usr/lib/jvm/default"\n'
    assert not window.dirty
    assert window.status.get_text() == "Saved. It applies at the next login."
    window.system.remove(1)
    window._set_dirty(True)
    window.save()
    assert "--backup" not in saver.calls[1]


def test_a_change_made_elsewhere(environment: Path) -> None:
    window = open_window(environment, saver=Saver(environment, status=3))
    window.system.add("A", "1")
    window._set_dirty(True)
    window.save()
    assert window.dirty
    assert "changed outside" in window.bar_text.get_text()
    environment.write_text("B=2\n")
    window.reload()
    assert names(window.system_list) == ["B"]
    environment.write_text("C=3\n")
    window._changed_outside()
    assert names(window.system_list) == ["C"]


def test_the_variable_dialog(environment: Path) -> None:
    window = open_window(environment)
    dialog = VariableDialog(window, "Add", taken=frozenset({"LANG"}))
    assert not dialog.ok.get_sensitive()
    dialog.name.set_text("LANG")
    assert not dialog.ok.get_sensitive()
    dialog.name.set_text("MY_DIRS")
    dialog.value.set_text("/a:/b")
    assert dialog.ok.get_sensitive()
    dialog.as_list.set_active(True)
    buffer = dialog.items.get_buffer()
    assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == "/a\n/b"
    buffer.set_text("/a\n\n/c\n")
    assert dialog.variable == ("MY_DIRS", "/a:/c")
    buffer.set_text("/a:b")
    assert not dialog.ok.get_sensitive()
    dialog.destroy()
    dialog = VariableDialog(window, "Edit", "PATH", "/usr/bin:/bin")
    assert dialog.as_list.get_active()
    dialog.destroy()
    dialog = VariableDialog(window, "Add", system=True)
    dialog.name.set_text("Q")
    dialog.value.set_text("\"'")
    assert not dialog.ok.get_sensitive()
    dialog.destroy()
