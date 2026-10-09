"""The client against the daemon's object and Awake, on a D-Bus daemon of the test's own.

The client's calls are synchronous, and the services answer only while the main loop runs,
so each call is made from a thread of its own while the test pumps the loop.
"""

import json
import threading
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import TypeVar
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys import BUS_NAME, OBJECT_PATH
from minttoys.api import DAEMON_INTERFACE, ModuleInfo, ModuleOff, NotRunning, Refused
from minttoys.client import Client
from minttoys.daemon.service import DaemonService
from minttoys.modules.awake.inhibit import Flags
from minttoys.modules.awake.module import Awake
from minttoys.modules.base import Module

T = TypeVar("T")
NOW = datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Europe/Budapest"))


class NoInhibitor:
    def hold(self, flags: Flags, reason: str) -> None:
        pass

    def release(self) -> None:
        pass


class QuietAwake(Awake):
    """Awake as the daemon builds it, with no arguments, but with nothing real behind it."""

    def __init__(self) -> None:
        super().__init__(
            make_inhibitor=lambda bus: NoInhibitor(),
            notify=lambda bus, summary, body: None,
            now=lambda: NOW,
        )


def broken_import() -> type[Module]:
    raise ImportError("no typelib")


def take_name(connection: Gio.DBusConnection) -> None:
    connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (BUS_NAME, 4)),  # 4: do not queue
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )


class Remote:
    """The client, with every call made off the main loop."""

    def __init__(self, client: Client, pump: Callable[..., bool]) -> None:
        self._client = client
        self._pump = pump

    def __call__(self, call: Callable[[Client], T]) -> T:
        outcome: list = []

        def work() -> None:
            try:
                outcome.append((True, call(self._client)))
            except Exception as error:
                outcome.append((False, error))

        thread = threading.Thread(target=work)
        thread.start()
        assert self._pump(lambda: outcome), "the call got no answer"
        thread.join()
        succeeded, value = outcome[0]
        if not succeeded:
            raise value
        return value


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "minttoys" / "config.json"


@pytest.fixture
def remote(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    pump: Callable[..., bool],
    config_path: Path,
) -> Iterator[Remote]:
    service_bus, client_bus = private_bus
    take_name(service_bus)
    service = DaemonService({"awake": lambda: QuietAwake, "broken": broken_import}, config_path)
    service.start(service_bus)
    yield Remote(Client(client_bus), pump)
    service.stop()


def test_modules(remote: Remote) -> None:
    awake, broken = remote(lambda client: client.modules())
    assert (awake.id, awake.name, awake.state, awake.error) == ("awake", "Awake", "on", "")
    assert broken == ModuleInfo("broken", "broken", "", "failed", "ImportError: no typelib")


def test_switching_awake_off_saves_it_and_takes_it_off_the_bus(
    remote: Remote, config_path: Path
) -> None:
    remote(lambda client: client.set_module_enabled("awake", False))
    assert remote(lambda client: client.modules())[0].state == "off"
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "modules": {"awake": {"enabled": False}}
    }
    with pytest.raises(ModuleOff):
        remote(lambda client: client.awake_state())


def test_switching_awake_back_on(remote: Remote) -> None:
    remote(lambda client: client.set_module_enabled("awake", False))
    remote(lambda client: client.set_module_enabled("awake", True))
    assert remote(lambda client: client.awake_state())["mode"] == "off"


def test_the_screen_setting_is_saved_next_to_the_rest(remote: Remote, config_path: Path) -> None:
    remote(lambda client: client.set_module_enabled("awake", True))
    remote(lambda client: client.awake_set_keep_screen(True))
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "modules": {"awake": {"enabled": True, "keep_screen": True}}
    }
    assert remote(lambda client: client.awake_state())["keep_screen"] is True


def test_the_screen_setting_survives_switching_awake_off_and_on(remote: Remote) -> None:
    remote(lambda client: client.awake_set_keep_screen(True))
    remote(lambda client: client.set_module_enabled("awake", False))
    remote(lambda client: client.set_module_enabled("awake", True))
    assert remote(lambda client: client.awake_state())["keep_screen"] is True


def test_toggle(remote: Remote) -> None:
    remote(lambda client: client.awake_toggle())
    assert remote(lambda client: client.awake_state())["mode"] == "indefinite"
    remote(lambda client: client.awake_toggle())
    assert remote(lambda client: client.awake_state())["mode"] == "off"


