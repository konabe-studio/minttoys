"""Always on Top, as the daemon runs it.

Pinning is Muffin's own: its toggle-above action, which has no keys by default. Always on
Top gives it Super+Ctrl+T when it comes on, unless those keys are in use or the action has
keys of the user's already, and takes them back only when the user switches it, or its
shortcut, off; not at the end of a session.

The frame around a pinned window is drawn by a helper of its own (minttoys.alwaysontop),
since the daemon has no GTK: started while Always on Top is on and its border is wanted,
restarted when the frame's settings change, stopped when it goes off.

Interface io.github.konabe_studio.MintToys.AlwaysOnTop at
/io/github/konabe_studio/MintToys/modules/alwaysontop:

- GetState() -> a{sv}: shortcut s (toggle-above's keys, "" for none), shortcut_problem s
  ("taken" when Super+Ctrl+T was in use already)
- StateChanged(a{sv}): the same, whenever it changes
"""

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar, Protocol

from gi.repository import Gio, GLib

from minttoys.api import ALWAYSONTOP_INTERFACE as INTERFACE
from minttoys.api import ALWAYSONTOP_PATH as OBJECT_PATH
from minttoys.api import ALWAYSONTOP_SETTINGS
from minttoys.core import accel
from minttoys.core.i18n import _
from minttoys.core.nemo_action import INSTALLED_ROOT, LIBEXEC, PACKAGE_ROOT
from minttoys.modules.alwaysontop.options import SHORTCUT_KEYS, Options
from minttoys.modules.base import Context, Module

log = logging.getLogger(__name__)

ACTION = "toggle-above"
HELPER = "minttoys-always-on-top"
INTERFACE_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="GetState">
      <arg name="state" type="a{{sv}}" direction="out"/>
    </method>
    <signal name="StateChanged">
      <arg name="state" type="a{{sv}}"/>
    </signal>
  </interface>
</node>
"""


class Keybindings(Protocol):
    """Muffin's keys; core.keybindings.CinnamonKeybindings is the real one."""

    def wm_keys(self, action: str) -> list[str]: ...
    def set_wm_keys(self, action: str, keys: list[str]) -> None: ...
    def taken_by(self, keys: str) -> list[str]: ...


def cinnamon_keybindings() -> Keybindings:
    from minttoys.core.keybindings import CinnamonKeybindings

    return CinnamonKeybindings()


def helper_command(options: Options, package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The frame helper's command line: the installed launcher, or the checkout's module."""
    arguments = ["--width", str(options.border_width)]
    if options.border_color:
        arguments += ["--color", options.border_color]
    installed = LIBEXEC / HELPER
    if package_root == INSTALLED_ROOT and installed.exists():
        return [str(installed), *arguments]
    return [sys.executable, "-m", "minttoys.alwaysontop", *arguments]


class Helper(Protocol):
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


def start_helper(command: list[str]) -> Helper:
    environment = {**os.environ, "PYTHONPATH": str(PACKAGE_ROOT)}
    return subprocess.Popen(command, env=environment)


class AlwaysOnTop(Module):
    id: ClassVar[str] = "alwaysontop"
    name: ClassVar[str] = _("Always on Top")
    description: ClassVar[str] = _(
        "Pins a window above the others with Super+Ctrl+T, and frames it so you see which."
    )
    settings_types: ClassVar[Mapping[str, str]] = ALWAYSONTOP_SETTINGS

    def __init__(
        self,
        make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings,
        start: Callable[[list[str]], Helper] = start_helper,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for both."""
        self._make_keybindings = make_keybindings
        self._start = start
        self._keybindings: Keybindings | None = None
        self._helper: Helper | None = None
        self._options = Options()
        self._shortcut_problem = ""
        self._bus: Gio.DBusConnection | None = None
        self._registration = 0
        self._reported: dict[str, Any] = {}

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self._bus = context.bus
        self._options = Options.read(context.settings)
        try:
            self._keybindings = self._make_keybindings()
        except Exception:
            log.exception("no shortcut: Muffin's keybindings are not there")
        if self._options.shortcut:
            self._keep_shortcut()
        self._run_helper()
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._registration = context.bus.register_object(
            OBJECT_PATH, node.interfaces[0], self._on_call, None, None
        )

    def disable(self) -> None:
        self._stop_helper()
        if self._registration and self._bus is not None:
            self._bus.unregister_object(self._registration)
        self._registration = 0
        self._keybindings = None
        self._reported = {}

    def switched_off(self) -> None:
        self._drop_shortcut()

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        old = self._options
        self._options = Options.read(settings)
        if self._options.shortcut:
            self._keep_shortcut()
        else:
            self._drop_shortcut()
        frame = ("border", "border_color", "border_width")
        if any(getattr(old, key) != getattr(self._options, key) for key in frame):
            self._run_helper()
        self._emit()

    def state(self) -> dict[str, Any]:
        keys = self._keybindings.wm_keys(ACTION) if self._keybindings is not None else []
        return {"shortcut": keys[0] if keys else "", "shortcut_problem": self._shortcut_problem}

    def _keep_shortcut(self) -> None:
        """Gives toggle-above Super+Ctrl+T, unless it has keys already or they are taken."""
        if self._keybindings is None or self._keybindings.wm_keys(ACTION):
            return
        taken = self._keybindings.taken_by(SHORTCUT_KEYS)
        if taken:
            log.info("no shortcut: %s is taken by %s", SHORTCUT_KEYS, ", ".join(taken))
            self._shortcut_problem = "taken"
            return
        self._shortcut_problem = ""
        self._keybindings.set_wm_keys(ACTION, [SHORTCUT_KEYS])

    def _drop_shortcut(self) -> None:
        """Takes the keys back, if they are still the ones Always on Top gave."""
        self._shortcut_problem = ""
        if self._keybindings is None:
            return
        keys = self._keybindings.wm_keys(ACTION)
        if len(keys) == 1 and accel.same(keys[0], SHORTCUT_KEYS):
            self._keybindings.set_wm_keys(ACTION, [])

    def _run_helper(self) -> None:
        self._stop_helper()
        if not self._options.border:
            return
        try:
            self._helper = self._start(helper_command(self._options))
        except OSError:
            log.exception("the frame helper could not start")

    def _stop_helper(self) -> None:
        helper, self._helper = self._helper, None
        if helper is None or helper.poll() is not None:
            return
        helper.terminate()
        try:
            helper.wait(timeout=2)
        except subprocess.TimeoutExpired:
            log.warning("the frame helper did not stop")

    def _emit(self) -> None:
        if self._bus is None or not self._registration:
            return
        state = self.state()
        if state == self._reported:
            return
        self._reported = state
        self._bus.emit_signal(
            None, OBJECT_PATH, INTERFACE, "StateChanged", GLib.Variant("(a{sv})", (_typed(state),))
        )

    def _on_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        try:
            if method == "GetState":
                invocation.return_value(GLib.Variant("(a{sv})", (_typed(self.state()),)))
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))


def _typed(state: Mapping[str, Any]) -> dict[str, GLib.Variant]:
    return {key: GLib.Variant("s", value) for key, value in state.items()}
