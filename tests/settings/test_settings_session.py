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

from gi.repository import Gdk, Gio, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.modules.colorpicker.options import Options as PickerOptions  # noqa: E402
from tuxtoys.modules.hosts.options import Options as HostsOptions  # noqa: E402
from tuxtoys.modules.imageresizer.options import Options as ResizerOptions  # noqa: E402
from tuxtoys.modules.imageresizer.options import Size as ResizerSize  # noqa: E402
from tuxtoys.modules.renameplus.options import Options as RenameOptions  # noqa: E402
from tuxtoys.modules.screenruler.options import Options as RulerOptions  # noqa: E402
from tuxtoys.modules.textextractor import tesseract  # noqa: E402
from tuxtoys.modules.textextractor.options import Options as ExtractorOptions  # noqa: E402
from tuxtoys.settings.alwaysontop_page import AlwaysOnTopPage  # noqa: E402
from tuxtoys.settings.awake_page import SAVE_AFTER_MS, AwakePage  # noqa: E402
from tuxtoys.settings.colorpicker_page import ColorPickerPage  # noqa: E402
from tuxtoys.settings.envvars_page import EnvVarsPage  # noqa: E402
from tuxtoys.settings.general_page import GeneralPage  # noqa: E402
from tuxtoys.settings.hosts_page import HostsPage  # noqa: E402
from tuxtoys.settings.imageresizer_page import ImageResizerPage  # noqa: E402
from tuxtoys.settings.lightswitch_page import LightSwitchPage  # noqa: E402
from tuxtoys.settings.newplus_page import NewPlusPage  # noqa: E402
from tuxtoys.settings.overview_page import OverviewPage  # noqa: E402
from tuxtoys.settings.renameplus_page import RenamePlusPage  # noqa: E402
from tuxtoys.settings.screenruler_page import ScreenRulerPage  # noqa: E402
from tuxtoys.settings.textextractor_page import TextExtractorPage  # noqa: E402
from tuxtoys.settings.window import SettingsWindow  # noqa: E402

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
        self.locksmith_on = "off"
        self.newplus_on = "on"
        self.newplus_settings = {"replace_variables": False, "hide_digits": False}
        self.newplus_calls: list[dict] = []
        self.resizer_on = "on"
        self.resizer_settings = ResizerOptions().settings()
        self.resizer_calls: list[dict] = []
        self.hosts_on = "on"
        self.picker_on = "on"
        self.picker_settings = PickerOptions().settings()
        self.picker_calls: list[dict] = []
        self.ruler_settings = RulerOptions().settings()
        self.extractor_settings = ExtractorOptions().settings()
        self.extractor_calls: list[dict] = []
        self.ruler_calls: list[dict] = []
        self.hosts_settings = HostsOptions().settings()
        self.hosts_calls: list[dict] = []
        self.rename_on = "on"
        self.rename_settings = RenameOptions().settings()
        self.rename_calls: list[dict] = []
        self.pin_on = "on"
        self.pin_settings = {
            "shortcut": True,
            "border": True,
            "border_color": "",
            "border_width": 4,
            "opacity_shortcuts": True,
            "border_opacity": 100,
            "border_radius": 8,
            "sound": False,
            "excluded": "vlc",
        }
        self.pin_state = {
            "shortcut": "<Primary><Super>t",
            "shortcut_problem": "",
            "opacity_problem": "",
        }
        self.pin_calls: list[dict] = []

    def modules(self) -> list[ModuleInfo]:
        if isinstance(self.fail, NotRunning):
            raise self.fail
        if not self.listed:
            return []
        return [
            ModuleInfo("awake", "Awake", "", self.state, self.error),
            ModuleInfo("lightswitch", "Light Switch", "", self.light_on, ""),
            ModuleInfo("locksmith", "File Locksmith", "", self.locksmith_on, ""),
            ModuleInfo("alwaysontop", "Always on Top", "", self.pin_on, ""),
            ModuleInfo("newplus", "New+", "", self.newplus_on, ""),
            ModuleInfo("imageresizer", "Image Resizer", "", self.resizer_on, ""),
            ModuleInfo("renameplus", "Rename+", "", self.rename_on, ""),
            ModuleInfo("hosts", "Hosts File Editor", "", self.hosts_on, ""),
            ModuleInfo("envvars", "Environment Variables", "", "off", ""),
            ModuleInfo("colorpicker", "Color Picker", "", self.picker_on, ""),
            ModuleInfo("screenruler", "Screen Ruler", "", "on", ""),
            ModuleInfo("textextractor", "Text Extractor", "", "on", ""),
        ]

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        if module_id == "lightswitch":
            self.light_calls.append(("enabled", enabled))
            self.light_on = "on" if enabled else "off"
            return
        if module_id == "locksmith":
            self.light_calls.append(("locksmith", enabled))
            self.locksmith_on = "on" if enabled else "off"
            return
        self.calls.append(("enabled", module_id, enabled))
        self.state = "on" if enabled else "off"

    def module_settings(self, module_id: str) -> dict:
        if module_id == "lightswitch":
            return dict(self.light_settings)
        if module_id == "alwaysontop":
            return dict(self.pin_settings)
        if module_id == "newplus":
            return dict(self.newplus_settings)
        if module_id == "imageresizer":
            return dict(self.resizer_settings)
        if module_id == "renameplus":
            return dict(self.rename_settings)
        if module_id == "hosts":
            return dict(self.hosts_settings)
        if module_id == "colorpicker":
            return dict(self.picker_settings)
        if module_id == "screenruler":
            return dict(self.ruler_settings)
        if module_id == "textextractor":
            return dict(self.extractor_settings)
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
        if module_id == "alwaysontop":
            self.pin_calls.append(dict(changes))
            self.pin_settings.update(changes)
            return
        if module_id == "newplus":
            self.newplus_calls.append(dict(changes))
            self.newplus_settings.update(changes)
            return
        if module_id == "textextractor":
            self.extractor_calls.append(dict(changes))
            options = ExtractorOptions.read(self.extractor_settings).update(changes)
            self.extractor_settings = options.settings()
            return
        if module_id == "screenruler":
            self.ruler_calls.append(dict(changes))
            self.ruler_settings = RulerOptions.read(self.ruler_settings).update(changes).settings()
            return
        if module_id == "colorpicker":
            self.picker_calls.append(dict(changes))
            options = PickerOptions.read(self.picker_settings).update(changes)
            self.picker_settings = options.settings()
            return
        if module_id == "hosts":
            self.hosts_calls.append(dict(changes))
            self.hosts_settings = HostsOptions.read(self.hosts_settings).update(changes).settings()
            return
        if module_id == "renameplus":
            self.rename_calls.append(dict(changes))
            options = RenameOptions.read(self.rename_settings).update(changes)
            self.rename_settings = options.settings()
            return
        if module_id == "imageresizer":
            self.resizer_calls.append(dict(changes))
            self.resizer_settings = (
                ResizerOptions.read(self.resizer_settings).update(changes).settings()
            )
            return
        self.calls.append(("settings", dict(changes)))
        self.settings.update(changes)

    def alwaysontop_state(self) -> dict:
        return dict(self.pin_state)

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
    assert page.problem.get_text() == "TuxToys is not running."
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
    assert page.problem.get_text() == "This version of TuxToys has no Awake."
    assert not page.enabled.get_sensitive()
    assert not page.click.get_sensitive()


