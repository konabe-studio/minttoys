import os
from pathlib import Path

import pytest

from tuxtoys.modules.locksmith.scan import Holder, scan


def can_link(tmp_path: Path) -> bool:
    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        return False
    (tmp_path / "probe").unlink()
    return True


@pytest.fixture
def world(tmp_path: Path) -> Path:
    """A home with a document and a folder, and a /proc of the test's own."""
    if not can_link(tmp_path):
        pytest.skip("symbolic links are not allowed here")
    home = tmp_path / "home"
    (home / "Music").mkdir(parents=True)
    (home / "report.odt").write_text("", encoding="utf-8")
    (home / "Music" / "song.ogg").write_text("", encoding="utf-8")
    (tmp_path / "proc").mkdir()
    return tmp_path


def process(world: Path, pid: int, name: str, files: list[str], cwd: str = "/") -> None:
    entry = world / "proc" / str(pid)
    (entry / "fd").mkdir(parents=True)
    (entry / "comm").write_text(name + "\n", encoding="utf-8")
    for fd, target in enumerate(files):
        os.symlink(target, entry / "fd" / str(fd))
    os.symlink(cwd, entry / "cwd")


def test_finds_the_process_with_the_file_open(world: Path) -> None:
    report = str(world / "home" / "report.odt")
    process(world, 100, "soffice.bin", [report, "socket:[123]"])
    process(world, 200, "bash", ["/dev/pts/0"])
    result = scan([report], world / "proc")
    assert result.holders == [Holder(100, "soffice.bin", (report,))]


def test_a_folder_holds_what_is_inside_it(world: Path) -> None:
    song = str(world / "home" / "Music" / "song.ogg")
    process(world, 100, "rhythmbox", [song])
    result = scan([str(world / "home" / "Music")], world / "proc")
    assert [holder.name for holder in result.holders] == ["rhythmbox"]


def test_working_in_a_folder_counts(world: Path) -> None:
    music = str(world / "home" / "Music")
    process(world, 100, "bash", [], cwd=music)
    assert scan([music], world / "proc").holders == [Holder(100, "bash", (music,))]


def test_a_sibling_with_a_longer_name_is_not_inside(world: Path) -> None:
    (world / "home" / "Music2").mkdir()
    other = str(world / "home" / "Music2")
    process(world, 100, "bash", [], cwd=other)
    assert scan([str(world / "home" / "Music")], world / "proc").holders == []


def test_deleted_files_and_skipped_pids_are_left_out(world: Path) -> None:
    report = str(world / "home" / "report.odt")
    process(world, 100, "old", [report + " (deleted)"])
    process(world, 300, "us", [report])
    assert scan([report], world / "proc", skip=300).holders == []


def test_sorted_by_name_then_pid(world: Path) -> None:
    report = str(world / "home" / "report.odt")
    for pid, name in [(30, "b"), (20, "a"), (10, "b")]:
        process(world, pid, name, [report])
    result = scan([report], world / "proc")
    assert [(holder.name, holder.pid) for holder in result.holders] == [
        ("a", 20),
        ("b", 10),
        ("b", 30),
    ]


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="needs a non-root user")
def test_a_process_whose_files_cannot_be_read_is_reported(world: Path) -> None:
    process(world, 100, "secret", [])
    (world / "proc" / "100" / "fd").chmod(0)
    try:
        result = scan([str(world / "home")], world / "proc")
    finally:
        (world / "proc" / "100" / "fd").chmod(0o755)
    assert result.some_hidden


def test_the_real_proc_finds_this_test_holding_its_own_file(tmp_path: Path) -> None:
    if not Path("/proc/self/fd").is_dir():
        pytest.skip("no /proc here")
    target = tmp_path / "held.txt"
    with target.open("w", encoding="utf-8"):
        result = scan([str(target)])
    assert os.getpid() in [holder.pid for holder in result.holders]