DEFAULT_SETTINGS = {
    "default_mode": "indefinite",
    "default_minutes": 60,
    "default_until": "18:00",
    "keep_screen": False,
}


def test_module_settings(remote: Remote) -> None:
    assert remote(lambda client: client.module_settings("awake")) == DEFAULT_SETTINGS


def test_settings_are_there_while_the_module_is_off(remote: Remote) -> None:
    remote(lambda client: client.set_module_enabled("awake", False))
    remote(lambda client: client.set_module_settings("awake", {"default_minutes": 45}))
    settings = remote(lambda client: client.module_settings("awake"))
    assert settings == {**DEFAULT_SETTINGS, "default_minutes": 45}


def test_set_module_settings_saves_only_what_changed(remote: Remote, config_path: Path) -> None:
    changes = {"default_mode": "duration", "default_minutes": 45}
    remote(lambda client: client.set_module_settings("awake", changes))
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"modules": {"awake": changes}}


def test_set_module_settings_reach_the_running_module(remote: Remote) -> None:
    remote(lambda client: client.set_module_settings("awake", {"default_mode": "until"}))
    remote(lambda client: client.awake_toggle())
    assert remote(lambda client: client.awake_state())["mode"] == "until"


def test_a_bad_setting_is_refused_and_changes_nothing(remote: Remote, config_path: Path) -> None:
    with pytest.raises(Refused, match="default_minutes"):
        remote(
            lambda client: client.set_module_settings(
                "awake", {"keep_screen": True, "default_minutes": 0}
            )
        )
    assert not config_path.exists()
    assert remote(lambda client: client.module_settings("awake")) == DEFAULT_SETTINGS


def test_a_setting_the_module_does_not_have_is_refused_before_sending(remote: Remote) -> None:
    with pytest.raises(Refused, match="colour"):
        remote(lambda client: client.set_module_settings("awake", {"colour": "green"}))


def test_settings_of_an_unknown_module_are_refused(remote: Remote) -> None:
    with pytest.raises(Refused, match=r"^unknown module: 'nope'$"):
        remote(lambda client: client.module_settings("nope"))


def test_settings_of_a_module_that_did_not_load_are_refused(remote: Remote) -> None:
    with pytest.raises(Refused, match="could not be loaded"):
        remote(lambda client: client.module_settings("broken"))


def subscribe(bus: Gio.DBusConnection, signal: str, into: list) -> None:
    bus.signal_subscribe(
        None,
        DAEMON_INTERFACE,
        signal,
        OBJECT_PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *arguments: into.append(arguments[5].unpack()),
    )


def test_a_settings_change_is_signalled_with_every_setting(
    remote: Remote,
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    pump: Callable[..., bool],
) -> None:
    heard: list = []
    subscribe(private_bus[1], "ModuleSettingsChanged", heard)
    remote(lambda client: client.awake_set_keep_screen(True))
    assert pump(lambda: heard)
    assert heard == [("awake", {**DEFAULT_SETTINGS, "keep_screen": True})]


def test_switching_a_module_is_signalled_with_the_new_list(
    remote: Remote,
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    pump: Callable[..., bool],
) -> None:
    heard: list = []
    subscribe(private_bus[1], "ModulesChanged", heard)
    remote(lambda client: client.set_module_enabled("awake", False))
    assert pump(lambda: heard)
    ((rows,),) = heard
    assert rows[0][:4] == ("awake", "Awake", rows[0][2], "off")


def test_an_unknown_module_is_refused_with_the_reason(remote: Remote) -> None:
    with pytest.raises(Refused, match=r"^unknown module: 'nope'$"):
        remote(lambda client: client.set_module_enabled("nope", True))


def test_awake_start_and_stop(remote: Remote) -> None:
    remote(lambda client: client.awake_start("indefinite", 0, "", True))
    assert remote(lambda client: client.awake_state()) == {
        "mode": "indefinite",
        "keep_screen": True,
        "ends_at": 0,
    }
    remote(lambda client: client.awake_stop())
    assert remote(lambda client: client.awake_state())["mode"] == "off"


def test_a_bad_start_is_refused_with_the_reason(remote: Remote) -> None:
    with pytest.raises(Refused, match=r"^unknown mode: 'sometimes'$"):
        remote(lambda client: client.awake_start("sometimes", 0, "", False))


def test_nobody_owning_the_name_is_not_running(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> None:
    _, client_bus = private_bus
    with pytest.raises(NotRunning):
        Remote(Client(client_bus), pump)(lambda client: client.modules())
