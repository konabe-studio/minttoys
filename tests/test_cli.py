import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from minttoys import cli
from minttoys.api import ModuleInfo, ModuleOff, NotRunning, Refused

BUDAPEST = ZoneInfo("Europe/Budapest")
NOW = datetime(2026, 6, 1, 10, 0, tzinfo=BUDAPEST)  # 08:00 UTC
OFF = {"mode": "off", "keep_screen": False, "ends_at": 0}
AWAKE = ModuleInfo("awake", "Awake", "Keeps the computer awake.", "on", "")


def unix(*fields: int) -> int:
    return int(datetime(*fields, tzinfo=UTC).timestamp())


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.state = OFF
        self.infos = [AWAKE]
        self.error: Exception | None = None
        self.lightswitch = {
            "dark": False,
            "dark_from": "18:09",
            "dark_to": "06:53",
            "by_sun": True,
            "problem": "",
            "shortcut": "<Primary><Shift><Super>d",
            "shortcut_problem": "",
        }

    def _check(self) -> None:
        if self.error:
            raise self.error

    def modules(self) -> list[ModuleInfo]:
        self._check()
        return self.infos

    def set_module_enabled(self, module_id: str, enabled: bool) -> None:
        self._check()
        self.calls.append(("set_module_enabled", module_id, enabled))

    def awake_state(self) -> dict:
        self._check()
        return self.state

    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None:
        self._check()
        self.calls.append(("awake_start", mode, minutes, until, keep_screen))

    def awake_stop(self) -> None:
        self._check()
        self.calls.append(("awake_stop",))

    def awake_toggle(self) -> None:
        self._check()
        self.calls.append(("awake_toggle",))

    def lightswitch_state(self) -> dict:
        self._check()
        return self.lightswitch

    def lightswitch_toggle(self) -> None:
        self._check()
        self.calls.append(("lightswitch_toggle",))
        self.lightswitch = {**self.lightswitch, "dark": not self.lightswitch["dark"]}


