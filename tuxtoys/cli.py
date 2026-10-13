"""The tuxtoys command: the tools and the modules, from a terminal or a script.

    tuxtoys awake on [--for 90m | --until 18:00] [--screen | --no-screen]
    tuxtoys awake off
    tuxtoys awake toggle
    tuxtoys awake status
    tuxtoys lightswitch [status | toggle]
    tuxtoys alwaysontop opacity {up | down}
    tuxtoys modules [list | enable MODULE | disable MODULE]

Exit status: 0 when done, 1 when TuxToys could not do it, 2 when the command line is wrong.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Protocol, TextIO

from tuxtoys.api import ModuleInfo, ModuleOff, NotRunning, Refused
from tuxtoys.core import clock
from tuxtoys.core.i18n import _
from tuxtoys.modules.awake import text, timer
from tuxtoys.modules.lightswitch import text as lightswitch_text


class Client(Protocol):
    """What the command needs from tuxtoys.client.Client, which is the real one."""

    def modules(self) -> list[ModuleInfo]: ...
    def set_module_enabled(self, module_id: str, enabled: bool) -> None: ...
    def awake_state(self) -> dict: ...
    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None: ...
    def awake_stop(self) -> None: ...
    def awake_toggle(self) -> None: ...
    def lightswitch_state(self) -> dict: ...
    def lightswitch_toggle(self) -> None: ...


def main(
    argv: Sequence[str] | None = None,
    connect: Callable[[], Client] | None = None,
    now: Callable[[], datetime] = clock.now,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Runs one command. The tests hand in a client, a clock and streams of their own."""
    out, err = out or sys.stdout, err or sys.stderr
    args = parser().parse_args(argv)
    if args.command == "alwaysontop":
        return run_alwaysontop(args, err)
    try:
        client = (connect or _connect)()
        if args.command == "awake":
            run_awake(client, args, now(), out)
        elif args.command == "lightswitch":
            run_lightswitch(client, args, out)
        else:
            run_modules(client, args, out)
    except ImportError:
        print(_("TuxToys needs PyGObject: sudo apt install python3-gi"), file=err)
        return 1
    except NotRunning:
        print(_("TuxToys is not running in this session."), file=err)
        return 1
    except ModuleOff:
        if args.command == "lightswitch":
            print(_("Light Switch is switched off in TuxToys."), file=err)
            print(_("Switch it on with: tuxtoys modules enable lightswitch"), file=err)
        else:
            print(_("Awake is switched off in TuxToys."), file=err)
            print(_("Switch it on with: tuxtoys modules enable awake"), file=err)
        return 1
    except Refused as error:
        print(_("TuxToys refused: {reason}").format(reason=error), file=err)
        return 1
    return 0


def run_awake(client: Client, args: argparse.Namespace, now: datetime, out: TextIO) -> None:
    if args.action == "on":
        # Without --screen or --no-screen, the setting the panel icon shows decides.
        keep_screen = args.screen
        if keep_screen is None:
            keep_screen = client.awake_state()["keep_screen"]
        if args.duration is not None:
            client.awake_start("duration", args.duration, "", keep_screen)
        elif args.until is not None:
            client.awake_start("until", 0, args.until, keep_screen)
        else:
            client.awake_start("indefinite", 0, "", keep_screen)
    elif args.action == "off":
        client.awake_stop()
    elif args.action == "toggle":
        client.awake_toggle()
    print(text.describe(client.awake_state(), now), file=out)


def run_lightswitch(client: Client, args: argparse.Namespace, out: TextIO) -> None:
    if args.action == "toggle":
        client.lightswitch_toggle()
    print(lightswitch_text.describe(client.lightswitch_state()), file=out)


def run_alwaysontop(args: argparse.Namespace, err: TextIO) -> int:
    """Steps the active window's opacity, if it is pinned. Straight to X11: no daemon."""
    try:
        from tuxtoys.platform.x11 import step_active_opacity
    except ImportError:
        print(_("This needs python3-xlib: sudo apt install python3-xlib"), file=err)
        return 1
    try:
        stepped = step_active_opacity(args.direction == "up")
    except Exception as error:  # Xlib raises its own, display errors among them
        print(_("Could not change the window's opacity: {error}").format(error=error), file=err)
        return 1
    if not stepped:
        print(_("The active window is not kept on top, so its opacity stays as it is."), file=err)
        return 1
    return 0


