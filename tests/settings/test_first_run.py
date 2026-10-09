from pathlib import Path

from minttoys.settings import first_run


def test_the_state_directory_from_the_environment(tmp_path: Path) -> None:
    path = first_run.state_file({"XDG_STATE_HOME": str(tmp_path)})
    assert path == tmp_path / "minttoys" / "settings-window.ini"


def test_a_relative_state_directory_is_ignored() -> None:
    path = first_run.state_file({"XDG_STATE_HOME": "relative/state"})
    assert path == Path.home() / ".local" / "state" / "minttoys" / "settings-window.ini"


def test_not_welcomed_before_the_first_time(tmp_path: Path) -> None:
    assert not first_run.welcomed(tmp_path / "settings-window.ini")


def test_welcomed_once_marked(tmp_path: Path) -> None:
    path = tmp_path / "minttoys" / "settings-window.ini"
    first_run.mark_welcomed(path)
    assert first_run.welcomed(path)


def test_a_broken_file_counts_as_not_welcomed(tmp_path: Path) -> None:
    path = tmp_path / "settings-window.ini"
    path.write_text("this is not\n[an ini file", encoding="utf-8")
    assert not first_run.welcomed(path)