def test_a_refused_change_is_reported_and_undone(client: FakeClient, errors: list[str]) -> None:
    page = page_for(client, errors)
    client.fail = Refused("disk full")
    page.keep_screen.content_widget.set_active(True)
    assert errors == ["TuxToys refused: disk full"]
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
    assert window.get_title() == "TuxToys"
    assert window.awake.mode.content_widget.get_active_id() == "indefinite"


def test_the_sidebar_starts_with_the_overview_then_the_tools_under_headings(
    window: SettingsWindow,
) -> None:
    rows = window.sidebar.get_children()
    assert [row.page for row in rows] == [
        "overview",
        "general",
        "awake",
        "lightswitch",
        "hosts",
        "envvars",
        "alwaysontop",
        "colorpicker",
        "screenruler",
        "textextractor",
        "locksmith",
        "newplus",
        "imageresizer",
        "renameplus",
    ]
    assert rows[0].get_header() is None
    assert rows[1].get_header() is None
    assert rows[2].get_header().get_text() == "System"
    assert rows[3].get_header() is None
    assert rows[4].get_header() is None
    assert rows[5].get_header() is None
    assert rows[6].get_header().get_text() == "Windows"
    assert rows[7].get_header().get_text() == "Screen"
    assert rows[10].get_header().get_text() == "Files"
    assert rows[0].get_child().get_children()[-1].get_text() == "Home"
    assert window.stack.get_visible_child_name() == "overview"