def run(client: FakeClient, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    status = cli.main(list(argv), lambda: client, lambda: NOW, out, err)
    return status, out.getvalue(), err.getvalue()


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


class TestAwakeOn:
    def test_without_a_time_is_indefinite(self, client: FakeClient) -> None:
        assert run(client, "awake", "on")[0] == 0
        assert client.calls == [("awake_start", "indefinite", 0, "", False)]

    def test_for(self, client: FakeClient) -> None:
        run(client, "awake", "on", "--for", "1h30m")
        assert client.calls == [("awake_start", "duration", 90, "", False)]

    def test_until_is_sent_as_hh_mm(self, client: FakeClient) -> None:
        run(client, "awake", "on", "--until", "8:05")
        assert client.calls == [("awake_start", "until", 0, "08:05", False)]

    def test_screen(self, client: FakeClient) -> None:
        run(client, "awake", "on", "--screen")
        assert client.calls == [("awake_start", "indefinite", 0, "", True)]

    def test_no_screen_overrides_the_setting(self, client: FakeClient) -> None:
        client.state = {"mode": "off", "keep_screen": True, "ends_at": 0}
        run(client, "awake", "on", "--no-screen")
        assert client.calls == [("awake_start", "indefinite", 0, "", False)]

    def test_without_either_the_setting_decides(self, client: FakeClient) -> None:
        client.state = {"mode": "off", "keep_screen": True, "ends_at": 0}
        run(client, "awake", "on", "--for", "30m")
        assert client.calls == [("awake_start", "duration", 30, "", True)]

    def test_prints_the_state_it_ends_up_in(self, client: FakeClient) -> None:
        client.state = {"mode": "indefinite", "keep_screen": True, "ends_at": 0}
        assert "Awake is on until you turn it off." in run(client, "awake", "on")[1]

    def test_for_and_until_together_are_refused(
        self, client: FakeClient, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exit_:
            run(client, "awake", "on", "--for", "1h", "--until", "18:00")
        assert exit_.value.code == 2
        assert "not allowed with" in capsys.readouterr().err
        assert client.calls == []

    @pytest.mark.parametrize(
        ("flag", "value", "message"),
        [("--for", "abc", "is not a duration"), ("--until", "25:00", "is not a time of day")],
    )
    def test_a_bad_value_is_a_usage_error(
        self,
        client: FakeClient,
        capsys: pytest.CaptureFixture[str],
        flag: str,
        value: str,
        message: str,
    ) -> None:
        with pytest.raises(SystemExit) as exit_:
            run(client, "awake", "on", flag, value)
        assert exit_.value.code == 2
        assert message in capsys.readouterr().err
        assert client.calls == []


class TestAwakeOffAndStatus:
    def test_off(self, client: FakeClient) -> None:
        status, out, _ = run(client, "awake", "off")
        assert (status, client.calls) == (0, [("awake_stop",)])
        assert out == "Awake is off.\n"

    def test_status_changes_nothing(self, client: FakeClient) -> None:
        assert run(client, "awake", "status")[0] == 0
        assert client.calls == []

    def test_toggle(self, client: FakeClient) -> None:
        status, out, _ = run(client, "awake", "toggle")
        assert (status, client.calls) == (0, [("awake_toggle",)])
        assert out == "Awake is off.\n"


class TestModules:
    def test_list_is_the_default(self, client: FakeClient) -> None:
        status, out, _ = run(client, "modules")
        assert status == 0
        assert out == "awake  on      Awake\n"

    def test_a_failed_module_shows_why(self, client: FakeClient) -> None:
        client.infos = [ModuleInfo("awake", "Awake", "", "failed", "RuntimeError: no bus")]
        out = run(client, "modules", "list")[1]
        assert out == "awake  failed  Awake\n       RuntimeError: no bus\n"

    @pytest.mark.parametrize(("action", "enabled"), [("enable", True), ("disable", False)])
    def test_enable_and_disable(self, client: FakeClient, action: str, enabled: bool) -> None:
        status, out, _ = run(client, "modules", action, "awake")
        assert status == 0
        assert client.calls == [("set_module_enabled", "awake", enabled)]
        assert out.startswith("awake")


class TestErrors:
    def test_not_running(self, client: FakeClient) -> None:
        client.error = NotRunning()
        status, _, err = run(client, "awake", "status")
        assert status == 1
        assert err == "MintToys is not running in this session.\n"

    def test_module_off_says_how_to_switch_it_on(self, client: FakeClient) -> None:
        client.error = ModuleOff()
        status, _, err = run(client, "awake", "on")
        assert status == 1
        assert "minttoys modules enable awake" in err

    def test_refused_says_why(self, client: FakeClient) -> None:
        client.error = Refused("unknown module: 'nope'")
        status, _, err = run(client, "modules", "enable", "nope")
        assert status == 1
        assert err == "MintToys refused: unknown module: 'nope'\n"

    def test_no_pygobject(self) -> None:
        def connect() -> FakeClient:
            raise ImportError("No module named 'gi'")

        err = io.StringIO()
        assert cli.main(["awake", "status"], connect, lambda: NOW, io.StringIO(), err) == 1
        assert "python3-gi" in err.getvalue()

    def test_a_command_is_required(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_:
            cli.main([])
        assert exit_.value.code == 2


class TestLightSwitch:
    def test_status_is_the_default(self, client: FakeClient) -> None:
        status, out, _ = run(client, "lightswitch")
        assert status == 0
        assert out.splitlines() == [
            "The desktop is in its day mode now.",
            "Dark from 18:09 to 06:53, sunset to sunrise.",
            "Keyboard shortcut: Shift+Ctrl+Super+D",
        ]

    def test_toggle(self, client: FakeClient) -> None:
        out = run(client, "lightswitch", "toggle")[1]
        assert client.calls == [("lightswitch_toggle",)]
        assert out.splitlines()[0] == "The desktop is dark now."

    def test_set_times_and_a_custom_theme(self, client: FakeClient) -> None:
        client.lightswitch = {
            "dark": False,
            "dark_from": "20:00",
            "dark_to": "06:00",
            "by_sun": False,
            "problem": "custom",
            "shortcut": "",
            "shortcut_problem": "taken",
        }
        out = run(client, "lightswitch", "status")[1]
        assert out.splitlines()[1:] == [
            "Dark from 20:00 to 06:00.",
            "Your themes are not one of Mint's styles, so Light Switch leaves them alone.",
            "Its keyboard shortcut, Shift+Ctrl+Super+D, is in use already, so it has none.",
        ]

    def test_switched_off_says_how_to_switch_it_on(self, client: FakeClient) -> None:
        client.error = ModuleOff()
        status, _, err = run(client, "lightswitch")
        assert status == 1
        assert err.splitlines() == [
            "Light Switch is switched off in MintToys.",
            "Switch it on with: minttoys modules enable lightswitch",
        ]
