import importlib.resources
import os
import zoneinfo
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from minttoys.core.clock import local_zone


def zone_file(key: str) -> bytes:
    """The compiled rules of a zone, from the system or from the tzdata package."""
    for root in zoneinfo.TZPATH:
        candidate = Path(root, key)
        if candidate.is_file():
            return candidate.read_bytes()
    return importlib.resources.files("tzdata.zoneinfo").joinpath(*key.split("/")).read_bytes()


def link(tmp_path: Path, target: Path) -> Path:
    localtime = tmp_path / "localtime"
    try:
        os.symlink(target, localtime)
    except OSError:
        pytest.skip("this system cannot make symbolic links")
    return localtime


def test_tz_names_the_zone(tmp_path: Path) -> None:
    zone = local_zone({"TZ": "Europe/Budapest"}, tmp_path / "missing")
    assert zone == ZoneInfo("Europe/Budapest")


def test_tz_may_start_with_a_colon(tmp_path: Path) -> None:
    assert local_zone({"TZ": ":Asia/Tokyo"}, tmp_path / "missing") == ZoneInfo("Asia/Tokyo")


def test_a_tz_that_is_not_a_zone_name_leaves_it_to_localtime(tmp_path: Path) -> None:
    localtime = tmp_path / "localtime"
    localtime.write_bytes(zone_file("Europe/Budapest"))
    zone = local_zone({"TZ": "CET-1CEST,M3.5.0,M10.5.0/3"}, localtime)
    assert str(zone) == "localtime"


def test_a_link_into_a_zoneinfo_tree_names_the_zone(tmp_path: Path) -> None:
    target = tmp_path / "usr" / "share" / "zoneinfo" / "Europe" / "Budapest"
    target.parent.mkdir(parents=True)
    target.write_bytes(zone_file("Europe/Budapest"))
    assert local_zone({}, link(tmp_path, target)) == ZoneInfo("Europe/Budapest")


def test_a_copied_file_is_read_with_its_rules(tmp_path: Path) -> None:
    localtime = tmp_path / "localtime"
    localtime.write_bytes(zone_file("Europe/Budapest"))
    zone = local_zone({}, localtime)
    assert str(zone) == "localtime"
    assert datetime(2026, 1, 15, 12, 0, tzinfo=zone).isoformat() == "2026-01-15T12:00:00+01:00"
    assert datetime(2026, 7, 15, 12, 0, tzinfo=zone).isoformat() == "2026-07-15T12:00:00+02:00"


def test_nothing_at_all_is_utc(tmp_path: Path) -> None:
    assert local_zone({}, tmp_path / "missing") is UTC
