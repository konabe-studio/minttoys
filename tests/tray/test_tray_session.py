"""The panel icon with real GTK and XApp, a stand-in client, and a D-Bus daemon of the
test's own. Needs a display: xvfb in CI, the desktop otherwise.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("XApp", "1.0")
except ValueError as error:
    pytest.skip(f"GTK 3 or XApp is missing: {error}", allow_module_level=True)

from gi.repository import Gio, GLib, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from minttoys import BUS_NAME  # noqa: E402
from minttoys.api import AWAKE_INTERFACE, AWAKE_PATH  # noqa: E402
from minttoys.tray import app, view  # noqa: E402

NOW = datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Europe/Budapest"))
OFF = {"mode": "off", "keep_screen": False, "ends_at": 0}
ON = {"mode": "indefinite", "keep_screen": True, "ends_at": 0}
SIGNATURES = {"mode": "s", "keep_screen": "b", "ends_at": "x"}


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.state = OFF

    def awake_state(self) -> dict:
        return self.state

    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None:
        self.calls.append(("start", mode, minutes, until, keep_screen))

    def awake_stop(self) -> None:
        self.calls.append(("stop",))

    def awake_toggle(self) -> None:
        self.calls.append(("toggle",))

    def awake_set_keep_screen(self, keep_screen: bool) -> None:
        self.calls.append(("keep_screen", keep_screen))


class Harness:
    def __init__(self, tray: app.Tray, client: FakeClient, service: Gio.DBusConnection) -> None:
        self.tray = tray
        self.client = client
        self.service = service

    def item(self, label: str) -> Gtk.MenuItem:
        for child in self.tray.menu.get_children():
            if child.get_label() == label:
                return child
        raise LookupError(label)

    def status(self) -> str:
        return self.tray.menu.get_children()[0].get_label()


@pytest.fixture
def harness(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> Iterator[Harness]:
    service, client_bus = private_bus
    client = FakeClient()
    tray = app.Tray(client_bus, client, now=lambda: NOW)
    # The name watcher reports, once, that nobody owns the daemon's name yet.
    pump(lambda: False, seconds=0.2)
    yield Harness(tray, client, service)
    # Run on a desktop, the test icons would otherwise stay in the panel until pytest ends.
    tray.status_icon.set_visible(False)


def test_without_the_daemon_it_says_so_and_offers_nothing(harness: Harness) -> None:
    assert harness.status() == "MintToys is not running."
    assert harness.tray.status_icon.get_tooltip_text() == "MintToys is not running."
    assert not harness.item("Until turned off").get_sensitive()
    assert not harness.item("Keep the screen on").get_sensitive()


def test_shows_the_state(harness: Harness) -> None:
    harness.tray.update(ON)
    assert harness.tray.status_icon.get_icon_name().endswith(view.ICON_ON + ".svg") or (
        harness.tray.status_icon.get_icon_name() == view.ICON_ON
    )
    assert harness.status() == "Awake is on until you turn it off."
    assert harness.item("Turn off").get_sensitive()
    assert harness.item("Keep the screen on").get_active()
    assert harness.client.calls == []  # showing the check box ticked is not a click on it


def test_left_click_toggles(harness: Harness) -> None:
    harness.tray.update(OFF)
    harness.tray.status_icon.emit("activate", 1, 0)
    assert harness.client.calls == [("toggle",)]


def test_left_click_without_the_daemon_does_nothing(harness: Harness) -> None:
    harness.tray.status_icon.emit("activate", 1, 0)
    assert harness.client.calls == []


def test_the_menu_starts_the_modes_with_the_screen_setting(harness: Harness) -> None:
    harness.tray.update({**OFF, "keep_screen": True})
    harness.item("Until turned off").activate()
    harness.item("For 30 minutes").activate()
    harness.item("For 2 hours").activate()
    assert harness.client.calls == [
        ("start", "indefinite", 0, "", True),
        ("start", "duration", 30, "", True),
        ("start", "duration", 120, "", True),
    ]


def test_the_check_box_sets_the_screen_setting(harness: Harness) -> None:
    harness.tray.update(OFF)
    harness.item("Keep the screen on").set_active(True)
    assert harness.client.calls == [("keep_screen", True)]


def test_turn_off(harness: Harness) -> None:
    harness.tray.update(ON)
    harness.item("Turn off").activate()
    assert harness.client.calls == [("stop",)]


def test_follows_the_daemon_on_the_bus(harness: Harness, pump: Callable[..., bool]) -> None:
    harness.client.state = OFF
    harness.service.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (BUS_NAME, 4)),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    assert pump(lambda: harness.status() == "Awake is off.")

    on = {key: GLib.Variant(kind, ON[key]) for key, kind in SIGNATURES.items()}
    harness.service.emit_signal(
        None, AWAKE_PATH, AWAKE_INTERFACE, "StateChanged", GLib.Variant("(a{sv})", (on,))
    )
    assert pump(lambda: harness.status() == "Awake is on until you turn it off.")
