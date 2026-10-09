"""Light Switch, as the daemon runs it: the schedule, the switch, and the D-Bus interface the
settings app and the command line use.

Interface io.github.konabe_studio.MintToys.LightSwitch at
/io/github/konabe_studio/MintToys/modules/lightswitch:

- Toggle(): switches now, to dark from the day's mode or back; the schedule takes over
  again at its next change.
- GetState() -> a{sv}: dark b (the desktop is in Mint's dark mode now), dark_from s and
  dark_to s (today's dark hours as "HH:MM"), by_sun b (they are sunset and sunrise), problem
  s ("" when the desktop can be switched, "custom" for themes that are none of Mint's
  styles, "no-mode" for a style without the mode to switch to)
- StateChanged(a{sv}): the same, whenever any of it changes

The settings (day_mode, schedule, dark_from, dark_to; see options.Options) go through the
daemon's GetModuleSettings and SetModuleSettings.

It switches only when the schedule moves from day to night or back, and only from the other
mode: a desktop already dark at nightfall, or already light or mixed at daybreak, is left
as the user set it. Switching off leaves the desktop as it is.
"""

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, ClassVar, Protocol

from gi.repository import Gio, GLib

from minttoys.api import LIGHTSWITCH_INTERFACE as INTERFACE
from minttoys.api import LIGHTSWITCH_PATH as OBJECT_PATH
from minttoys.api import LIGHTSWITCH_SETTINGS
from minttoys.core import clock
from minttoys.core.i18n import _
from minttoys.modules.base import Context, Module
from minttoys.modules.lightswitch import schedule, styles
from minttoys.modules.lightswitch.options import Options
from minttoys.modules.lightswitch.schedule import Dark, NightLight
from minttoys.modules.lightswitch.styles import Look, Style

log = logging.getLogger(__name__)

INTERFACE_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Toggle"/>
    <method name="GetState">
      <arg name="state" type="a{{sv}}" direction="out"/>
    </method>
    <signal name="StateChanged">
      <arg name="state" type="a{{sv}}"/>
    </signal>
  </interface>
