"""Session tests: they talk to the real session manager, so they run inside a desktop
session and are skipped anywhere else, CI included. Each inhibitor they take lasts a
fraction of a second.
"""

import time
from collections.abc import Iterator

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys.modules.awake.inhibit import (
    BUS_NAME,
    INTERFACE,
    OBJECT_PATH,
    Flags,
    Inhibitor,
)

APP_ID = "minttoys-test"


def call(
    connection: Gio.DBusConnection, method: str, arguments: GLib.Variant | None, reply: str
) -> tuple:
    result = connection.call_sync(
        BUS_NAME,
        OBJECT_PATH,
        INTERFACE,
        method,
        arguments,
        GLib.VariantType(reply),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    return result.unpack()


def inhibitors(connection: Gio.DBusConnection) -> set[str]:
    (paths,) = call(connection, "GetInhibitors", None, "(ao)")
    return set(paths)


def inhibited(connection: Gio.DBusConnection, flags: Flags) -> bool:
    (answer,) = call(connection, "IsInhibited", GLib.Variant("(u)", (int(flags),)), "(b)")
    return answer


@pytest.fixture
def bus() -> Gio.DBusConnection:
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION)
    except GLib.Error as error:
        pytest.skip(f"no session bus: {error.message}")
    (owned,) = connection.call_sync(
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
    if not owned:
        pytest.skip(f"nothing owns {BUS_NAME} on the session bus")
    return connection


@pytest.fixture
def inhibitor(bus: Gio.DBusConnection) -> Iterator[Inhibitor]:
    held = Inhibitor(bus, APP_ID)
    yield held
    held.release()


def test_hold_adds_one_inhibitor_and_release_removes_it(
    bus: Gio.DBusConnection, inhibitor: Inhibitor
) -> None:
    before = inhibitors(bus)
    inhibitor.hold(Flags.SUSPEND | Flags.IDLE, "MintToys session test")
    assert inhibitor.held
    assert len(inhibitors(bus) - before) == 1
    assert inhibited(bus, Flags.SUSPEND)
    assert inhibited(bus, Flags.IDLE)
    inhibitor.release()
    assert not inhibitor.held
    assert inhibitors(bus) == before


def test_suspend_only_leaves_idle_alone(bus: Gio.DBusConnection, inhibitor: Inhibitor) -> None:
    if inhibited(bus, Flags.IDLE):
        pytest.skip("another application is holding off idle right now")
    inhibitor.hold(Flags.SUSPEND, "MintToys session test")
    assert inhibited(bus, Flags.SUSPEND)
    assert not inhibited(bus, Flags.IDLE)


def test_a_new_hold_replaces_the_old_one(bus: Gio.DBusConnection, inhibitor: Inhibitor) -> None:
    if inhibited(bus, Flags.IDLE):
        pytest.skip("another application is holding off idle right now")
    before = inhibitors(bus)
    inhibitor.hold(Flags.SUSPEND | Flags.IDLE, "MintToys session test")
    inhibitor.hold(Flags.SUSPEND, "MintToys session test")
    assert len(inhibitors(bus) - before) == 1
    assert not inhibited(bus, Flags.IDLE)


def test_release_without_a_hold_does_nothing(inhibitor: Inhibitor) -> None:
    inhibitor.release()
    assert not inhibitor.held


def test_the_inhibitor_goes_with_its_connection(bus: Gio.DBusConnection) -> None:
    # A connection of its own, closed the way the bus sees a daemon that crashed or was
    # killed: its name disappears. The session manager has to notice within 5 seconds.
    address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
    own = Gio.DBusConnection.new_for_address_sync(
        address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None,
        None,
    )
    before = inhibitors(bus)
    Inhibitor(own, APP_ID).hold(Flags.SUSPEND | Flags.IDLE, "MintToys session test")
    new = inhibitors(bus) - before
    assert len(new) == 1
    (ours,) = new
    own.close_sync(None)

    deadline = time.monotonic() + 5
    while ours in inhibitors(bus) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert ours not in inhibitors(bus)
