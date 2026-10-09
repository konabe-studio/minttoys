"""The settings window with real GTK, XApp and python3-xapp, and a stand-in client. Needs
a display: xvfb in CI, the desktop otherwise.
"""

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

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

from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from minttoys.settings.awake_page import SAVE_AFTER_MS, AwakePage  # noqa: E402
from minttoys.settings.lightswitch_page import LightSwitchPage  # noqa: E402
from minttoys.settings.overview_page import OverviewPage  # noqa: E402
from minttoys.settings.window import SettingsWindow  # noqa: E402

SETTINGS = {
    "default_mode": "indefinite",
    "default_minutes": 60,
    "default_until": "18:00",
    "keep_screen": False,
}
LIGHT_SETTINGS = {
    "day_mode": "",
    "schedule": "night-light",
    "dark_from": "20:00",
    "dark_to": "06:00",
    "shortcut": True,
}
LIGHT_STATE = {
    "dark": False,
    "dark_from": "18:09",
    "dark_to": "06:53",
    "by_sun": True,
    "problem": "",
    "shortcut": "<Primary><Shift><Super>d",
    "shortcut_problem": "",
}


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.state = "on"
        self.error = ""
        self.settings = dict(SETTINGS)
        self.fail: Exception | None = None
        self.settings_fail: Exception | None = None
        self.listed = True
        # Light Switch, kept apart so that Awake's tests see only Awake's calls.
        self.light_on = "on"
        self.light_settings = dict(LIGHT_SETTINGS)
        self.light_state = dict(LIGHT_STATE)
        self.light_calls: list[tuple] = []

    def modules(self) -> list[ModuleInfo]:
        if isinstance(self.fail, NotRunning):
            raise self.fail
        if not self.listed:
            return []
        return [
            ModuleInfo("awake", "Awake", "", self.state, self.error),
            ModuleInfo("lightswitch", "Light Switch", "", self.light_on, ""),
        ]

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        if module_id == "lightswitch":
            self.light_calls.append(("enabled", enabled))
            self.light_on = "on" if enabled else "off"
            return
        self.calls.append(("enabled", module_id, enabled))
        self.state = "on" if enabled else "off"

    def module_settings(self, module_id: str) -> dict:
        if module_id == "lightswitch":
            return dict(self.light_settings)
        if self.settings_fail:
            raise self.settings_fail
        return dict(self.settings)

    def set_module_settings(self, module_id: str, changes: Mapping[str, object]) -> None:
        if self.fail:
            raise self.fail
        if module_id == "lightswitch":
            self.light_calls.append(("settings", dict(changes)))
            self.light_settings.update(changes)
            return
        self.calls.append(("settings", dict(changes)))
        self.settings.update(changes)

    def lightswitch_state(self) -> dict:
        if self.light_on != "on":
            raise ModuleOff()
        return dict(self.light_state)

    def lightswitch_toggle(self) -> None:
        self.light_calls.append(("toggle",))
        self.light_state["dark"] = not self.light_state["dark"]


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


def test_unreadable_settings_say_why(client: FakeClient, errors: list[str]) -> None:
    client.settings_fail = ModuleOff("No such method 'GetModuleSettings'")
    page = page_for(client, errors)
    assert page.problem.get_visible()
    assert page.problem.get_text() == (
        "Could not read Awake's settings: No such method 'GetModuleSettings'"
    )
    assert page.enabled.get_sensitive()  # switching Awake off and on again may help
    assert page.enabled.content_widget.get_active()
    assert not page.click.get_sensitive()


def test_a_missing_awake_says_so(client: FakeClient, errors: list[str]) -> None:
    client.listed = False
    page = page_for(client, errors)
    assert page.problem.get_text() == "This version of MintToys has no Awake."
    assert not page.enabled.get_sensitive()
    assert not page.click.get_sensitive()


def test_a_refused_change_is_reported_and_undone(client: FakeClient, errors: list[str]) -> None:
    page = page_for(client, errors)
    client.fail = Refused("disk full")
    page.keep_screen.content_widget.set_active(True)
    assert errors == ["MintToys refused: disk full"]
    assert not page.keep_screen.content_widget.get_active()


@pytest.fixture
def window(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    client: FakeClient,
    tmp_path: Path,
) -> Iterator[SettingsWindow]:
    _, bus = private_bus
    shown = SettingsWindow(None, bus, client, tmp_path / "settings-window.ini")
    yield shown
    shown.destroy()


def test_the_window_holds_the_awake_page(window: SettingsWindow) -> None:
    assert window.get_title() == "MintToys"
    assert window.awake.mode.content_widget.get_active_id() == "indefinite"


def test_the_sidebar_starts_with_the_overview_then_the_tools_under_headings(
    window: SettingsWindow,
) -> None:
    rows = window.sidebar.get_children()
    assert [row.page for row in rows] == ["overview", "awake", "lightswitch"]
    assert rows[0].get_header() is None
    assert rows[1].get_header().get_text() == "System"
    assert rows[2].get_header() is None
    assert window.stack.get_visible_child_name() == "overview"