def test_choosing_a_tool_shows_its_page(window: SettingsWindow) -> None:
    window.show_page("awake")
    assert window.stack.get_visible_child_name() == "awake"


def test_the_overview_lists_every_tool_with_its_switch(window: SettingsWindow) -> None:
    row = window.overview.rows["awake"]
    assert row.name.get_text() == "Awake"
    assert row.content_widget.get_active()


def test_the_overview_lists_the_tools_in_the_sidebars_order(window: SettingsWindow) -> None:
    sidebar = [row.page for row in window.sidebar.get_children()][2:]
    assert list(window.overview.rows) == sidebar


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
    assert page.problem.get_text() == "TuxToys is not running."
    assert not page.rows["awake"].get_sensitive()


def test_the_first_open_greets_once(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    client: FakeClient,
    tmp_path: Path,
) -> None:
    _, bus = private_bus
    state = tmp_path / "tuxtoys" / "settings-window.ini"
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


def test_file_locksmith_page_switches_it(window: SettingsWindow, client: FakeClient) -> None:
    page = window.locksmith
    assert not page.enabled.content_widget.get_active()
    page.enabled.content_widget.set_active(True)
    assert client.light_calls == [("locksmith", True)]
    assert page.enabled.content_widget.get_active()


@pytest.fixture
def templates_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "Templates"
    folder.mkdir()
    (folder / "Note.txt").write_text("", encoding="utf-8")
    (folder / "Letter.odt").write_text("", encoding="utf-8")
    return folder


def newplus_page(client: FakeClient, errors: list[str], folder: Path | None) -> NewPlusPage:
    return NewPlusPage(client, errors.append, lambda: folder, lambda path: path.unlink())


def listed(page: NewPlusPage) -> list[str]:
    return [row.template.name for row in page.list.get_children() if hasattr(row, "template")]


def test_new_plus_lists_the_templates(
    client: FakeClient, errors: list[str], templates_folder: Path
) -> None:
    page = newplus_page(client, errors, templates_folder)
    assert listed(page) == ["Letter.odt", "Note.txt"]
    assert page.where.content_widget.get_text() == str(templates_folder)


def test_new_plus_adds_renames_and_removes(
    client: FakeClient, errors: list[str], templates_folder: Path, tmp_path: Path
) -> None:
    page = newplus_page(client, errors, templates_folder)
    source = tmp_path / "Note.txt"
    source.write_text("", encoding="utf-8")
    page.add_files([source])
    assert "Note (2).txt" in listed(page)
    (letter,) = [row.template for row in page.list.get_children() if hasattr(row, "template")][:1]
    assert page.rename(letter, "Invoice.odt")
    assert (templates_folder / "Invoice.odt").exists()
    note = next(
        r.template
        for r in page.list.get_children()
        if getattr(r, "template", None) and r.template.name == "Note.txt"
    )
    page.remove(note)
    assert listed(page) == ["Invoice.odt", "Note (2).txt"]
    assert errors == []


