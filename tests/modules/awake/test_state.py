from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from minttoys.modules.awake.state import (
    MAX_MINUTES,
    OFF,
    Defaults,
    Mode,
    State,
    expired,
    next_check,
    request,
)

BUDAPEST = ZoneInfo("Europe/Budapest")
NOW = datetime(2026, 6, 1, 10, 0, tzinfo=BUDAPEST)  # 08:00 UTC


class TestRequest:
    def test_indefinite(self) -> None:
        assert request("indefinite", 0, "", True, NOW) == State(Mode.INDEFINITE, True)

    def test_duration_reads_minutes(self) -> None:
        wanted = request("duration", 90, "", False, NOW)
        assert wanted == State(Mode.DURATION, False, datetime(2026, 6, 1, 9, 30, tzinfo=UTC))

    def test_until_reads_the_time_of_day(self) -> None:
        wanted = request("until", 0, "18:00", True, NOW)
        assert wanted == State(Mode.UNTIL, True, datetime(2026, 6, 1, 16, 0, tzinfo=UTC))

    def test_until_past_midnight(self) -> None:
        wanted = request("until", 0, "01:00", False, NOW.replace(hour=23))
        assert wanted.ends_at == datetime(2026, 6, 1, 23, 0, tzinfo=UTC)

    def test_off(self) -> None:
        assert request("off", 30, "18:00", True, NOW) == OFF

    def test_a_mode_ignores_what_it_does_not_read(self) -> None:
        assert request("indefinite", 0, "not a time", False, NOW).mode is Mode.INDEFINITE
        assert request("duration", 30, "not a time", False, NOW).mode is Mode.DURATION

    def test_refuses_an_unknown_mode(self) -> None:
        with pytest.raises(ValueError, match="unknown mode"):
            request("sometimes", 30, "", False, NOW)

    def test_refuses_a_duration_of_zero(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            request("duration", 0, "", False, NOW)

    def test_refuses_a_duration_past_the_calendar(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            request("duration", 2**32 - 1, "", False, NOW)

    def test_refuses_a_time_that_is_not_one(self) -> None:
        with pytest.raises(ValueError, match="not a time of day"):
            request("until", 0, "25:00", False, NOW)


class TestDescribe:
    def test_off(self) -> None:
        assert OFF.describe() == {"mode": "off", "keep_screen": False, "ends_at": 0}

    def test_timed(self) -> None:
        wanted = State(Mode.DURATION, True, datetime(2026, 6, 1, 9, 30, tzinfo=UTC))
        assert wanted.describe() == {"mode": "duration", "keep_screen": True, "ends_at": 1780306200}


class TestTiming:
    def test_only_a_timed_mode_expires(self) -> None:
        assert not expired(OFF, NOW)
        assert not expired(State(Mode.INDEFINITE), NOW + timedelta(days=30))

    def test_expires_at_the_end_and_not_before(self) -> None:
        wanted = request("duration", 30, "", False, NOW)
        assert not expired(wanted, NOW + timedelta(minutes=29, seconds=59))
        assert expired(wanted, NOW + timedelta(minutes=30))

    def test_nothing_to_check_without_a_timer(self) -> None:
        assert next_check(OFF, NOW, timedelta(minutes=1)) is None
        assert next_check(State(Mode.INDEFINITE), NOW, timedelta(minutes=1)) is None

    def test_checks_every_so_often_while_far_from_the_end(self) -> None:
        wanted = request("duration", 120, "", False, NOW)
        assert next_check(wanted, NOW, timedelta(minutes=1)) == timedelta(minutes=1)

    def test_checks_at_the_end_when_it_is_sooner(self) -> None:
        wanted = request("duration", 1, "", False, NOW)
        later = NOW + timedelta(seconds=45)
        assert next_check(wanted, later, timedelta(minutes=1)) == timedelta(seconds=15)

    def test_checks_at_once_when_the_end_has_passed(self) -> None:
        wanted = request("duration", 1, "", False, NOW)
        assert next_check(wanted, NOW + timedelta(hours=3), timedelta(minutes=1)) == timedelta(0)


class TestDefaults:
    def test_without_settings_toggle_starts_indefinite_with_the_screen_free(self) -> None:
        defaults = Defaults.read({})
        assert defaults == Defaults(Mode.INDEFINITE, 60, "18:00", False)
        assert defaults.start(NOW) == State(Mode.INDEFINITE, False)

    def test_reads_every_setting(self) -> None:
        settings = {
            "default_mode": "duration",
            "default_minutes": 45,
            "default_until": "7:30",
            "keep_screen": True,
        }
        defaults = Defaults.read(settings)
        assert defaults == Defaults(Mode.DURATION, 45, "07:30", True)
        assert defaults.start(NOW) == State(
            Mode.DURATION, True, datetime(2026, 6, 1, 8, 45, tzinfo=UTC)
        )

    def test_until_starts_until_the_time_set(self) -> None:
        defaults = Defaults.read({"default_mode": "until", "default_until": "18:00"})
        assert defaults.start(NOW).ends_at == datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        "settings",
        [
            {"default_mode": "off"},
            {"default_mode": "sometimes"},
            {"default_mode": 3},
            {"default_minutes": 0},
            {"default_minutes": -5},
            {"default_minutes": "60"},
            {"default_minutes": True},
            {"default_minutes": 1.5},
            {"default_until": "25:00"},
            {"default_until": 1800},
            {"keep_screen": "yes"},
            {"keep_screen": 1},
        ],
    )
    def test_a_value_of_the_wrong_kind_falls_back(self, settings: dict) -> None:
        assert Defaults.read(settings) == Defaults()


class TestDefaultsUpdate:
    def test_changes_only_what_is_given(self) -> None:
        updated = Defaults().update({"default_minutes": 90, "keep_screen": True})
        assert updated == Defaults(Mode.INDEFINITE, 90, "18:00", True)

    def test_normalizes_the_time_of_day(self) -> None:
        assert Defaults().update({"default_until": "7:05"}).until == "07:05"

    def test_settings_is_the_config_form(self) -> None:
        assert Defaults(Mode.UNTIL, 45, "07:30", True).settings() == {
            "default_mode": "until",
            "default_minutes": 45,
            "default_until": "07:30",
            "keep_screen": True,
        }

    def test_refuses_a_key_it_does_not_know(self) -> None:
        with pytest.raises(ValueError, match="unknown setting: 'colour'"):
            Defaults().update({"colour": "green"})

    @pytest.mark.parametrize(
        ("changes", "message"),
        [
            ({"default_mode": "off"}, "default_mode is indefinite, duration or until"),
            ({"default_minutes": 0}, "default_minutes is 1 to 5999"),
            ({"default_minutes": 6000}, "default_minutes is 1 to 5999"),
            ({"default_minutes": True}, "default_minutes is 1 to 5999"),
            ({"default_until": "25:00"}, "default_until is a time of day"),
            ({"keep_screen": "yes"}, "keep_screen is true or false"),
        ],
    )
    def test_refuses_a_value_its_key_does_not_take(self, changes: dict, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            Defaults().update(changes)

    def test_all_or_none(self) -> None:
        with pytest.raises(ValueError, match="default_minutes"):
            Defaults().update({"keep_screen": True, "default_minutes": 0})

    def test_read_ignores_a_duration_too_long_for_the_settings_app(self) -> None:
        assert Defaults.read({"default_minutes": MAX_MINUTES + 1}).minutes == 60
