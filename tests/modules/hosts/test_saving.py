from pathlib import Path

import pytest

from tuxtoys.modules.hosts import saving
from tuxtoys.modules.hosts.options import Options

HASH = "a" * 64


def test_from_a_checkout(tmp_path: Path) -> None:
    argv = saving.command(HASH, Options(), backup=True, package_root=tmp_path)
    assert argv[:3] == ["pkexec", "env", f"PYTHONPATH={tmp_path}"]
    assert argv[4:6] == ["-m", "tuxtoys.modules.hosts.save"]
    assert argv[6:] == [
        "--expect",
        HASH,
        "--backup",
        "--keep",
        "age",
        "--count",
        "5",
        "--days",
        "15",
    ]


def test_no_backup_after_the_first_save_or_when_off(tmp_path: Path) -> None:
    argv = saving.command(HASH, Options(), backup=False, package_root=tmp_path)
    assert "--backup" not in argv
    argv = saving.command(HASH, Options(backup=False), backup=True, package_root=tmp_path)
    assert "--backup" not in argv


def test_outcome() -> None:
    assert [saving.outcome(status) for status in (0, 2, 3, 4, 126, 127, 1)] == [
        "saved",
        "bad",
        "changed",
        "failed",
        "dismissed",
        "not-allowed",
        "failed",
    ]


def test_options() -> None:
    options = Options()
    assert options.show_warning
    assert not options.loopback_duplicates
    assert (options.keep, options.count, options.days) == ("age", 5, 15)
    changed = options.update({"keep": "count", "count": 3})
    assert Options.read(changed.settings()) == changed
    for bad, message in (
        ({"keep": "always"}, "keep is never"),
        ({"count": -1}, "count is a whole number"),
        ({"days": True}, "days is a whole number"),
        ({"x": 1}, "unknown setting"),
    ):
        with pytest.raises(ValueError, match=message):
            options.update(bad)
    assert Options.read({"keep": "always", "days": 3}) == Options(days=3)
