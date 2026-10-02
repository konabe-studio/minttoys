"""Session tests: they start the real daemon on the session bus, so they run inside a desktop
session and are skipped anywhere else, CI included, and also while MintToys is running.
"""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys import BUS_NAME

CHECKOUT = Path(__file__).parents[2]


def owned(bus: Gio.DBusConnection) -> bool:
    (answer,) = bus.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameHasOwner",
        GLib.Variant("(s)", (BUS_NAME,)),
        GLib.VariantType("(b)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    ).unpack()
    return answer


def soon(condition: Callable[[], bool], seconds: float = 5) -> bool:
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


@pytest.fixture
def bus() -> Gio.DBusConnection:
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION)
    except GLib.Error as error:
        pytest.skip(f"no session bus: {error.message}")
    if owned(connection):
        pytest.skip(f"{BUS_NAME} is taken, MintToys is running in this session")
    return connection


@pytest.fixture
def start(tmp_path: Path) -> Iterator[Callable[[], subprocess.Popen[str]]]:
    started: list[subprocess.Popen[str]] = []

    def launch() -> subprocess.Popen[str]:
        daemon = subprocess.Popen(
            [sys.executable, "-m", "minttoys.daemon"],
            cwd=CHECKOUT,
            env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path)},
            stderr=subprocess.PIPE,
            text=True,
        )
        started.append(daemon)
        return daemon

    yield launch
    for daemon in started:
        if daemon.poll() is None:
            daemon.kill()
        daemon.wait()
        if daemon.stderr:
            daemon.stderr.close()


def test_owns_the_name_and_lets_go_of_it_on_sigterm(
    bus: Gio.DBusConnection, start: Callable[[], subprocess.Popen[str]]
) -> None:
    daemon = start()
    assert soon(lambda: owned(bus)), "the daemon never took its bus name"
    daemon.send_signal(signal.SIGTERM)
    assert daemon.wait(timeout=5) == 0
    assert soon(lambda: not owned(bus))
    assert "stopped" in daemon.communicate()[1]


def test_a_second_daemon_exits_and_leaves_the_first_alone(
    bus: Gio.DBusConnection, start: Callable[[], subprocess.Popen[str]]
) -> None:
    first = start()
    assert soon(lambda: owned(bus)), "the daemon never took its bus name"
    second = start()
    assert second.wait(timeout=5) == 1
    assert "already running" in second.communicate()[1]
    assert first.poll() is None
    assert owned(bus)