def test_new_plus_refuses_a_taken_name(
    client: FakeClient, errors: list[str], templates_folder: Path
) -> None:
    page = newplus_page(client, errors, templates_folder)
    letter = next(r.template for r in page.list.get_children() if hasattr(r, "template"))
    assert not page.rename(letter, "Note.txt")
    assert errors == ["There is a template called Note.txt already."]


def test_new_plus_without_a_folder_offers_to_make_one(
    client: FakeClient, errors: list[str]
) -> None:
    page = newplus_page(client, errors, None)
    assert page.where.content_widget.get_text() == "You have no templates folder."
    assert page.make_button.get_parent().get_visible()
    assert not page.add_button.get_parent().get_visible()


def activate(row: Gtk.Widget) -> None:
    """A click on the row, as GTK reports it: the row's own list box activates it."""
    list_row = row.get_parent()
    list_row.get_parent().emit("row-activated", list_row)


def test_a_click_on_an_overview_row_opens_the_tool(
    window: SettingsWindow, client: FakeClient
) -> None:
    activate(window.overview.rows["lightswitch"])
    assert window.stack.get_visible_child_name() == "lightswitch"
    assert client.calls == []
    assert client.light_calls == []


def test_the_switch_on_an_overview_row_only_switches(
    window: SettingsWindow, client: FakeClient
) -> None:
    window.overview.rows["awake"].content_widget.set_active(False)
    assert client.calls == [("enabled", "awake", False)]
    assert window.stack.get_visible_child_name() == "overview"


def test_new_plus_shows_and_saves_its_naming_settings(
    client: FakeClient, errors: list[str], tmp_path: Path
) -> None:
    client.newplus_settings["hide_digits"] = True
    page = newplus_page(client, errors, tmp_path)
    assert not page.variables.content_widget.get_active()
    assert page.digits.content_widget.get_active()
    assert page.names.get_sensitive()
    page.variables.content_widget.set_active(True)
    assert client.newplus_calls == [{"replace_variables": True}]


def test_new_plus_naming_is_grey_while_it_is_off(
    client: FakeClient, errors: list[str], tmp_path: Path
) -> None:
    client.newplus_on = "off"
    page = newplus_page(client, errors, tmp_path)
    assert not page.names.get_sensitive()


def pin_page(client: FakeClient, errors: list[str]) -> AlwaysOnTopPage:
    return AlwaysOnTopPage(client, errors.append)


def test_always_on_top_shows_its_settings_and_keys(client: FakeClient, errors: list[str]) -> None:
    page = pin_page(client, errors)
    assert page.enabled.content_widget.get_active()
    assert page.shortcut.content_widget.get_active()
    assert page.keys.get_text() == "Ctrl+Super+T"
    assert page.accent.content_widget.get_active()
    assert not page.color_revealer.get_reveal_child()
    assert page.width.content_widget.get_value() == 4
    assert client.pin_calls == []


def test_always_on_top_a_color_of_ones_own(client: FakeClient, errors: list[str]) -> None:
    page = pin_page(client, errors)
    rgba = Gdk.RGBA()
    rgba.parse("#ff8000")
    page.color.content_widget.set_rgba(rgba)
    page.accent.content_widget.set_active(False)
    assert client.pin_calls == [{"border_color": "#ff8000"}]
    assert page.color_revealer.get_reveal_child()


def test_always_on_top_switches_save(client: FakeClient, errors: list[str]) -> None:
    page = pin_page(client, errors)
    page.border.content_widget.set_active(False)
    page.shortcut.content_widget.set_active(False)
    assert client.pin_calls == [{"border": False}, {"shortcut": False}]


def test_always_on_top_says_its_keys_were_taken(client: FakeClient, errors: list[str]) -> None:
    client.pin_state = {"shortcut": "", "shortcut_problem": "taken"}
    page = pin_page(client, errors)
    assert page.keys.get_text().startswith("Its keyboard shortcut, Ctrl+Super+T,")


