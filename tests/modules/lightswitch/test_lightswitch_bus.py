"""Light Switch on a D-Bus daemon of the test's own, with a stand-in for Cinnamon that keeps
the themes it is given, and a clock the test sets.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys.modules.base import Context
from minttoys.modules.lightswitch.module import INTERFACE, OBJECT_PATH, LightSwitch
from minttoys.modules.lightswitch.schedule import NightLight
from minttoys.modules.lightswitch.styles import Look, Style, Variant

BUDAPEST = ZoneInfo("Europe/Budapest")


def look(gtk: str, cinnamon: str) -> Look:
    return Look(gtk, "Mint-Y-Sand", cinnamon, "Bibata-Modern-Classic")


MIXED = look("Mint-Y-Aqua", "Mint-Y-Dark-Aqua")
DARK = look("Mint-Y-Dark-Aqua", "Mint-Y-Dark-Aqua")
LIGHT = look("Mint-Y-Aqua", "Mint-Y-Aqua")
MINT_Y = Style(
    "Mint-Y",
    {
        "mixed": [Variant("Aqua", MIXED)],
        "dark": [Variant("Aqua", DARK)],
        "light": [Variant("Aqua", LIGHT)],
    },
)
MODE_OF = {MIXED: "mixed", DARK: "dark", LIGHT: "light"}
TIMES = {"schedule": "times", "dark_from": "20:00", "dark_to": "06:00"}
# Night Light before it knows the location: its set hours.
NO_LOCATION = NightLight("manual", 20.0, 6.0, 91.0, 181.0)


@dataclass
class FakeDesktop:
    current: Look = MIXED
    writes: list[str] = field(default_factory=list)
    night: NightLight = NO_LOCATION

    def look(self) -> Look:
        return self.current

    def styles(self) -> list[Style]:
        return [MINT_Y]

    def write(self, mode: str, new: Look) -> None:
        assert MODE_OF[new] == mode
        self.writes.append(mode)
        self.current = new

    def night_light(self) -> NightLight:
        return self.night


@dataclass
class Harness:
    module: LightSwitch
    desktop: FakeDesktop
    service: Gio.DBusConnection
    client: Gio.DBusConnection
    pump: Callable[..., bool]
    now: datetime = datetime(2026, 10, 9, 12, 0, tzinfo=BUDAPEST)
    config: dict = field(default_factory=dict)
    saved: list[dict] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)

    def set_settings(self, changes: dict) -> None:
        """What the daemon does for Context.set_settings: check, save, hand back."""
        updated = LightSwitch.check_settings(LightSwitch.read_settings(self.config), changes)
        saved = {key: updated[key] for key in changes}
        self.config.update(saved)
        self.saved.append(saved)
        self.module.apply_settings(updated)

    def enable(self, settings: dict | None = None) -> None:
        self.config = dict(settings if settings is not None else TIMES)
        context = Context(self.service, LightSwitch.read_settings(self.config), self.set_settings)
        self.module.enable(context)

    def at(self, hour: int, minute: int = 0) -> None:
        """Moves the clock and lets the module look at it, as its timer would."""
        self.now = self.now.replace(hour=hour, minute=minute)
        self.module._follow_schedule()

    def call(self, method: str) -> Any:  # noqa: ANN401
        results: list = []

        def done(connection: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                results.append(connection.call_finish(result).unpack())
            except GLib.Error as error:
                results.append(error)

        self.client.call(
            self.service.get_unique_name(),
            OBJECT_PATH,
            INTERFACE,
            method,
            None,
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
            done,
        )
        assert self.pump(lambda: results), f"{method} got no answer"
        return results[0]

    def state(self) -> dict:
        (state,) = self.call("GetState")
        return state


@pytest.fixture
def harness(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> Iterator[Harness]:
    service, client = private_bus
    desktop = FakeDesktop()
    shown: Harness
    module = LightSwitch(make_desktop=lambda: desktop, now=lambda: shown.now)
    shown = Harness(module, desktop, service, client, pump)
    client.signal_subscribe(
        service.get_unique_name(),
        INTERFACE,
        "StateChanged",
        OBJECT_PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *arguments: shown.signals.append(arguments[5].unpack()[0]),
    )
    yield shown
    module.disable()


def test_on_in_the_day_changes_nothing(harness: Harness) -> None:
    harness.enable()
    assert harness.desktop.writes == []
    assert harness.state() == {
        "dark": False,
        "dark_from": "20:00",
        "dark_to": "06:00",
        "by_sun": False,
        "problem": "",
    }


def test_on_at_night_goes_dark(harness: Harness) -> None:
    harness.now = harness.now.replace(hour=21)
    harness.enable()
    assert harness.desktop.writes == ["dark"]
    assert harness.state()["dark"] is True


def test_nightfall_and_daybreak(harness: Harness) -> None:
    harness.enable()
    harness.at(19, 59)
    harness.at(20, 0)
    assert harness.desktop.writes == ["dark"]
    harness.at(23, 0)
    harness.at(6, 0)
    assert harness.desktop.writes == ["dark", "mixed"]


def test_whoever_uses_light_keeps_light(harness: Harness) -> None:
    harness.desktop.current = LIGHT
    harness.enable()
    assert harness.saved == [{"day_mode": "light"}]
    harness.at(20, 0)
    harness.at(6, 0)
    assert harness.desktop.writes == ["dark", "light"]


def test_a_chosen_day_mode_is_kept(harness: Harness) -> None:
    harness.desktop.current = LIGHT
    harness.enable({**TIMES, "day_mode": "mixed"})
    assert harness.saved == []
    harness.at(20, 0)
    harness.at(6, 0)
    assert harness.desktop.writes == ["dark", "mixed"]


def test_a_desktop_already_dark_at_nightfall_is_left_alone(harness: Harness) -> None:
    harness.enable()
    harness.desktop.current = DARK
    harness.at(20, 0)
    assert harness.desktop.writes == []


def test_a_light_desktop_at_daybreak_is_left_alone(harness: Harness) -> None:
    harness.now = harness.now.replace(hour=21)
    harness.enable()
    harness.desktop.current = LIGHT  # the user went light in the night
    harness.at(6, 0)
    assert harness.desktop.writes == ["dark"]


def test_toggle_holds_until_the_schedule_changes(harness: Harness) -> None:
    harness.enable()
    assert harness.call("Toggle") == ()
    assert harness.desktop.writes == ["dark"]
    harness.at(12, 1)
    harness.at(20, 0)  # night comes, and it is dark already
    assert harness.desktop.writes == ["dark"]
    harness.at(6, 0)
    assert harness.desktop.writes == ["dark", "mixed"]


def test_toggle_back(harness: Harness) -> None:
    harness.enable()
    harness.call("Toggle")
    harness.call("Toggle")
    assert harness.desktop.writes == ["dark", "mixed"]


def test_custom_themes_are_left_alone(harness: Harness) -> None:
    harness.desktop.current = Look("Arc", "Papirus", "Arc", "DMZ")
    harness.now = harness.now.replace(hour=21)
    harness.enable()
    harness.call("Toggle")
    assert harness.desktop.writes == []
    assert harness.state()["problem"] == "custom"


def test_night_lights_schedule_with_a_location_follows_the_sun(harness: Harness) -> None:
    harness.desktop.night = NightLight("auto", 20.0, 6.0, 47.3, 19.05)
    harness.enable({"schedule": "night-light"})
    state = harness.state()
    assert state["by_sun"] is True
    assert state["dark_from"] == "18:09"
    assert state["dark_to"] == "06:53"


def test_changed_settings_take_effect_at_once(harness: Harness) -> None:
    harness.enable()
    harness.set_settings({"dark_from": "11:00"})
    assert harness.desktop.writes == ["dark"]
    assert harness.state()["dark_from"] == "11:00"


def test_every_change_is_signalled(harness: Harness) -> None:
    harness.enable()
    harness.call("Toggle")
    assert harness.pump(lambda: harness.signals and harness.signals[-1]["dark"] is True)


def test_switching_off_leaves_the_desktop_and_the_bus(harness: Harness) -> None:
    harness.now = harness.now.replace(hour=21)
    harness.enable()
    harness.module.disable()
    assert harness.desktop.current == DARK
    assert isinstance(harness.call("GetState"), GLib.Error)
    harness.module.disable()  # a second time does no harm