def run_modules(client: Client, args: argparse.Namespace, out: TextIO) -> None:
    if args.action in ("enable", "disable"):
        client.set_module_enabled(args.module, args.action == "enable")
        infos = [info for info in client.modules() if info.id == args.module]
    else:
        infos = client.modules()
    print(describe_modules(infos), file=out)


def describe_modules(infos: list[ModuleInfo]) -> str:
    # TRANSLATORS: a module's state in the list `tuxtoys modules` prints.
    states = {"on": _("on"), "off": _("off"), "failed": _("failed")}
    width = max((len(info.id) for info in infos), default=0)
    state_width = max(len(label) for label in states.values())
    lines = []
    for info in infos:
        state = states.get(info.state, info.state)
        lines.append(f"{info.id:<{width}}  {state:<{state_width}}  {info.name}")
        if info.error:
            lines.append(f"{'':<{width}}  {info.error}")
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="tuxtoys", description=_("Power-user utilities for Linux Mint Cinnamon.")
    )
    commands = root.add_subparsers(dest="command", required=True, metavar=_("COMMAND"))

    awake = commands.add_parser(
        "awake", help=_("keep the computer awake"), description=_("Keep the computer awake.")
    )
    actions = awake.add_subparsers(dest="action", required=True, metavar=_("ACTION"))
    on = actions.add_parser(
        "on",
        help=_("switch Awake on"),
        description=_(
            "Switch Awake on: until you turn it off, for a set time, or until a time of day."
        ),
    )
    timing = on.add_mutually_exclusive_group()
    timing.add_argument(
        "--for",
        dest="duration",
        type=_minutes,
        metavar=_("DURATION"),
        help=_("stay awake this long: 90 or 90m, 2h, 1h30m"),
    )
    timing.add_argument(
        "--until",
        type=_time_of_day,
        metavar=_("HH:MM"),
        help=_("stay awake until this time of day, even one past midnight"),
    )
    on.add_argument(
        "--screen",
        action=argparse.BooleanOptionalAction,
        help=_("keep the screen on as well, or not; without either, as set in TuxToys"),
    )
    actions.add_parser("off", help=_("switch Awake off"))
    actions.add_parser(
        "toggle",
        help=_("switch Awake off when on, or on as set in TuxToys; good for a shortcut"),
    )
    actions.add_parser("status", help=_("show whether Awake is on, and for how long"))

    lightswitch = commands.add_parser(
        "lightswitch",
        help=_("switch between light and dark"),
        description=_("Switch the desktop between light and dark, or show when it is dark."),
    )
    switches = lightswitch.add_subparsers(dest="action", metavar=_("ACTION"))
    switches.add_parser("status", help=_("show the mode and the dark hours (the default)"))
    switches.add_parser(
        "toggle",
        help=_("switch to dark, or back to the day's mode, until the schedule changes"),
    )

    alwaysontop = commands.add_parser(
        "alwaysontop",
        help=_("change a pinned window's opacity"),
        description=_("Make the active window more or less opaque, if it is pinned on top."),
    )
    pinned = alwaysontop.add_subparsers(dest="action", required=True, metavar=_("ACTION"))
    opacity = pinned.add_parser("opacity", help=_("one step more or less opaque"))
    opacity.add_argument("direction", choices=("up", "down"))

    modules = commands.add_parser(
        "modules",
        help=_("list the modules, switch one on or off"),
        description=_("List TuxToys' modules, or switch one on or off."),
    )
    which = modules.add_subparsers(dest="action", metavar=_("ACTION"))
    which.add_parser("list", help=_("list the modules and their state (the default)"))
    for action, help_text in (
        ("enable", _("switch a module on")),
        ("disable", _("switch a module off")),
    ):
        choice = which.add_parser(action, help=help_text)
        choice.add_argument("module", metavar=_("MODULE"))
    return root


def _minutes(text: str) -> int:
    try:
        return int(timer.parse_duration(text) / timedelta(minutes=1))
    except ValueError:
        raise argparse.ArgumentTypeError(
            _(
                "'{text}' is not a duration. Use minutes (90 or 90m), hours (2h), or both (1h30m)."
            ).format(text=text)
        ) from None


def _time_of_day(text: str) -> str:
    try:
        return f"{timer.parse_clock_time(text):%H:%M}"
    except ValueError:
        raise argparse.ArgumentTypeError(
            _("'{text}' is not a time of day. Use hours and minutes, such as 18:00.").format(
                text=text
            )
        ) from None


def _connect() -> Client:
    # PyGObject only once a command really talks to the daemon.
    from tuxtoys.client import Client as BusClient

    return BusClient.connect()
