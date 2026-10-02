import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

# A session bus with no service directories, so that nothing on it can be started on
# demand: a call to a name nobody owns fails at once, instead of launching, say, a real
# notification server onto the desktop.
BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:dir={directory}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


@pytest.fixture
def private_bus(tmp_path: Path) -> Iterator[tuple[Any, Any]]:
    """Two connections to a D-Bus daemon of the test's own, one for the service under test
    and one for its client. Nothing reaches the desktop's own buses, so no inhibitor is
    taken and no bubble shows. Skipped without PyGObject or dbus-daemon.
    """
    gio = pytest.importorskip("gi.repository.Gio", reason="PyGObject is not installed")
    if shutil.which("dbus-daemon") is None:
        pytest.skip("dbus-daemon is not installed")
    config = tmp_path / "bus.conf"
    config.write_text(BUS_CONFIG.format(directory=tmp_path), encoding="utf-8")
    daemon = subprocess.Popen(
        ["dbus-daemon", f"--config-file={config}", "--nofork", "--print-address"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert daemon.stdout is not None
    try:
        address = daemon.stdout.readline().strip()
        flags = (
            gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        )
        service, client = (
            gio.DBusConnection.new_for_address_sync(address, flags, None, None) for _ in range(2)
        )
        yield service, client
        service.close_sync(None)
        client.close_sync(None)
    finally:
        daemon.terminate()
        daemon.wait()
        daemon.stdout.close()


@pytest.fixture
def pump() -> Callable[..., bool]:
    """Runs the main loop until `condition` holds, for at most `seconds`.

    A D-Bus service in the test's own process answers only while the loop runs, so a test
    calls it asynchronously and pumps until the answer is in.
    """
    glib = pytest.importorskip("gi.repository.GLib", reason="PyGObject is not installed")

    def run(condition: Callable[[], object], seconds: float = 5) -> bool:
        context = glib.MainContext.default()
        deadline = time.monotonic() + seconds
        while not condition():
            if time.monotonic() > deadline:
                return False
            if not context.iteration(False):
                time.sleep(0.002)
        return True

    return run
