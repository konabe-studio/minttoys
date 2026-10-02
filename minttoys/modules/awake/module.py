"""Awake, as the daemon runs it: the inhibitor, the timer, and the D-Bus interface the panel
icon, the settings app and the command line use.

Interface io.github.konabe_studio.MintToys.Awake at
/io/github/konabe_studio/MintToys/modules/awake:

- Start(mode s, minutes u, until s, keep_screen b): mode is "indefinite", "duration" (reads
  minutes), "until" (reads until, as "18:00") or "off". A bad value is InvalidArgs.
- Stop()
- Toggle(): Stop when on; when off, Start with Awake's settings (see state.Defaults).
- SetKeepScreen(keep_screen b): SetSettings with keep_screen alone.
- GetSettings() -> a{sv}: default_mode s, default_minutes u, default_until s, keep_screen b
  (see state.Defaults).
- SetSettings(a{sv}): saves the settings given, the rest stay. An unknown key or a bad
  value is InvalidArgs, and then nothing changes. keep_screen applies at once when on.
- GetState() -> a{sv}: mode s, keep_screen b, ends_at x (unix time, 0 when not timed).
  While off, keep_screen is the setting, the one the next Toggle uses.
- StateChanged(a{sv}): the same, whenever any of it changes
- SettingsChanged(a{sv}): every setting, whenever one changes
"""

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, ClassVar, Protocol

from gi.repository import Gio, GLib

from minttoys import APP_ID
from minttoys.api import AWAKE_INTERFACE as INTERFACE
from minttoys.api import AWAKE_PATH as OBJECT_PATH
from minttoys.api import AWAKE_SETTINGS
from minttoys.core import clock, notifications
from minttoys.core.i18n import _
from minttoys.modules.awake import state
from minttoys.modules.awake.inhibit import Flags, Inhibitor
from minttoys.modules.awake.state import OFF, Defaults, Mode, State
from minttoys.modules.base import Context, Module

log = logging.getLogger(__name__)

INTERFACE_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Start">
      <arg name="mode" type="s" direction="in"/>
      <arg name="minutes" type="u" direction="in"/>
      <arg name="until" type="s" direction="in"/>
      <arg name="keep_screen" type="b" direction="in"/>
    </method>
    <method name="Stop"/>
    <method name="Toggle"/>
    <method name="SetKeepScreen">
      <arg name="keep_screen" type="b" direction="in"/>
    </method>
    <method name="GetSettings">
      <arg name="settings" type="a{{sv}}" direction="out"/>
    </method>
    <method name="SetSettings">
      <arg name="settings" type="a{{sv}}" direction="in"/>
    </method>
    <method name="GetState">
      <arg name="state" type="a{{sv}}" direction="out"/>
    </method>
    <signal name="StateChanged">
      <arg name="state" type="a{{sv}}"/>
    </signal>
    <signal name="SettingsChanged">
      <arg name="settings" type="a{{sv}}"/>
    </signal>
  </interface>