def test_choosing_a_tool_shows_its_page(window: SettingsWindow) -> None:
    window.show_page("awake")
    assert window.stack.get_visible_child_name() == "awake"


def test_the_overview_lists_every_tool_with_its_switch(window: SettingsWindow) -> None:
    row = window.overview.rows["awake"]
    assert row.name.get_text() == "Awake"
    assert row.content_widget.get_active()


def test_a_switch_on_the_overview_turns_the_tool_on_and_off(
    window: SettingsWindow, client: FakeClient
) -> None:
    window.overview.rows["awake"].content_widget.set_active(False)
    assert client.calls == [("enabled", "awake", False)]
    assert client.state == "off"


def test_the_overview_says_why_a_tool_failed(client: FakeClient, errors: list[str]) -> None:
    client.state, client.error = "failed", "RuntimeError: no session manager"
    page = OverviewPage(client, errors.append, welcome=False)
    text = page.rows["awake"].description.get_text()
    assert text.endswith("Could not be switched on: RuntimeError: no session manager")
    assert not page.rows["awake"].content_widget.get_active()


def test_without_the_daemon_the_overview_says_so(client: FakeClient, errors: list[str]) -> None:
    page = OverviewPage(client, errors.append, welcome=False)
    client.fail = NotRunning()
    page.refresh()
    assert page.problem.get_text() == "MintToys is not running."
    assert not page.rows["awake"].get_sensitive()


def test_the_first_open_greets_once(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    client: FakeClient,
    tmp_path: Path,
) -> None:
    _, bus = private_bus
    state = tmp_path / "minttoys" / "settings-window.ini"
    first = SettingsWindow(None, bus, client, state)
    assert first.overview.welcome.get_visible()
    first.destroy()
    second = SettingsWindow(None, bus, client, state)
    assert not second.overview.welcome.get_visible()
    second.destroy()


def light_page(client: FakeClient, errors: list[str]) -> LightSwitchPage:
    return LightSwitchPage(client, errors.append)


def test_light_switch_shows_its_settings_and_hours(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    assert page.enabled.content_widget.get_active()
    assert page.day.content_widget.get_active_id() == "mixed"  # not chosen yet
    assert page.schedule.content_widget.get_active_id() == "night-light"
    assert page.night_light_revealer.get_reveal_child()
    assert not page.from_revealer.get_reveal_child()
    assert page.hours.get_text() == "Dark from 18:09 to 06:53, sunset to sunrise."
    assert client.light_calls == []


def test_light_switch_set_times_show_their_fields(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    page.schedule.content_widget.set_active_id("times")
    assert client.light_calls == [("settings", {"schedule": "times"})]
    assert page.from_revealer.get_reveal_child()
    assert page.to_revealer.get_reveal_child()
    assert not page.night_light_revealer.get_reveal_child()


def test_light_switch_day_mode_saves(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    page.day.content_widget.set_active_id("light")
    assert client.light_calls == [("settings", {"day_mode": "light"})]


def test_light_switch_times_save_once_the_fields_settle(
    client: FakeClient, errors: list[str], pump: Callable[..., bool]
) -> None:
    client.light_settings["schedule"] = "times"
    page = light_page(client, errors)
    page.dark_from.hours.set_value(21)
    assert pump(lambda: client.light_calls, seconds=SAVE_AFTER_MS / 1000 + 1)
    assert client.light_calls == [("settings", {"dark_from": "21:00"})]


def test_light_switch_switch_now(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    page.switch_now.content_widget.clicked()
    assert client.light_calls == [("toggle",)]


def test_light_switch_says_why_it_leaves_custom_themes(
    client: FakeClient, errors: list[str]
) -> None:
    client.light_state["problem"] = "custom"
    page = light_page(client, errors)
    assert page.hours.get_text().endswith("so Light Switch leaves them alone.")


def test_light_switch_off_waits(client: FakeClient, errors: list[str]) -> None:
    client.light_on = "off"
    page = light_page(client, errors)
    assert not page.enabled.content_widget.get_active()
    assert not page.modes.get_sensitive()
    assert not page.now.get_sensitive()
    page.enabled.content_widget.set_active(True)
    assert client.light_calls == [("enabled", True)]
    assert page.modes.get_sensitive()


def test_light_switch_shows_its_shortcut(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    assert page.shortcut.content_widget.get_active()
    assert page.keys.get_text() == "Shift+Ctrl+Super+D"


def test_light_switch_shortcut_can_be_switched_off(client: FakeClient, errors: list[str]) -> None:
    page = light_page(client, errors)
    page.shortcut.content_widget.set_active(False)
    assert client.light_calls == [("settings", {"shortcut": False})]


def test_light_switch_says_its_shortcut_was_taken(client: FakeClient, errors: list[str]) -> None:
    client.light_state.update(shortcut="", shortcut_problem="taken")
    page = light_page(client, errors)
    assert page.keys.get_text() == (
        "Its keyboard shortcut, Shift+Ctrl+Super+D, is in use already, so it has none."
    )
