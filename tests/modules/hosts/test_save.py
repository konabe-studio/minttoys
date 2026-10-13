import hashlib
import io
import os
import xml.dom.minidom
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tuxtoys.modules.hosts import policy
from tuxtoys.modules.hosts.backups import backup_name, made_at, to_delete
from tuxtoys.modules.hosts.save import BAD, CHANGED, FAILED, MOST_BYTES, SAVED, save

NOW = datetime(2026, 10, 13, 15, 30, tzinfo=UTC)
OLD = "127.0.0.1 localhost\n"
NEW = "10.0.0.1\tdb\n127.0.0.1 localhost\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def hosts(tmp_path: Path) -> Path:
    path = tmp_path / "etc" / "hosts"
    path.parent.mkdir()
    path.write_text(OLD, encoding="utf-8", newline="\n")
    return path


def run(hosts: Path, argv: list[str], content: str | bytes = NEW) -> tuple[int, str]:
    data = content.encode() if isinstance(content, str) else content
    return save(argv, io.BytesIO(data), hosts, hosts.parent.parent / "backups", NOW)


def test_save_with_a_backup(hosts: Path) -> None:
    assert run(hosts, ["--expect", sha(OLD), "--backup"]) == (SAVED, "")
    assert hosts.read_bytes() == NEW.encode()
    backups = hosts.parent.parent / "backups"
    assert [p.name for p in backups.iterdir()] == ["hosts-20261013-153000"]
    assert (backups / "hosts-20261013-153000").read_text() == OLD
    # Nothing left beside it.
    assert sorted(p.name for p in hosts.parent.iterdir()) == ["hosts"]
    # A second backup in the same second gets a number.
    assert run(hosts, ["--expect", sha(NEW), "--backup"], OLD)[0] == SAVED
    assert sorted(p.name for p in backups.iterdir()) == [
        "hosts-20261013-153000",
        "hosts-20261013-153000-2",
    ]


def test_without_a_backup(hosts: Path) -> None:
    assert run(hosts, ["--expect", sha(OLD)]) == (SAVED, "")
    assert not (hosts.parent.parent / "backups").exists()


def test_a_change_made_elsewhere_is_never_lost(hosts: Path) -> None:
    status, reason = run(hosts, ["--expect", sha("something else")])
    assert status == CHANGED
    assert "changed" in reason
    assert hosts.read_text() == OLD


@pytest.mark.parametrize(
    ("argv", "content"),
    [
        (["--expect", "abc"], NEW),
        (["--expect", sha(OLD), "--keep", "forever"], NEW),
        (["--expect", sha(OLD), "--count", "-1"], NEW),
        (["--expect", sha(OLD), "--path", "/etc/shadow"], NEW),
        ([], NEW),
        (["--expect", sha(OLD)], b"a\0b"),
        (["--expect", sha(OLD)], b"\xff\xfe"),
        (["--expect", sha(OLD)], b"x" * (MOST_BYTES + 1)),
    ],
    ids=["short-hash", "keep", "count", "unknown", "no-hash", "nul", "not-utf8", "too-big"],
)
def test_bad_options_and_content(hosts: Path, argv: list[str], content: str | bytes) -> None:
    assert run(hosts, argv, content)[0] == BAD
    assert hosts.read_text() == OLD


@pytest.mark.skipif(not hasattr(os, "symlink") or os.name == "nt", reason="symlinks")
def test_never_through_a_link(hosts: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.write_text(OLD)
    link = tmp_path / "link"
    link.symlink_to(target)
    assert run(link, ["--expect", sha(OLD)])[0] == FAILED
    assert target.read_text() == OLD
    backups = hosts.parent.parent / "backups"
    backups.symlink_to(tmp_path / "etc")
    assert run(hosts, ["--expect", sha(OLD), "--backup"])[0] == FAILED
    assert hosts.read_text() == OLD


@pytest.mark.skipif(os.name == "nt", reason="file modes")
def test_owner_and_mode_are_kept(hosts: Path) -> None:
    hosts.chmod(0o640)
    assert run(hosts, ["--expect", sha(OLD)])[0] == SAVED
    assert hosts.stat().st_mode & 0o777 == 0o640


def test_missing_file(tmp_path: Path) -> None:
    status, reason = run(tmp_path / "hosts", ["--expect", sha(OLD)])
    assert status == FAILED
    assert reason


def test_old_backups_are_deleted(hosts: Path) -> None:
    backups = hosts.parent.parent / "backups"
    backups.mkdir()
    for days in range(1, 9):
        (backups / backup_name(NOW - timedelta(days=days))).write_text("")
    (backups / "notes.txt").write_text("")
    argv = ["--expect", sha(OLD), "--backup", "--keep", "count", "--count", "3"]
    assert run(hosts, argv)[0] == SAVED
    assert len([p for p in backups.iterdir() if p.name.startswith("hosts-")]) == 3
    assert (backups / "notes.txt").exists()


def test_to_delete() -> None:
    names = [backup_name(NOW - timedelta(days=days)) for days in (0, 1, 5, 20, 30, 40)]
    assert to_delete(names, "never", 5, 15, NOW) == []
    assert to_delete(names, "count", 2, 15, NOW) == names[2:]
    # Older than 15 days, but the newest 5 always stay.
    assert to_delete(names, "age", 5, 15, NOW) == names[5:]
    assert to_delete(names, "age", 0, 15, NOW) == names[3:]
    assert to_delete(["hosts", "other"], "count", 0, 0, NOW) == []
    assert made_at("hosts-20261013-153000-2") == NOW
    assert made_at("hosts.bak") is None


def test_policy() -> None:
    text = policy.render(
        {"": "Save the hosts file", "hu": "A hosts fájl mentése"},
        {"": "Authentication is required", "hu": "Hitelesítés & jelszó"},
        "/usr/libexec/tuxtoys/tuxtoys-hosts-save",
    )
    assert '<action id="io.github.konabe_studio.TuxToys.hosts.save">' in text
    assert '<description xml:lang="hu">A hosts fájl mentése</description>' in text
    assert "Hitelesítés &amp; jelszó" in text
    assert "<allow_active>auth_admin_keep</allow_active>" in text
    assert (
        '<annotate key="org.freedesktop.policykit.exec.path">'
        "/usr/libexec/tuxtoys/tuxtoys-hosts-save</annotate>"
    ) in text
    xml.dom.minidom.parseString(text)  # well formed


def test_policy_without_catalogues(tmp_path: Path) -> None:
    assert policy.translated(tmp_path, ["hu"], policy.MESSAGE) == {"": policy.MESSAGE}