def test_always_on_top_shows_the_rest(client: FakeClient, errors: list[str]) -> None:
    page = pin_page(client, errors)
    assert page.opacity_shortcuts.content_widget.get_active()
    assert "Page Up" in page.opacity_keys.get_text()
    assert page.opacity.content_widget.get_value() == 100
    assert page.radius.content_widget.get_value() == 8
    assert not page.sound.content_widget.get_active()
    assert page.excluded.text == "vlc"
    assert client.pin_calls == []


def test_always_on_top_saves_the_rest(client: FakeClient, errors: list[str]) -> None:
    page = pin_page(client, errors)
    page.sound.content_widget.set_active(True)
    page.opacity_shortcuts.content_widget.set_active(False)
    page.radius.content_widget.set_value(0)
    page.opacity.content_widget.set_value(60)
    page.excluded.text = "vlc\nfirefox"
    page._save_now()
    assert client.pin_calls == [
        {"sound": True},
        {"opacity_shortcuts": False},
        {"border_radius": 0, "border_opacity": 60, "excluded": "vlc\nfirefox"},
    ]
    assert page.opacity_keys.get_text() == ""


def test_always_on_top_says_its_opacity_keys_were_taken(
    client: FakeClient, errors: list[str]
) -> None:
    client.pin_state = {"shortcut": "", "shortcut_problem": "", "opacity_problem": "taken"}
    page = pin_page(client, errors)
    assert "is in use already" in page.opacity_keys.get_text()


def resizer_page(client: FakeClient, errors: list[str]) -> ImageResizerPage:
    return ImageResizerPage(client, errors.append)


def test_image_resizer_lists_its_sizes(client: FakeClient, errors: list[str]) -> None:
    page = resizer_page(client, errors)
    rows = page.sizes.get_children()
    assert [row.size.shown_name for row in rows] == ["Small", "Medium", "Large", "Phone"]
    assert page.quality.content_widget.get_value() == 90
    assert page.file_name.content_widget.get_text() == "%1 (%2)"
    assert not page.keep_date.content_widget.get_active()
    assert client.resizer_calls == []


def test_image_resizer_adds_and_removes_sizes(client: FakeClient, errors: list[str]) -> None:
    page = resizer_page(client, errors)
    page.set_size(None, ResizerSize("Web", "fill", 800, 0, "px"))
    assert client.resizer_calls[-1]["sizes"][-1] == ("Web", "fill", 800, 0, "px")
    assert [row.size.name for row in page.sizes.get_children()][-1] == "Web"
    page.remove_size(0)
    assert page.sizes.get_children()[0].size.name == "$medium$"


def test_image_resizer_keeps_the_date_on_its_switch(client: FakeClient, errors: list[str]) -> None:
    page = resizer_page(client, errors)
    page.keep_date.content_widget.set_active(True)
    assert client.resizer_calls == [{"keep_date": True}]


def test_image_resizer_saves_a_file_name_only_once_it_can_be_used(
    client: FakeClient, errors: list[str]
) -> None:
    page = resizer_page(client, errors)
    entry = page.file_name.content_widget
    entry.set_text("%2/")
    assert page.file_name_problem
    assert page._pending == {}
    entry.set_text("%2/%1")
    assert not page.file_name_problem
    page._save_now()
    assert client.resizer_calls == [{"file_name": "%2/%1"}]
    assert errors == []


def test_rename_plus_page(client: FakeClient) -> None:
    page = RenamePlusPage(client, lambda message: None)
    assert page.restore_flags.content_widget.get_active()
    assert not page.nemo_rename.content_widget.get_active()
    assert not page.forget.get_sensitive()
    page.nemo_rename.content_widget.set_active(True)
    assert client.rename_calls[-1] == {"nemo_rename": True}
    client.rename_settings["recent_search"] = ["a"]
    page.refresh()
    assert page.forget.get_sensitive()
    page._on_forget()
    assert client.rename_calls[-1] == {"recent_search": [], "recent_replace": []}
    assert not page.forget.get_sensitive()
    client.rename_on = "off"
    page.refresh()
    assert not page.window.get_sensitive()


