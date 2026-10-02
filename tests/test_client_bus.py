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

from minttoys import BUS_NAME
from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused
from minttoys.client import Client
from minttoys.daemon.host import ModuleHost
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
    service = DaemonService(
        ModuleHost({"awake": lambda: QuietAwake, "broken": broken_import}), config_path
    )
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