</node>
"""
SIGNATURES = {"dark": "b", "dark_from": "s", "dark_to": "s", "by_sun": "b", "problem": "s"}
# How often it looks at the clock. A minute late at most, after a suspend or a clock change.
CHECK_EVERY_SECONDS = 60


class Desktop(Protocol):
    """What Light Switch needs from Cinnamon; desktop.CinnamonDesktop is the real one."""

    def look(self) -> Look: ...
    def styles(self) -> list[Style]: ...
    def write(self, mode: str, look: Look) -> None: ...
    def night_light(self) -> NightLight: ...


def cinnamon_desktop() -> Desktop:
    from minttoys.modules.lightswitch.desktop import CinnamonDesktop

    return CinnamonDesktop()


class LightSwitch(Module):
    id: ClassVar[str] = "lightswitch"
    name: ClassVar[str] = _("Light Switch")
    description: ClassVar[str] = _(
        "Switches between light and dark by the time of day, the way the Themes window does."
    )
    settings_types: ClassVar[Mapping[str, str]] = LIGHTSWITCH_SETTINGS

    def __init__(
        self,
        make_desktop: Callable[[], Desktop] = cinnamon_desktop,
        now: Callable[[], datetime] = clock.now,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for both."""
        self._make_desktop = make_desktop
        self._now = now
        self._desktop: Desktop | None = None
        self._bus: Gio.DBusConnection | None = None
        self._registration = 0
        self._timeout = 0
        self._options = Options()
        # Which side of the schedule it last switched for, so it switches once per change.
        self._scheduled_dark: bool | None = None
        self._problem = ""
        self._reported: dict[str, Any] = {}
        # Mint's styles, read when it comes on and again before each switch, rather than on
        # every look at the clock.
        self._styles: list[Style] = []

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
        self._desktop = self._make_desktop()
        self._styles = self._desktop.styles()
        self._options = Options.read(context.settings)
        if not self._options.day_mode:
            # Keep the mode in use: whoever uses Light keeps Light.
            self._options = self._options.update({"day_mode": self._day_mode_in_use()})
            try:
                context.set_settings({"day_mode": self._options.day_mode})
            except Exception:
                log.exception("the day's mode could not be saved")
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self._registration = context.bus.register_object(
            OBJECT_PATH, node.interfaces[0], self._on_call, None, None
        )
        self._follow_schedule()
        self._timeout = GLib.timeout_add_seconds(CHECK_EVERY_SECONDS, self._on_timeout)

    def disable(self) -> None:
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0
        if self._registration and self._bus is not None:
            self._bus.unregister_object(self._registration)
        self._registration = 0
        self._desktop = None
        self._styles = []
        self._scheduled_dark = None
        self._reported = {}

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        self._options = Options.read(settings)
        self._follow_schedule()

    def toggle(self) -> None:
        """Dark now if the desktop is not, else the day's mode."""
        self._reload_styles()
        found = self._active()
        if found is not None:
            _style, mode, _variant = found
            self._switch(mode != "dark")
        self._emit()

    def state(self) -> dict[str, Any]:
        dark = self._dark_hours()
        found = self._active()
        return {
            "dark": found is not None and found[1] == "dark",
            "dark_from": schedule.clock(dark.start),
            "dark_to": schedule.clock(dark.end),
            "by_sun": dark.by_sun,
            "problem": "custom" if found is None else self._problem,
        }

    def _follow_schedule(self) -> None:
        """Switches when the schedule has moved to the other side since the last time."""
        wanted = schedule.is_dark(self._dark_hours(), self._now())
        if wanted != self._scheduled_dark:
            self._scheduled_dark = wanted
            self._reload_styles()
            found = self._active()
            if found is not None:
                _style, mode, _variant = found
                if wanted != (mode == "dark"):
                    self._switch(wanted)
        self._emit()

    def _switch(self, dark: bool) -> None:
        assert self._desktop is not None
        found = self._active()
        if found is None:
            return
        style, _mode, variant = found
        mode = "dark" if dark else self._options.day
        target = styles.variant_for(style, mode, variant)
        if target is None:
            self._problem = "no-mode"
            return
        self._problem = ""
        log.info("switching to %s: %s", mode, target.name)
        self._desktop.write(mode, target.look)

    def _active(self) -> tuple[Style, str, styles.Variant] | None:
        if self._desktop is None:
            return None
        return styles.active(self._styles, self._desktop.look())

    def _reload_styles(self) -> None:
        if self._desktop is not None:
            self._styles = self._desktop.styles()

    def _day_mode_in_use(self) -> str:
        found = self._active()
        return "light" if found is not None and found[1] == "light" else "mixed"

    def _dark_hours(self) -> Dark:
        if self._options.schedule == "times" or self._desktop is None:
            return schedule.by_times(self._options.dark_from, self._options.dark_to)
        return schedule.by_night_light(self._desktop.night_light(), self._now())

    def _on_timeout(self) -> bool:
        try:
            self._follow_schedule()
        except Exception:
            log.exception("the schedule could not be followed")
        return GLib.SOURCE_CONTINUE

    def _emit(self) -> None:
        """Signals the state when it differs from what was last signalled."""
        if self._bus is None or not self._registration:
            return
        state = self.state()
        if state == self._reported:
            return
        self._reported = state
        self._bus.emit_signal(
            None,
            OBJECT_PATH,
            INTERFACE,
            "StateChanged",
            GLib.Variant("(a{sv})", (self._typed(state),)),
        )

    @staticmethod
    def _typed(state: Mapping[str, Any]) -> dict[str, GLib.Variant]:
        return {key: GLib.Variant(SIGNATURES[key], value) for key, value in state.items()}

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
            if method == "Toggle":
                self.toggle()
                invocation.return_value(None)
            elif method == "GetState":
                invocation.return_value(GLib.Variant("(a{sv})", (self._typed(self.state()),)))
        except ValueError as error:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(error))
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))
