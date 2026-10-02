"""The settings window with real GTK, XApp and python3-xapp, and a stand-in client. Needs
a display: xvfb in CI, the desktop otherwise.
"""

from collections.abc import Callable, Mapping

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("XApp", "1.0")
except ValueError as error:
    pytest.skip(f"GTK 3 or XApp is missing: {error}", allow_module_level=True)
pytest.importorskip("xapp.SettingsWidgets", reason="python3-xapp is not installed")

from gi.repository import Gio, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from minttoys.api import ModuleInfo, NotRunning, Refused  # noqa: E402
from minttoys.settings.awake_page import SAVE_AFTER_MS, AwakePage  # noqa: E402
from minttoys.settings.window import SettingsWindow  # noqa: E402

SETTINGS = {
    "default_mode": "indefinite",
    "default_minutes": 60,
    "default_until": "18:00",
    "keep_screen": False,
}


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.state = "on"
        self.error = ""
        self.settings = dict(SETTINGS)
        self.fail: Exception | None = None

    def modules(self) -> list[ModuleInfo]:
        if isinstance(self.fail, NotRunning):
            raise self.fail
        return [ModuleInfo("awake", "Awake", "", self.state, self.error)]

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        self.calls.append(("enabled", module_id, enabled))
        self.state = "on" if enabled else "off"

    def awake_settings(self) -> dict:
        return dict(self.settings)

    def awake_set_settings(self, changes: Mapping[str, object]) -> None:
        if self.fail:
            raise self.fail
        self.calls.append(("settings", dict(changes)))
        self.settings.update(changes)


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def errors() -> list[str]:
    return []


def page_for(client: FakeClient, errors: list[str]) -> AwakePage:
    return AwakePage(client, errors.append)


def test_shows_the_settings(client: FakeClient, errors: list[str]) -> None:
    page = page_for(client, errors)
    assert page.enabled.content_widget.get_active()
    assert page.mode.content_widget.get_active_id() == "indefinite"
    assert page.duration.get() == (1, 0)
    assert page.until.get() == (18, 0)
    assert not page.keep_screen.content_widget.get_active()
    assert not page.duration_revealer.get_reveal_child()
    assert not page.until_revealer.get_reveal_child()
    assert client.calls == []  # showing is not changing


def test_choosing_a_mode_saves_it_and_shows_its_field(
    client: FakeClient, errors: list[str]
) -> None:
    page = page_for(client, errors)
    page.mode.content_widget.set_active_id("duration")
    assert client.calls == [("settings", {"default_mode": "duration"})]
    assert page.duration_revealer.get_reveal_child()
    assert not page.until_revealer.get_reveal_child()


def test_the_screen_switch_saves_at_once(client: FakeClient, errors: list[str]) -> None:
    page = page_for(client, errors)
    page.keep_screen.content_widget.set_active(True)
    assert client.calls == [("settings", {"keep_screen": True})]


def test_the_duration_saves_once_the_fields_settle(
    client: FakeClient, errors: list[str], pump: Callable[..., bool]
) -> None:
    page = page_for(client, errors)
    page.duration.minutes.set_value(15)
    page.duration.minutes.set_value(30)
    assert client.calls == []
    assert pump(lambda: client.calls, seconds=SAVE_AFTER_MS / 1000 + 1)
    assert client.calls == [("settings", {"default_minutes": 90})]


def test_the_time_of_day_saves_as_hh_mm(
    client: FakeClient, errors: list[str], pump: Callable[..., bool]
) -> None:
    page = page_for(client, errors)
    page.until.hours.set_value(7)
    assert pump(lambda: client.calls, seconds=SAVE_AFTER_MS / 1000 + 1)
    assert client.calls == [("settings", {"default_until": "07:00"})]


def test_settings_changed_elsewhere_show_without_saving(
    client: FakeClient, errors: list[str]
) -> None:
    page = page_for(client, errors)
    page.show_settings({**SETTINGS, "default_mode": "until", "keep_screen": True})
    assert page.mode.content_widget.get_active_id() == "until"
    assert page.until_revealer.get_reveal_child()
    assert page.keep_screen.content_widget.get_active()
    assert client.calls == []


def test_with_awake_off_the_settings_wait(client: FakeClient, errors: list[str]) -> None:
    client.state = "off"
    page = page_for(client, errors)
    assert not page.enabled.content_widget.get_active()
    assert not page.click.get_sensitive()
    page.enabled.content_widget.set_active(True)
    assert client.calls == [("enabled", "awake", True)]
    assert page.click.get_sensitive()


def test_a_failed_awake_says_why(client: FakeClient, errors: list[str]) -> None:
    client.state, client.error = "failed", "RuntimeError: no session manager"
    page = page_for(client, errors)
    assert page.problem.get_visible()
    assert "RuntimeError: no session manager" in page.problem.get_text()


def test_without_the_daemon_it_says_so(client: FakeClient, errors: list[str]) -> None:
    client.fail = NotRunning()
    page = page_for(client, errors)
    assert page.problem.get_text() == "MintToys is not running."
    assert not page.enabled.get_sensitive()
    assert not page.click.get_sensitive()


def test_a_refused_change_is_reported_and_undone(client: FakeClient, errors: list[str]) -> None:
    page = page_for(client, errors)
    client.fail = Refused("disk full")
    page.keep_screen.content_widget.set_active(True)
    assert errors == ["MintToys refused: disk full"]
    assert not page.keep_screen.content_widget.get_active()


def test_the_window_holds_the_awake_page(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], client: FakeClient
) -> None:
    _, bus = private_bus
    window = SettingsWindow(None, bus, client)
    assert window.get_title() == "MintToys"
    assert window.awake.mode.content_widget.get_active_id() == "indefinite"
    window.destroy()
