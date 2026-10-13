"""Hosts File Editor's window with real GTK, a hosts file of the test's own, and stand-ins
for pkexec and ping. Needs a display: xvfb in CI, the desktop otherwise.
"""

import hashlib
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

from tuxtoys.api import NotRunning  # noqa: E402
from tuxtoys.hostseditor.window import EntryDialog, HostsWindow  # noqa: E402
from tuxtoys.modules.hosts.hostsfile import Entry  # noqa: E402
from tuxtoys.modules.hosts.options import Options  # noqa: E402

TEXT = """127.0.0.1\tlocalhost
127.0.1.1\tlmde

# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
10.0.0.1 db # work
# 10.0.0.2 old
10.0.0.3 DB
"""


class FakeClient:
    def __init__(self, settings: dict | None = None, running: bool = True) -> None:
        self.settings = settings if settings is not None else Options().settings()
        self.running = running

    def module_settings(self, module_id: str) -> dict:
        if not self.running:
            raise NotRunning
        return dict(self.settings)


class Saver:
    """Saves the way the helper does, or answers with a status of its own."""

    def __init__(self, path: Path, status: int = 0, reason: str = "") -> None:
        self.path = path
        self.status = status
        self.reason = reason
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], content: bytes, done) -> None:  # noqa: ANN001
        self.calls.append(argv)
        if self.status == 0:
            self.path.write_bytes(content)
        done(self.status, self.reason)


@pytest.fixture
def hosts(tmp_path: Path) -> Path:
    path = tmp_path / "hosts"
    path.write_text(TEXT, encoding="utf-8", newline="\n")
    return path


def open_window(
    hosts: Path, saver: Saver | None = None, settings: dict | None = None
) -> HostsWindow:
    return HostsWindow(
        None,
        FakeClient(settings),
        hosts,
        saver or Saver(hosts),
        pinger=lambda address, done: done(address == "127.0.0.1"),
    )


def test_the_entries_are_listed(hosts: Path) -> None:
    window = open_window(hosts)
    rows = window.rows()
    assert [row.entry.address for row in rows] == [
        "127.0.0.1",
        "127.0.1.1",
        "::1",
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.3",
    ]
    assert rows[3].comment.get_text() == "work"
    assert not rows[4].switch.get_active()
    assert [row.doubled for row in rows] == [False, False, False, True, False, True]
    assert not window.save_button.get_sensitive()
    assert window.expect == hashlib.sha256(TEXT.encode()).hexdigest()


def test_filters(hosts: Path) -> None:
    window = open_window(hosts)

    def shown() -> list[str]:
        return [row.entry.address for row in window.rows() if window._shown(row)]

    window.by_hosts.set_text("LOCAL")
    assert shown() == ["127.0.0.1", "::1"]
    window.clear_filters()
    window.only_duplicates.set_active(True)
    assert shown() == ["10.0.0.1", "10.0.0.3"]
    window.clear_filters()
    window.by_comment.set_text("work")
    assert shown() == ["10.0.0.1"]


def test_edit_and_save_with_a_backup_once(hosts: Path) -> None:
    saver = Saver(hosts)
    window = open_window(hosts, saver)
    window.duplicate(window.rows()[3])
    assert window.dirty
    assert window.save_button.get_sensitive()
    window.save()
    assert saver.calls[0][0] == "pkexec"
    assert "--backup" in saver.calls[0]
    assert (
        saver.calls[0][saver.calls[0].index("--expect") + 1]
        == hashlib.sha256(TEXT.encode()).hexdigest()
    )
    assert hosts.read_text().startswith("10.0.0.1\tdb\t# work\n127.0.0.1\tlocalhost\n")
    assert not window.dirty
    assert window.status.get_text() == "Saved."
    # The second save of the session makes no backup.
    window.move(window.rows()[0], up=False)
    window.save()
    assert "--backup" not in saver.calls[1]


def test_switching_an_entry_off_keeps_the_rest(hosts: Path) -> None:
    window = open_window(hosts)
    window.set_active(window.rows()[3], False)
    window.save()
    assert "# 10.0.0.1 db # work\n" in hosts.read_text()
    assert hosts.read_text().replace("# 10.0.0.1 db # work", "10.0.0.1 db # work") == TEXT


def test_a_change_made_elsewhere(hosts: Path) -> None:
    window = open_window(hosts, Saver(hosts, status=3))
    window.hosts.remove(window.rows()[5].index)
    window._changed()
    window.save()
    assert window.dirty
    assert window.bar.get_visible()
    assert "changed outside" in window.bar_text.get_text()
    assert window.reload_button.get_visible()
    window.reload()
    assert not window.dirty
    assert len(window.rows()) == 6


def test_the_password_dialog_dismissed_changes_nothing(hosts: Path) -> None:
    window = open_window(hosts, Saver(hosts, status=126))
    window.duplicate(window.rows()[0])
    window.save()
    assert window.dirty
    assert not window.bar.get_visible()
    assert hosts.read_text() == TEXT


def test_a_failure_is_shown(hosts: Path) -> None:
    window = open_window(hosts, Saver(hosts, status=4, reason="/etc/hosts: No space left"))
    window.duplicate(window.rows()[0])
    window.save()
    assert "No space left" in window.bar_text.get_text()


def test_a_change_on_disk_is_picked_up_when_nothing_is_unsaved(hosts: Path) -> None:
    window = open_window(hosts)
    hosts.write_text("10.9.9.9 new\n")
    window._changed_outside()
    assert [row.entry.address for row in window.rows()] == ["10.9.9.9"]
    window.duplicate(window.rows()[0])
    hosts.write_text("10.8.8.8 other\n")
    window._changed_outside()
    assert window.bar.get_visible()
    assert len(window.rows()) == 2


def test_ping(hosts: Path) -> None:
    window = open_window(hosts)
    window.ping(window.rows()[0])
    window.ping(window.rows()[3])
    assert window.pings == {"127.0.0.1": True, "10.0.0.1": False}


def test_a_missing_file(tmp_path: Path) -> None:
    window = open_window(tmp_path / "missing")
    assert window.rows() == []
    assert "cannot be read" in window.bar_text.get_text()
    assert not window.save_button.get_sensitive()


def test_the_entry_dialog(hosts: Path) -> None:
    window = open_window(hosts)
    dialog = EntryDialog(window, None)
    assert not dialog.ok.get_sensitive()
    dialog.address.set_text("10.1.2.3")
    dialog.hosts.set_text("a b.local")
    dialog.comment.set_text("test")
    assert dialog.ok.get_sensitive()
    assert dialog.entry == Entry("10.1.2.3", ("a", "b.local"), "test")
    dialog.address.set_text("10.1.2")
    assert not dialog.ok.get_sensitive()
    assert dialog.address.get_icon_name(Gtk.EntryIconPosition.SECONDARY)
    dialog.destroy()


def test_loopback_setting(hosts: Path) -> None:
    window = open_window(hosts, settings=Options(loopback_duplicates=True).settings())
    assert [row.doubled for row in window.rows()][:3] == [False, False, False]
    hosts.write_text("127.0.0.1 a\n127.0.1.1 a\n")
    window.reload()
    assert [row.doubled for row in window.rows()] == [True, True]
