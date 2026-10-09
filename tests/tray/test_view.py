from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from minttoys.tray import view

BUDAPEST = ZoneInfo("Europe/Budapest")
NOW = datetime(2026, 6, 1, 10, 0, tzinfo=BUDAPEST)  # 08:00 UTC


def unix(moment: datetime) -> int:
    return int(moment.timestamp())


class TestPresent:
    def test_off(self) -> None:
        shown = view.present({"mode": "off", "keep_screen": True, "ends_at": 0}, NOW)
        assert shown == view.View(view.ICON_OFF, "Awake is off.", True, False, True)

    def test_on(self) -> None:
        state = {"mode": "indefinite", "keep_screen": False, "ends_at": 0}
        shown = view.present(state, NOW)
        assert shown.icon == view.ICON_ON
        assert shown.status == "Awake is on until you turn it off."
        assert (shown.available, shown.on, shown.keep_screen) == (True, True, False)

    def test_timed_shows_the_time_left(self) -> None:
        end = unix(datetime(2026, 6, 1, 8, 30, tzinfo=UTC))
        shown = view.present({"mode": "duration", "keep_screen": False, "ends_at": end}, NOW)
        assert shown.status == "Awake is on for 30 min more, until 10:30."

    @pytest.mark.parametrize(
        ("mode", "icon"),
        [
            ("indefinite", view.ICON_ON),
            ("duration", view.ICON_DURATION),
            ("until", view.ICON_UNTIL),
        ],
    )
    def test_the_icon_tells_the_mode(self, mode: str, icon: str) -> None:
        end = 0 if mode == "indefinite" else unix(datetime(2026, 6, 1, 8, 30, tzinfo=UTC))
        shown = view.present({"mode": mode, "keep_screen": False, "ends_at": end}, NOW)
        assert shown.icon == icon

    def test_no_state_shows_the_problem(self) -> None:
        shown = view.present(None, NOW, "MintToys is not running.")
        assert shown == view.View(view.ICON_OFF, "MintToys is not running.", False, False, False)


def test_icon_names_carry_the_app_id() -> None:
    assert view.ICON_ON == "io.github.konabe_studio.MintToys-awake-on-symbolic"
    assert view.ICON_OFF == "io.github.konabe_studio.MintToys-awake-off-symbolic"


def test_every_icon_is_in_the_checkout() -> None:
    icons = Path(__file__).parents[2] / "data" / "icons" / "hicolor" / "symbolic" / "apps"
    for name in (view.ICON_OFF, *view.ICONS.values()):
        assert (icons / f"{name}.svg").is_file(), name


@pytest.mark.parametrize(
    ("minutes", "label"),
    [(1, "For 1 minute"), (30, "For 30 minutes"), (60, "For 1 hour"), (120, "For 2 hours")],
)
def test_quick_label(minutes: int, label: str) -> None:
    assert view.quick_label(minutes) == label


class TestRefreshIn:
    def state(self, left: timedelta) -> dict:
        return {"mode": "duration", "keep_screen": False, "ends_at": unix(NOW + left)}

    def test_nothing_counts_down_while_off_or_indefinite(self) -> None:
        assert view.refresh_in(None, NOW) is None
        assert view.refresh_in({"mode": "off", "keep_screen": False, "ends_at": 0}, NOW) is None
        indefinite = {"mode": "indefinite", "keep_screen": False, "ends_at": 0}
        assert view.refresh_in(indefinite, NOW) is None

    @pytest.mark.parametrize(
        ("left", "wait"),
        [
            (timedelta(minutes=2, seconds=5), 6),  # 3 min shown until 2:00 is left
            (timedelta(minutes=2), 60),  # 2 min shown until 1:00 is left
            (timedelta(seconds=30), 31),
        ],
    )
    def test_wakes_just_after_the_minutes_left_go_down(self, left: timedelta, wait: int) -> None:
        assert view.refresh_in(self.state(left), NOW) == wait

    def test_nothing_once_the_end_has_passed(self) -> None:
        assert view.refresh_in(self.state(timedelta(minutes=-1)), NOW) is None


@pytest.mark.parametrize(
    ("hour", "minute", "offered"),
    [(10, 0, (11, 0)), (10, 29, (11, 0)), (10, 31, (12, 0)), (23, 0, (0, 0))],
)
def test_next_full_hour(hour: int, minute: int, offered: tuple[int, int]) -> None:
    assert view.next_full_hour(NOW.replace(hour=hour, minute=minute)) == offered