def test_hosts_page(client: FakeClient) -> None:
    opened: list[object] = []
    page = HostsPage(client, lambda message: None, opened.append)
    assert page.show_warning.content_widget.get_active()
    assert page.backup.content_widget.get_active()
    assert page.keep.content_widget.get_active_id() == "age"
    assert page.count_revealer.get_reveal_child()
    assert page.days_revealer.get_reveal_child()
    page.keep.content_widget.set_active_id("count")
    assert client.hosts_calls[-1] == {"keep": "count"}
    assert not page.days_revealer.get_reveal_child()
    page.loopback.content_widget.set_active(True)
    assert client.hosts_calls[-1] == {"loopback_duplicates": True}
    page.count.content_widget.set_value(7)
    page._save_numbers()
    assert client.hosts_calls[-1] == {"count": 7}
    page.backup.content_widget.set_active(False)
    assert not page.keep.get_sensitive()
    page._on_open()
    assert len(opened) == 1
    client.hosts_on = "off"
    page.refresh()
    assert not page.backups.get_sensitive()


class FakeTray:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")


def test_general_page_panel_icon(client: FakeClient, tmp_path: Path) -> None:
    tray = FakeTray()
    page = GeneralPage(client, lambda message: None, tray, lambda: tmp_path / "autostart")
    assert page.panel_icon.content_widget.get_active()
    page.panel_icon.content_widget.set_active(False)
    assert tray.calls == ["stop"]
    assert (tmp_path / "autostart" / "io.github.konabe_studio.TuxToys.Tray.desktop").exists()
    page.panel_icon.content_widget.set_active(True)
    assert tray.calls == ["stop", "start"]
    assert not (tmp_path / "autostart" / "io.github.konabe_studio.TuxToys.Tray.desktop").exists()
    assert set(page.links.links) == {"docs", "code", "bug", "idea"}


def test_general_page_backs_up_and_restores(client: FakeClient, tmp_path: Path) -> None:
    errors: list[str] = []
    target = tmp_path / "settings.json"
    page = GeneralPage(
        client, errors.append, FakeTray(), lambda: tmp_path / "autostart", lambda saving: target
    )
    page._on_back_up()
    assert '"format": "tuxtoys-settings"' in target.read_text(encoding="utf-8")
    # What has not changed is not sent back.
    page._on_restore()
    assert client.hosts_calls == []
    assert client.rename_calls == []
    client.hosts_settings["days"] = 99
    client.rename_settings["regex"] = True
    page._on_restore()
    assert client.hosts_settings["days"] == 15
    assert client.rename_settings["regex"] is False
    assert errors == []
    target.write_text("{}", encoding="utf-8")
    page._on_restore()
    assert errors == ["This is not a file of TuxToys settings."]


def test_envvars_page_opens_the_window(client: FakeClient) -> None:
    opened: list[object] = []
    page = EnvVarsPage(client, lambda message: None, opened.append)
    page._on_open()
    assert len(opened) == 1


class FakeShortcut:
    def __init__(self, keys: str) -> None:
        self.keys = keys

    def current_keys(self) -> str:
        return self.keys


def test_colorpicker_page(client: FakeClient) -> None:
    opened: list[object] = []
    shortcut = FakeShortcut("<Shift><Super>c")
    page = ColorPickerPage(client, lambda message: None, opened.append, shortcut)
    assert page.format.content_widget.get_active_id() == "HEX"
    assert page.keys.get_text() == "Shift+Super+C"
    page.format.content_widget.set_active_id("RGB")
    assert client.picker_calls[-1] == {"default_format": "RGB"}
    page.shortcut.content_widget.set_active(False)
    assert client.picker_calls[-1] == {"shortcut": False}
    assert page.keys.get_text() == ""
    page._opener(lambda message: None)
    assert len(opened) == 1
    taken = ColorPickerPage(client, lambda message: None, opened.append, FakeShortcut(""))
    taken._save({"shortcut": True})
    assert "in use already" in taken.keys.get_text()


