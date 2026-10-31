from datetime import UTC, datetime, timedelta

import pytest

from blr_air.domain import Hour, NoWindowError, RequestSpec
from blr_air.scoring import aqi_category, select_window

NOW = datetime(2026, 10, 31, 0, 40, tzinfo=UTC)  # 06:10 in Bengaluru


def hour(h, *, aqi=50, pm=10, rain=0, temp=25):
    return Hour(datetime(2026, 10, 31, tzinfo=UTC) + timedelta(hours=h), aqi, pm, rain, temp)


def test_avoids_past_hours_even_when_their_air_is_cleanest():
    result = select_window(
        [hour(0, aqi=1), hour(1), hour(2, aqi=80)], RequestSpec(), "Asia/Kolkata", NOW
    )
    assert result.start == datetime(2026, 10, 31, 1, tzinfo=UTC)


def test_two_hour_window_uses_both_hours_and_reports_aggregates():
    result = select_window(
        [hour(1, aqi=1, rain=90), hour(2, aqi=60, pm=12), hour(3, aqi=40, pm=8, rain=10)],
        RequestSpec(hours=2),
        "Asia/Kolkata",
        NOW,
    )
    assert result.start.astimezone(UTC).hour == 2
    assert result.end.astimezone(UTC).hour == 4
    assert result.us_aqi == 50
    assert result.pm2_5 == 10
    assert result.rain_probability == 10


def test_does_not_join_rows_across_missing_hour():
    with pytest.raises(NoWindowError):
        select_window([hour(1), hour(3)], RequestSpec(hours=2), "Asia/Kolkata", NOW)


def test_48_hour_limit_applies_to_end_of_window():
    with pytest.raises(NoWindowError):
        select_window([hour(48), hour(49)], RequestSpec(hours=2), "Asia/Kolkata", NOW)


def test_never_falls_back_to_nighttime():
    with pytest.raises(NoWindowError):
        select_window([hour(18), hour(19)], RequestSpec(), "Asia/Kolkata", NOW)


def test_heat_and_pm25_affect_ranking_when_aqi_and_rain_are_equal():
    result = select_window(
        [hour(1, temp=36), hour(2, pm=50), hour(3)], RequestSpec(), "Asia/Kolkata", NOW
    )
    assert result.start.astimezone(UTC).hour == 3


def test_ties_choose_earliest_regardless_of_input_order():
    result = select_window([hour(3), hour(2), hour(1)], RequestSpec(), "Asia/Kolkata", NOW)
    assert result.start.astimezone(UTC).hour == 1


def test_today_and_morning_apply_in_location_timezone():
    result = select_window(
        [hour(1, aqi=90), hour(9, aqi=1), hour(25, aqi=1)],
        RequestSpec(day="today", period="morning"),
        "Asia/Kolkata",
        NOW,
    )
    assert result.start.astimezone(UTC).hour == 1


def test_dst_uses_real_elapsed_hours_and_explicit_offsets():
    now = datetime(2026, 11, 1, 4, tzinfo=UTC)
    rows = [Hour(datetime(2026, 11, 1, h, tzinfo=UTC), 50, 10, 0, 20) for h in (10, 11)]
    result = select_window(rows, RequestSpec(hours=2), "America/New_York", now)
    assert result.start.isoformat() == "2026-11-01T05:00:00-05:00"
    assert result.end.isoformat() == "2026-11-01T07:00:00-05:00"


@pytest.mark.parametrize("utc_hour,period", [(15, "any"), (6, "morning"), (11, "afternoon")])
def test_entire_window_must_fit_local_period_even_with_fractional_timezone(utc_hour, period):
    with pytest.raises(NoWindowError):
        select_window([hour(utc_hour)], RequestSpec(period=period), "Asia/Kolkata", NOW)


@pytest.mark.parametrize(
    "value,label",
    [
        (50, "Good"),
        (51, "Moderate"),
        (101, "Unhealthy for sensitive groups"),
        (151, "Unhealthy"),
        (201, "Very unhealthy"),
        (301, "Hazardous"),
    ],
)
def test_aqi_categories(value, label):
    assert aqi_category(value) == label


@pytest.mark.parametrize("hours", [0, 3, -1, True, "2"])
def test_rejects_unsupported_duration(hours):
    with pytest.raises(ValueError):
        RequestSpec(hours=hours)
