"""The minttoys command: Awake and the modules, from a terminal or a script.

    minttoys awake on [--for 90m | --until 18:00] [--screen]
    minttoys awake off
    minttoys awake status
    minttoys modules [list | enable MODULE | disable MODULE]

Exit status: 0 when done, 1 when MintToys could not do it, 2 when the command line is wrong.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Protocol, TextIO

from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused
from minttoys.core import clock
from minttoys.core.i18n import _
from minttoys.modules.awake import timer


class Client(Protocol):
    """What the command needs from minttoys.client.Client, which is the real one."""

    def modules(self) -> list[ModuleInfo]: ...
    def set_module_enabled(self, module_id: str, enabled: bool) -> None: ...
    def awake_state(self) -> dict: ...
    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None: ...
    def awake_stop(self) -> None: ...


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
    try:
        client = (connect or _connect)()
        if args.command == "awake":
            run_awake(client, args, now(), out)
        else:
            run_modules(client, args, out)
    except ImportError:
        print(_("MintToys needs PyGObject: sudo apt install python3-gi"), file=err)
        return 1
    except NotRunning:
        print(_("MintToys is not running in this session."), file=err)
        return 1
    except ModuleOff:
        print(_("Awake is switched off in MintToys."), file=err)
        print(_("Switch it on with: minttoys modules enable awake"), file=err)
        return 1
    except Refused as error:
        print(_("MintToys refused: {reason}").format(reason=error), file=err)
        return 1
    return 0


def run_awake(client: Client, args: argparse.Namespace, now: datetime, out: TextIO) -> None:
    if args.action == "on":
        if args.duration is not None:
            client.awake_start("duration", args.duration, "", args.screen)
        elif args.until is not None:
            client.awake_start("until", 0, args.until, args.screen)
        else:
            client.awake_start("indefinite", 0, "", args.screen)
    elif args.action == "off":
        client.awake_stop()
    print(describe_awake(client.awake_state(), now), file=out)


def run_modules(client: Client, args: argparse.Namespace, out: TextIO) -> None:
    if args.action in ("enable", "disable"):
        client.set_module_enabled(args.module, args.action == "enable")
        infos = [info for info in client.modules() if info.id == args.module]
    else:
        infos = client.modules()
    print(describe_modules(infos), file=out)


def describe_awake(state: dict, now: datetime) -> str:
    """Awake's state in a sentence or two, the way `minttoys awake status` prints it."""
    if state["mode"] == "off":
        return _("Awake is off.")
    if state["mode"] == "indefinite":
        first = _("Awake is on until you turn it off.")
    else:
        end = datetime.fromtimestamp(state["ends_at"], now.tzinfo)
        first = _("Awake is on for {left} more, until {end}.").format(
            left=format_minutes(timer.minutes_left(now, end)), end=format_end(end, now)
        )
    if state["keep_screen"]:
        second = _("The screen stays on.")
    else:
        second = _("The screen may turn off, but the computer will not sleep.")
    return f"{first}\n{second}"


def format_minutes(minutes: int) -> str:
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return _("{minutes} min").format(minutes=minutes)
    if not minutes:
        return _("{hours} h").format(hours=hours)
    return _("{hours} h {minutes} min").format(hours=hours, minutes=minutes)


def format_end(end: datetime, now: datetime) -> str:
    """The time of day within the next 24 hours, which leaves no doubt which day it is; the
    date as well beyond that.
    """
    local = end.astimezone(now.tzinfo)
    # Not end - now: both carry the same zone, and Python would subtract clock times.
    if timer.remaining(now, end) < timedelta(hours=24):
        return f"{local:%H:%M}"
    return f"{local:%Y-%m-%d %H:%M}"


def describe_modules(infos: list[ModuleInfo]) -> str:
    states = {"on": _("on"), "off": _("off"), "failed": _("failed")}
    width = max((len(info.id) for info in infos), default=0)
    lines = []
    for info in infos:
        lines.append(f"{info.id:<{width}}  {states.get(info.state, info.state):<8}  {info.name}")
        if info.error:
            lines.append(f"{'':<{width}}  {info.error}")
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="minttoys", description=_("Power-user utilities for Linux Mint Cinnamon.")
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
    on.add_argument("--screen", action="store_true", help=_("keep the screen on as well"))
    actions.add_parser("off", help=_("switch Awake off"))
    actions.add_parser("status", help=_("show whether Awake is on, and for how long"))

    modules = commands.add_parser(
        "modules",
        help=_("list the modules, switch one on or off"),
        description=_("List MintToys' modules, or switch one on or off."),
    )
    which = modules.add_subparsers(dest="action", metavar=_("ACTION"))
    which.add_parser("list", help=_("list the modules and their state (the default)"))
    for action, text in (
        ("enable", _("switch a module on")),
        ("disable", _("switch a module off")),
    ):
        choice = which.add_parser(action, help=text)
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
    from minttoys.client import Client as BusClient

    return BusClient.connect()
