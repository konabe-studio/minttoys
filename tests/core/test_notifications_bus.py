"""Against a fake notification server on a D-Bus daemon of the test's own."""

from collections.abc import Callable

import pytest

pytest.importorskip("gi", reason="PyGObject is not installed")

from gi.repository import Gio, GLib

from minttoys import APP_ID
from minttoys.core import notifications

SERVER_XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg type="s" direction="in"/><arg type="u" direction="in"/>
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="s" direction="in"/><arg type="as" direction="in"/>
      <arg type="a{sv}" direction="in"/><arg type="i" direction="in"/>
      <arg type="u" direction="out"/>
    </method>
  </interface>
</node>
"""


def serve(connection: Gio.DBusConnection, received: list[tuple]) -> None:
    def on_call(
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        received.append(parameters.unpack())
        invocation.return_value(GLib.Variant("(u)", (1,)))

    node = Gio.DBusNodeInfo.new_for_xml(SERVER_XML)
    connection.register_object(notifications.OBJECT_PATH, node.interfaces[0], on_call, None, None)
    connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (notifications.BUS_NAME, 4)),  # 4: do not queue
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )


def test_sends_summary_body_and_desktop_entry(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> None:
    server, client = private_bus
    received: list[tuple] = []
    serve(server, received)
    notifications.send(client, "Awake is off", "The time is up.")
    assert pump(lambda: received)
    app_name, _, _, summary, body, _, hints, _ = received[0]
    assert (app_name, summary, body) == ("MintToys", "Awake is off", "The time is up.")
    assert hints == {"desktop-entry": APP_ID}


def test_no_server_is_logged_not_raised(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection],
    pump: Callable[..., bool],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, client = private_bus
    notifications.send(client, "Awake is off", "The time is up.")
    assert pump(lambda: "could not show a notification" in caplog.text)