def test_a_tool_the_running_service_does_not_have(client: FakeClient) -> None:
    client.listed = False
    page = HostsPage(client, lambda message: None)
    assert not page.enabled.get_sensitive()
    assert "does not have this tool" in page.problem.get_text()


def test_colorpicker_page_behaviour_and_formats(client: FakeClient) -> None:
    page = ColorPickerPage(client, lambda message: None, lambda error: None, FakeShortcut(""))
    assert page.activation.content_widget.get_active_id() == "pick"
    assert page.buttons["left"].content_widget.get_active_id() == "pick-editor"
    page.activation.content_widget.set_active_id("editor")
    assert client.picker_calls[-1] == {"activation": "editor"}
    page.buttons["right"].content_widget.set_active_id("pick-close")
    assert client.picker_calls[-1] == {"right": "pick-close"}
    page.show_name.content_widget.set_active(True)
    assert client.picker_calls[-1] == {"show_name": True}
    rows = page.formats_list.get_children()
    assert len(rows) == 16
    page.move_format(0, 1)
    assert [entry[0] for entry in client.picker_calls[-1]["formats"][:2]] == ["RGB", "HEX"]
    page.delete_format(0)
    assert "RGB" not in [entry[0] for entry in client.picker_calls[-1]["formats"]]


def test_colorpicker_formats_reorder_by_drag(client: FakeClient) -> None:
    page = ColorPickerPage(client, lambda message: None, lambda error: None, FakeShortcut(""))
    page.reorder_format(0, 2)
    assert [entry[0] for entry in client.picker_calls[-1]["formats"][:3]] == ["RGB", "HSL", "HEX"]
    page.reorder_format(2, 0)
    assert [entry[0] for entry in client.picker_calls[-1]["formats"][:3]] == ["HEX", "RGB", "HSL"]


def test_screenruler_page(client: FakeClient) -> None:
    opened: list[object] = []
    page = ScreenRulerPage(
        client, lambda message: None, opened.append, FakeShortcut("<Primary><Shift><Super>m")
    )
    assert page.keys.get_text() == "Shift+Ctrl+Super+M"
    assert page.mode.content_widget.get_active_id() == "none"
    assert page.unit.content_widget.get_active_id() == "none"
    assert page.tolerance.content_widget.get_value() == 30
    page.mode.content_widget.set_active_id("spacing")
    assert client.ruler_calls[-1] == {"default_mode": "spacing"}
    page.unit.content_widget.set_active_id("cm")
    assert client.ruler_calls[-1] == {"extra_unit": "cm"}
    page.per_channel.content_widget.set_active(True)
    assert client.ruler_calls[-1] == {"per_channel": True}
    page.draw_feet.content_widget.set_active(False)
    assert client.ruler_calls[-1] == {"draw_feet": False}
    page.tolerance.content_widget.set_value(45)
    page._save_tolerance()
    assert client.ruler_calls[-1] == {"tolerance": 45}
    page._opener(lambda message: None)
    assert len(opened) == 1


def test_textextractor_page(client: FakeClient) -> None:
    opened: list[object] = []
    page = TextExtractorPage(
        client,
        lambda message: None,
        opened.append,
        FakeShortcut("<Shift><Super>t"),
        lambda: ["deu", "eng", "hun"],
    )
    assert page.keys.get_text() == "Shift+Super+T"
    # Nothing set: the desktop's language.
    wanted = tesseract.pick("", ["deu", "eng", "hun"])
    assert page.language.content_widget.get_active_id() == wanted
    page.language.content_widget.set_active_id("hun")
    assert client.extractor_calls[-1] == {"language": "hun"}
    page.shortcut.content_widget.set_active(False)
    assert client.extractor_calls[-1] == {"shortcut": False}
    page._opener(lambda message: None)
    assert len(opened) == 1


def test_textextractor_page_without_tesseract(client: FakeClient) -> None:
    page = TextExtractorPage(
        client, lambda message: None, lambda error: None, FakeShortcut(""), lambda: None
    )
    assert not page.language.get_sensitive()
