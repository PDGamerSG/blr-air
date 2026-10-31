import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from blr_air.domain import Forecast, Location, RequestSpec, Window
from blr_air.service import Recommendation


def recommendation(**changes):
    start = datetime(2026, 10, 31, 2, 30, tzinfo=UTC)
    window = Window(
        start=start,
        end=start + timedelta(hours=1),
        us_aqi=40,
        pm2_5=10,
        rain_probability=0,
        temperature=24,
        max_aqi=40,
        score=45,
        apparent_temperature=25,
        uv_index=1,
        wind_speed=6,
        daylight=True,
    )
    return Recommendation(
        RequestSpec(activity="run"),
        Location("Cubbon Park, Bengaluru", 12.9763, 77.5929),
        Forecast((), None, "Asia/Kolkata", start - timedelta(hours=1)),
        replace(window, **changes),
    )


def assessment(result):
    from blr_air.assessment import assess

    return assess(result)


@pytest.mark.parametrize(
    ("maximum", "category", "phrase"),
    [
        (50, "Good", "little or no risk"),
        (51, "Moderate", "unusually sensitive"),
        (100, "Moderate", "unusually sensitive"),
        (101, "Unhealthy for sensitive groups", "sensitive groups"),
        (150, "Unhealthy for sensitive groups", "sensitive groups"),
        (151, "Unhealthy", "everyone"),
        (200, "Unhealthy", "everyone"),
        (201, "Very unhealthy", "everyone"),
        (300, "Very unhealthy", "everyone"),
        (301, "Hazardous", "everyone"),
    ],
)
def test_aqi_assessment_uses_worst_hour_not_soothing_average(maximum, category, phrase):
    result = assessment(recommendation(us_aqi=40, max_aqi=maximum))
    assert result["aqi"]["category"] == category
    assert result["aqi"]["index"] == 40
    assert result["aqi"]["worst_hourly"] == maximum
    assert phrase in result["aqi"]["meaning"].lower()
    if maximum > 100:
        assert result["warnings"]
        assert "indoor" in result["aqi"]["advice"].lower()


def test_bad_air_verdict_cannot_be_overruled_by_cool_dry_weather():
    result = assessment(recommendation(max_aqi=251))
    assert "indoor" in result["verdict"].lower()
    assert "avoid" in " ".join(result["checklist"]).lower()


def test_hazardous_air_does_not_offer_shorter_outdoor_activity_as_a_solution():
    result = assessment(recommendation(max_aqi=350))
    checklist = " ".join(result["checklist"]).lower()
    assert "avoid outdoor physical activity" in checklist
    assert "if you still go" not in checklist


def test_children_receive_sensitive_group_context_when_air_is_adverse():
    request = recommendation(max_aqi=120)
    request = replace(request, request=RequestSpec(activity="kids"))
    result = assessment(request)
    assert "children" in " ".join(result["checklist"]).lower()


def test_feels_like_heat_is_distinguished_from_air_temperature():
    result = assessment(recommendation(temperature=29, apparent_temperature=38))
    warnings = " ".join(result["warnings"]).lower()
    assert "feels like" in warnings and "38" in warnings
    assert "29" in warnings
    assert "heat" in result["verdict"].lower()


def test_uv_rain_and_night_are_not_hidden_by_good_air():
    result = assessment(recommendation(uv_index=8, rain_probability=80, daylight=False))
    warnings = " ".join(result["warnings"]).lower()
    assert "uv" in warnings and "8" in warnings
    assert "rain" in warnings and "80" in warnings
    assert "daylight" in warnings
    assert "shade" in " ".join(result["checklist"]).lower()


def test_missing_optional_data_is_explicit_not_assumed_good():
    result = assessment(
        recommendation(apparent_temperature=None, uv_index=None, wind_speed=None, daylight=None)
    )
    warnings = " ".join(result["warnings"]).lower()
    for field in ("feels-like", "uv", "wind", "daylight"):
        assert field in warnings
    assert "unavailable" in warnings
    assert "safe" not in result["verdict"].lower()


def test_cold_temperature_does_not_receive_heat_advice():
    result = assessment(recommendation(temperature=-4, apparent_temperature=-9))
    warnings = " ".join(result["warnings"]).lower()
    assert "freezing" in warnings
    assert "heat" not in warnings
    assert "ice" in " ".join(result["checklist"]).lower()


def test_cycling_checklist_includes_wind_without_inventing_a_safety_limit():
    request = recommendation(wind_speed=22)
    request = replace(request, request=RequestSpec(activity="cycle"))
    result = assessment(request)
    checklist = " ".join(result["checklist"]).lower()
    assert "22" in checklist and "gust" in checklist
    assert "unsafe" not in checklist


def test_location_and_reasons_are_explicit_and_json_serializable():
    request = recommendation()
    request = replace(
        request,
        request=RequestSpec(max_aqi=70, max_rain=10, daylight_only=True),
    )
    result = assessment(request)
    location = result["location"]
    assert location["resolved_name"] == "Cubbon Park, Bengaluru"
    assert location["latitude"] == 12.9763 and location["longitude"] == 77.5929
    assert location["timezone"] == "Asia/Kolkata"
    assert location["maps_url"] == (
        "https://www.google.com/maps/search/?api=1&query=12.9763%2C77.5929"
    )
    assert "street" in location["precision_note"].lower()
    reasons = " ".join(result["reasons"])
    assert "70" in reasons and "10" in reasons and "daylight" in reasons
    assert "ratings" not in result and "rating" not in location
    json.dumps(result, allow_nan=False)


def test_synthetic_assessment_keeps_demo_label_in_verdict():
    request = recommendation()
    request = replace(request, forecast=replace(request.forecast, is_demo=True))
    result = assessment(request)
    assert "demo" in result["verdict"].lower()
    assert "synthetic" in " ".join(result["warnings"]).lower()
