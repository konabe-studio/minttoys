"""Awake's D-Bus interface, on a D-Bus daemon of the test's own, with a stand-in for the
inhibitor, the notification and the clock. The real inhibitor has its own session tests.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys.modules.awake.inhibit import Flags
from minttoys.modules.awake.module import INTERFACE, OBJECT_PATH, Awake
from minttoys.modules.awake.state import Mode
from minttoys.modules.base import Context

BUDAPEST = ZoneInfo("Europe/Budapest")
OFF = {"mode": "off", "keep_screen": False, "ends_at": 0}


class FakeInhibitor:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail = False

    def hold(self, flags: Flags, reason: str) -> None:
        if self.fail:
            raise RuntimeError("no session manager")
        self.calls.append(("hold", flags))

    def release(self) -> None:
        self.calls.append(("release",))


@dataclass
class Harness:
    module: Awake
    service: Gio.DBusConnection
    client: Gio.DBusConnection
    pump: Callable[..., bool]
    inhibitor: FakeInhibitor
    now: datetime
    notices: list[tuple[str, str]] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    # Awake's section of the config, and every change saved to it.
    config: dict = field(default_factory=dict)
    saved: list[dict] = field(default_factory=list)
    save_fails: bool = False

    def set_settings(self, changes: dict) -> None:
        """What the daemon does for Context.set_settings: check, save, hand back."""
        updated = Awake.check_settings(Awake.read_settings(self.config), changes)
        if self.save_fails:
            raise OSError("disk full")
        saved = {key: updated[key] for key in changes}
        self.config.update(saved)
        self.saved.append(saved)
        self.module.apply_settings(updated)

    def enable(self) -> None:
        self.module.enable(
            Context(self.service, Awake.read_settings(self.config), self.set_settings)
        )

    def reenable(self, settings: dict) -> None:
        """Switches the module off and on again, as the daemon would with these settings."""
        self.module.disable()
        self.config = dict(settings)
        self.enable()

    def call(self, method: str, *arguments: Any) -> Any:  # noqa: ANN401
        """Calls a method over the bus; returns its result, or the GLib.Error it raised."""
        signature = {"Start": "(susb)", "SetKeepScreen": "(b)"}.get(method)
        parameters = GLib.Variant(signature, arguments) if signature else None
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
            parameters,
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
            done,
        )
        assert self.pump(lambda: results), f"{method} got no answer"
        return results[0]

    def state(self) -> dict:
        (described,) = self.call("GetState")
        return described


def remote_error(result: object) -> str | None:
    return Gio.DBusError.get_remote_error(result) if isinstance(result, GLib.Error) else None


@pytest.fixture
def awake(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> Iterator[Harness]:
    service, client = private_bus
    inhibitor = FakeInhibitor()
    harness: Harness

    module = Awake(
        make_inhibitor=lambda bus: inhibitor,
        notify=lambda bus, summary, body: harness.notices.append((summary, body)),
        now=lambda: harness.now,
    )
    module.check_every = timedelta(milliseconds=20)
    harness = Harness(
        module, service, client, pump, inhibitor, datetime(2026, 6, 1, 10, 0, tzinfo=BUDAPEST)
    )
    client.signal_subscribe(
        service.get_unique_name(),
        INTERFACE,
        "StateChanged",
        OBJECT_PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: harness.signals.append(args[5].unpack()[0]),
    )
    harness.enable()
    yield harness
    module.disable()


def unix(*fields: int) -> int:
    return int(datetime(*fields, tzinfo=UTC).timestamp())


def test_starts_off(awake: Harness) -> None:
    assert awake.state() == OFF
    assert awake.inhibitor.calls == []


def test_indefinite_with_the_screen_on(awake: Harness) -> None:
    assert awake.call("Start", "indefinite", 0, "", True) == ()
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND | Flags.IDLE)]
    assert awake.state() == {"mode": "indefinite", "keep_screen": True, "ends_at": 0}


def test_without_the_screen_only_suspend_is_held_off(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND)]


def test_duration(awake: Harness) -> None:
    awake.call("Start", "duration", 90, "", False)
    assert awake.state() == {
        "mode": "duration",
        "keep_screen": False,
        "ends_at": unix(2026, 6, 1, 9, 30),
    }


def test_until(awake: Harness) -> None:
    awake.call("Start", "until", 0, "18:00", True)
    assert awake.state() == {
        "mode": "until",
        "keep_screen": True,
        "ends_at": unix(2026, 6, 1, 16, 0),
    }


def test_every_change_is_signalled(awake: Harness) -> None:
    awake.call("Start", "duration", 30, "", True)
    awake.call("Stop")
    assert awake.pump(lambda: len(awake.signals) == 2)
    assert awake.signals[0] == {
        "mode": "duration",
        "keep_screen": True,
        "ends_at": unix(2026, 6, 1, 8, 30),
    }
    assert awake.signals[1] == OFF


def test_a_new_start_replaces_the_running_one(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", True)
    awake.call("Start", "duration", 30, "", False)
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND | Flags.IDLE), ("hold", Flags.SUSPEND)]
    assert awake.state()["mode"] == "duration"


def test_stop_releases(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    assert awake.call("Stop") == ()
    assert awake.inhibitor.calls[-1] == ("release",)
    assert awake.state() == OFF


def test_stop_while_off_does_nothing(awake: Harness) -> None:
    awake.call("Stop")
    assert awake.inhibitor.calls == []
    assert not awake.pump(lambda: awake.signals, seconds=0.1)


def test_start_off_is_stop(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    awake.call("Start", "off", 0, "", False)
    assert awake.state() == OFF


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (("sometimes", 0, "", False), "unknown mode"),
        (("duration", 0, "", False), "positive"),
        (("until", 0, "25:00", False), "not a time of day"),
    ],
)
def test_bad_arguments_are_invalid_args(awake: Harness, arguments: tuple, message: str) -> None:
    result = awake.call("Start", *arguments)
    assert remote_error(result) == "org.freedesktop.DBus.Error.InvalidArgs"
    assert message in result.message
    assert awake.inhibitor.calls == []
    assert awake.state() == OFF


def test_an_inhibitor_that_cannot_be_taken_is_failed_and_changes_nothing(awake: Harness) -> None:
    awake.inhibitor.fail = True
    result = awake.call("Start", "indefinite", 0, "", False)
    assert remote_error(result) == "org.freedesktop.DBus.Error.Failed"
    assert awake.state() == OFF


def test_a_timed_mode_ends_by_itself_with_a_notification(awake: Harness) -> None:
    awake.call("Start", "duration", 1, "", False)
    awake.now += timedelta(minutes=1)
    assert awake.pump(lambda: awake.module.state.mode is Mode.OFF)
    assert awake.inhibitor.calls[-1] == ("release",)
    assert len(awake.notices) == 1
    assert awake.pump(lambda: awake.signals and awake.signals[-1] == OFF)


def test_a_timed_mode_does_not_end_early(awake: Harness) -> None:
    awake.call("Start", "duration", 1, "", False)
    awake.now += timedelta(seconds=59)
    assert not awake.pump(lambda: awake.module.state.mode is Mode.OFF, seconds=0.2)
    assert awake.notices == []


def test_a_stopped_timer_does_not_fire(awake: Harness) -> None:
    awake.call("Start", "duration", 1, "", False)
    awake.call("Stop")
    awake.now += timedelta(hours=1)
    assert not awake.pump(lambda: awake.notices, seconds=0.2)


def test_indefinite_never_ends_by_itself(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    awake.now += timedelta(days=3)
    assert not awake.pump(lambda: awake.module.state.mode is Mode.OFF, seconds=0.2)


def test_disable_releases_and_leaves_the_bus(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", True)
    awake.module.disable()
    assert awake.inhibitor.calls[-1] == ("release",)
    assert remote_error(awake.call("GetState")) is not None
    awake.module.disable()  # a second time does no harm


def test_toggle_starts_as_set_and_stops(awake: Harness) -> None:
    awake.call("Toggle")
    assert awake.state() == {"mode": "indefinite", "keep_screen": False, "ends_at": 0}
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND)]
    awake.call("Toggle")
    assert awake.state() == OFF


def test_toggle_follows_the_settings(awake: Harness) -> None:
    awake.reenable({"default_mode": "duration", "default_minutes": 30, "keep_screen": True})
    awake.call("Toggle")
    assert awake.state() == {
        "mode": "duration",
        "keep_screen": True,
        "ends_at": unix(2026, 6, 1, 8, 30),
    }
    assert awake.inhibitor.calls[-1] == ("hold", Flags.SUSPEND | Flags.IDLE)


def test_while_off_the_state_carries_the_screen_setting(awake: Harness) -> None:
    awake.reenable({"keep_screen": True})
    assert awake.state() == {"mode": "off", "keep_screen": True, "ends_at": 0}


def test_set_keep_screen_while_off_saves_it_and_says_so(awake: Harness) -> None:
    assert awake.call("SetKeepScreen", True) == ()
    assert awake.saved == [{"keep_screen": True}]
    assert awake.state()["keep_screen"] is True
    assert awake.inhibitor.calls == []
    assert awake.pump(lambda: awake.signals and awake.signals[-1]["keep_screen"] is True)


def test_set_keep_screen_while_on_applies_it_and_keeps_the_end(awake: Harness) -> None:
    awake.call("Start", "duration", 90, "", False)
    awake.call("SetKeepScreen", True)
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND), ("hold", Flags.SUSPEND | Flags.IDLE)]
    assert awake.state() == {
        "mode": "duration",
        "keep_screen": True,
        "ends_at": unix(2026, 6, 1, 9, 30),
    }


def test_a_screen_setting_that_cannot_be_saved_changes_nothing(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    awake.save_fails = True
    result = awake.call("SetKeepScreen", True)
    assert remote_error(result) == "org.freedesktop.DBus.Error.Failed"
    assert awake.state()["keep_screen"] is False
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND)]


def test_settings_from_a_config_edited_by_hand_fall_back_to_their_defaults() -> None:
    assert Awake.read_settings({"default_minutes": "lots", "keep_screen": True}) == {
        "default_mode": "indefinite",
        "default_minutes": 60,
        "default_until": "18:00",
        "keep_screen": True,
    }


def test_checked_settings_come_back_whole_and_normalized() -> None:
    settings = Awake.read_settings({})
    updated = Awake.check_settings(settings, {"default_until": "8:05"})
    assert updated == {**settings, "default_until": "08:05"}


def test_a_bad_setting_is_refused_whole() -> None:
    with pytest.raises(ValueError, match="default_minutes"):
        Awake.check_settings(Awake.read_settings({}), {"keep_screen": True, "default_minutes": 0})


def test_apply_settings_while_off_changes_what_toggle_starts(awake: Harness) -> None:
    awake.set_settings({"default_mode": "until", "default_until": "18:00"})
    awake.call("Toggle")
    assert awake.state() == {
        "mode": "until",
        "keep_screen": False,
        "ends_at": unix(2026, 6, 1, 16, 0),
    }


def test_apply_settings_while_on_takes_the_screen_at_once(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    awake.set_settings({"keep_screen": True})
    assert awake.inhibitor.calls[-1] == ("hold", Flags.SUSPEND | Flags.IDLE)
    assert awake.state()["keep_screen"] is True


def test_settings_other_than_the_screen_leave_a_running_mode_alone(awake: Harness) -> None:
    awake.call("Start", "indefinite", 0, "", False)
    awake.set_settings({"default_minutes": 30})
    assert awake.inhibitor.calls == [("hold", Flags.SUSPEND)]
    assert not awake.pump(lambda: len(awake.signals) > 1, seconds=0.1)
