"""Sunrise and sunset, worked out exactly as Cinnamon's Night Light does, so that Light Switch
turns dark at the same moment Night Light turns warm.

Ported from cinnamon-settings-daemon's csd_night_light_get_sunrise_sunset and
csd_night_light_frac_day_is_between (plugins/color/csd-night-light-common.c), which take
their formulas from NOAA: https://gml.noaa.gov/grad/solcalc/calcdetails.html
"""

import math
from datetime import UTC, datetime, timedelta

_EPOCH = datetime(1900, 1, 1, tzinfo=UTC)


def valid_coordinates(latitude: float, longitude: float) -> bool:
    """Night Light stores (91, 181) until it knows where the computer is."""
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def sunrise_sunset(day: datetime, latitude: float, longitude: float) -> tuple[float, float] | None:
    """Sunrise and sunset on `day` (an aware datetime) as fractional hours of its local time:
    6:30 is 6.5. None where the sun does not rise or set that day, near the poles.
    """
    if not valid_coordinates(latitude, longitude):
        return None
    offset = day.utcoffset()
    tz_offset = (offset or timedelta()) / timedelta(hours=1)  # B5
    days = (day - _EPOCH) // timedelta(days=1)
    date_as_number = days + 2  # B7
    julian_day = date_as_number + 2415018.5 - tz_offset / 24
    julian_century = (julian_day - 2451545) / 36525
    geom_mean_long_sun = math.fmod(
        280.46646 + julian_century * (36000.76983 + julian_century * 0.0003032), 360
    )  # I2
    geom_mean_anom_sun = 357.52911 + julian_century * (
        35999.05029 - 0.0001537 * julian_century
    )  # J2
    eccent_earth_orbit = 0.016708634 - julian_century * (
        0.000042037 + 0.0000001267 * julian_century
    )  # K2
    sun_eq_of_ctr = (
        math.sin(math.radians(geom_mean_anom_sun))
        * (1.914602 - julian_century * (0.004817 + 0.000014 * julian_century))
        + math.sin(math.radians(2 * geom_mean_anom_sun)) * (0.019993 - 0.000101 * julian_century)
        + math.sin(math.radians(3 * geom_mean_anom_sun)) * 0.000289
    )  # L2
    sun_true_long = geom_mean_long_sun + sun_eq_of_ctr  # M2
    omega = math.radians(125.04 - 1934.136 * julian_century)
    sun_app_long = sun_true_long - 0.00569 - 0.00478 * math.sin(omega)  # P2
    arc_seconds = 21.448 - julian_century * (
        46.815 + julian_century * (0.00059 - julian_century * 0.001813)
    )
    mean_obliq_ecliptic = 23 + (26 + arc_seconds / 60) / 60  # Q2
    obliq_corr = mean_obliq_ecliptic + 0.00256 * math.cos(omega)  # R2
    sun_declin = math.degrees(
        math.asin(math.sin(math.radians(obliq_corr)) * math.sin(math.radians(sun_app_long)))
    )  # T2
    var_y = math.tan(math.radians(obliq_corr / 2)) ** 2  # U2
    eq_of_time = 4 * math.degrees(
        var_y * math.sin(2 * math.radians(geom_mean_long_sun))
        - 2 * eccent_earth_orbit * math.sin(math.radians(geom_mean_anom_sun))
        + 4
        * eccent_earth_orbit
        * var_y
        * math.sin(math.radians(geom_mean_anom_sun))
        * math.cos(2 * math.radians(geom_mean_long_sun))
        - 0.5 * var_y * var_y * math.sin(4 * math.radians(geom_mean_long_sun))
        - 1.25 * eccent_earth_orbit**2 * math.sin(2 * math.radians(geom_mean_anom_sun))
    )  # V2
    cos_ha = math.cos(math.radians(90.833)) / (
        math.cos(math.radians(latitude)) * math.cos(math.radians(sun_declin))
    ) - math.tan(math.radians(latitude)) * math.tan(math.radians(sun_declin))
    if not -1 <= cos_ha <= 1:
        return None  # the sun stays up, or down, all day
    ha_sunrise = math.degrees(math.acos(cos_ha))  # W2
    solar_noon = (720 - 4 * longitude - eq_of_time + tz_offset * 60) / 1440  # X2
    sunrise = solar_noon - ha_sunrise * 4 / 1440  # Y2
    sunset = solar_noon + ha_sunrise * 4 / 1440  # Z2
    return sunrise * 24, sunset * 24


def frac_day(moment: datetime) -> float:
    """The time of day as fractional hours: 16:30 is 16.5."""
    return moment.hour + moment.minute / 60 + moment.second / 3600


def is_between(value: float, start: float, end: float) -> bool:
    """Whether the time of day `value` lies from `start` up to `end`, across midnight if
    `end` comes first. Equal ends mean the whole day.
    """
    if end <= start:
        end += 24
    if value < start and value < end:
        value += 24
    return start <= value < end