</node>
"""
SIGNATURES = {"mode": "s", "keep_screen": "b", "ends_at": "x"}
SETTING_SIGNATURES = AWAKE_SETTINGS


class Holder(Protocol):
    """What Awake needs from an inhibitor; Inhibitor is the real one."""

    def hold(self, flags: Flags, reason: str) -> None: ...
    def release(self) -> None: ...


def session_inhibitor(bus: Gio.DBusConnection) -> Holder:
    return Inhibitor(bus, APP_ID)


class Awake(Module):
    id: ClassVar[str] = "awake"
    name: ClassVar[str] = _("Awake")
    description: ClassVar[str] = _(
        "Keeps the computer awake until you turn it off, for a set time, or until a time of"
        " day, without changing your power settings."
    )

    # The longest a timed mode goes without looking at the clock. It also looks at the end
    # time itself, so this only bounds how late it notices the end after a suspend or a
    # change of the clock.
    check_every = timedelta(minutes=1)

    def __init__(
        self,
        make_inhibitor: Callable[[Gio.DBusConnection], Holder] = session_inhibitor,
        notify: Callable[[Gio.DBusConnection, str, str], None] = notifications.send,
        now: Callable[[], datetime] = clock.now,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for all three."""
        self._make_inhibitor = make_inhibitor
        self._notify = notify
        self._now = now
        self._bus: Gio.DBusConnection | None = None
        self._inhibitor: Holder | None = None
        self._registration = 0
        self._timeout = 0
        self._state = OFF
        self._defaults = Defaults()
        self._save: Callable[[Mapping[str, Any]], None] = lambda changes: None

    @property
    def state(self) -> State:
        return self._state

    def enable(self, context: Context) -> None:
        self._bus = context.bus
        self._defaults = Defaults.read(context.settings)
        self._save = context.save
        self._inhibitor = self._make_inhibitor(context.bus)
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._registration = context.bus.register_object(
            OBJECT_PATH, node.interfaces[0], self._on_call, None, None
        )

    def disable(self) -> None:
        self._cancel_timer()
        try:
            if self._inhibitor is not None:
                self._inhibitor.release()
        finally:
            self._inhibitor = None
            if self._registration and self._bus is not None:
                self._bus.unregister_object(self._registration)
            self._registration = 0
            self._state = OFF

    def start(self, wanted: State) -> None:
        """Switches to `wanted`, from whatever was on before. Raises if the inhibitor cannot
        be taken, and then nothing changes.
        """
        if wanted.mode is Mode.OFF:
            self.stop()
            return
        if self._inhibitor is None:
            raise RuntimeError("Awake is not switched on in the daemon")
        flags = Flags.SUSPEND | Flags.IDLE if wanted.keep_screen else Flags.SUSPEND
        self._inhibitor.hold(flags, _("Awake is keeping the computer awake"))
        self._state = wanted
        log.info("on: %s", wanted.describe())
        self._schedule()
        self._emit()

    def stop(self) -> None:
        if self._state.mode is Mode.OFF:
            return
        self._cancel_timer()
        if self._inhibitor is not None:
            self._inhibitor.release()
        self._state = OFF
        log.info("off")
        self._emit()

    def toggle(self) -> None:
        if self._state.mode is Mode.OFF:
            self.start(self._defaults.start(self._now()))
        else:
            self.stop()

    @property
    def defaults(self) -> Defaults:
        return self._defaults

    def set_settings(self, changes: Mapping[str, Any]) -> None:
        """Checks every change, saves them, then applies them; a bad value or a config that
        cannot be written changes nothing. keep_screen applies to a running mode at once,
        keeping its end.
        """
        updated = self._defaults.update(changes)
        self._save({key: updated.settings()[key] for key in changes})
        self._defaults = updated
        self._emit_settings()
        if self._state.mode is not Mode.OFF and self._state.keep_screen != updated.keep_screen:
            self.start(replace(self._state, keep_screen=updated.keep_screen))
        elif "keep_screen" in changes:
            self._emit()  # while off, the state reports the setting

    def _reported(self) -> State:
        """The state as GetState gives it: while off, with the keep_screen setting."""
        if self._state.mode is Mode.OFF:
            return replace(OFF, keep_screen=self._defaults.keep_screen)
        return self._state

    def _expire(self) -> None:
        self.stop()
        if self._bus is not None:
            self._notify(
                self._bus,
                _("Awake is off"),
                _("The time is up. Your usual power settings apply again."),
            )

    def _schedule(self) -> None:
        self._cancel_timer()
        wait = state.next_check(self._state, self._now(), self.check_every)
        if wait is not None:
            milliseconds = math.ceil(wait / timedelta(milliseconds=1))
            self._timeout = GLib.timeout_add(milliseconds, self._on_timeout)

    def _on_timeout(self) -> bool:
        self._timeout = 0
        try:
            if state.expired(self._state, self._now()):
                self._expire()
            else:
                self._schedule()
        except Exception:
            log.exception("the timer could not end Awake")
        return GLib.SOURCE_REMOVE

    def _cancel_timer(self) -> None:
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0

    def _emit(self) -> None:
        if self._bus is not None and self._registration:
            self._bus.emit_signal(
                None,
                OBJECT_PATH,
                INTERFACE,
                "StateChanged",
                GLib.Variant("(a{sv})", (self._described(),)),
            )

    def _emit_settings(self) -> None:
        if self._bus is not None and self._registration:
            self._bus.emit_signal(
                None,
                OBJECT_PATH,
                INTERFACE,
                "SettingsChanged",
                GLib.Variant("(a{sv})", (self._settings(),)),
            )

    def _settings(self) -> dict[str, GLib.Variant]:
        return {
            key: GLib.Variant(SETTING_SIGNATURES[key], value)
            for key, value in self._defaults.settings().items()
        }

    def _described(self) -> dict[str, GLib.Variant]:
        return {
            key: GLib.Variant(SIGNATURES[key], value)
            for key, value in self._reported().describe().items()
        }

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
            if method == "Start":
                mode, minutes, until, keep_screen = parameters.unpack()
                self.start(state.request(mode, minutes, until, keep_screen, self._now()))
                invocation.return_value(None)
            elif method == "Stop":
                self.stop()
                invocation.return_value(None)
            elif method == "Toggle":
                self.toggle()
                invocation.return_value(None)
            elif method == "SetKeepScreen":
                (keep_screen,) = parameters.unpack()
                self.set_settings({"keep_screen": keep_screen})
                invocation.return_value(None)
            elif method == "GetSettings":
                invocation.return_value(GLib.Variant("(a{sv})", (self._settings(),)))
            elif method == "SetSettings":
                (changes,) = parameters.unpack()
                self.set_settings(changes)
                invocation.return_value(None)
            elif method == "GetState":
                invocation.return_value(GLib.Variant("(a{sv})", (self._described(),)))
        except ValueError as error:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(error))
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))
