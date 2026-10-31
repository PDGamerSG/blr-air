from datetime import UTC, datetime

import httpx
import pytest

from blr_air.domain import LocationError, ProviderError
from blr_air.providers import OpenMeteo, merge_forecasts


def payloads():
    times = [1793408400, 1793412000, 1793415600]
    aq = {
        "timezone": "Asia/Kolkata",
        "current": {"time": times[0], "us_aqi": 107, "pm2_5": 29.9},
        "hourly": {"time": times, "us_aqi": [60, 50, 40], "pm2_5": [15, 12, 10]},
    }
    wx = {
        "timezone": "Asia/Kolkata",
        "hourly": {
            "time": times,
            "precipitation_probability": [30, None, 0],
            "temperature_2m": [25, 24, 23],
        },
    }
    return aq, wx


def test_aligns_by_timestamp_and_drops_missing_rain_without_inventing_zero():
    aq, wx = payloads()
    result = merge_forecasts(aq, wx, datetime.now(UTC))
    assert len(result.hours) == 2
    assert result.hours[0].rain_probability == 30
    assert result.hours[1].us_aqi == 40
    assert result.current.us_aqi == 107


def test_missing_current_is_not_replaced_with_future_forecast():
    aq, wx = payloads()
    del aq["current"]
    assert merge_forecasts(aq, wx, datetime.now(UTC)).current is None


@pytest.mark.parametrize("field,value", [("us_aqi", float("nan")), ("pm2_5", -2)])
def test_discards_nonfinite_and_negative_pollution(field, value):
    aq, wx = payloads()
    aq["hourly"][field][0] = value
    assert len(merge_forecasts(aq, wx, datetime.now(UTC)).hours) == 1


def test_malformed_provider_payload_fails_explicitly():
    with pytest.raises(ProviderError):
        merge_forecasts({"hourly": {}}, {}, datetime.now(UTC))


async def test_locality_resolution_does_not_need_network():
    def offline(request):
        raise AssertionError("local lookup should not call HTTP")

    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
        result = await OpenMeteo(client).locate("HSR Layout, Bangalore")
        assert result.name == "HSR Layout, Bengaluru"
        assert result.latitude == pytest.approx(12.9116)


async def test_global_geocoding_retains_country_and_timezone():
    def respond(request):
        assert request.url.params["name"] == "Melbourne"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "name": "Melbourne",
                        "latitude": -37.814,
                        "longitude": 144.963,
                        "timezone": "Australia/Melbourne",
                        "country": "Australia",
                        "admin1": "Victoria",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await OpenMeteo(client).locate("Melbourne")
        assert result.timezone == "Australia/Melbourne"
        assert "Australia" in result.name


async def test_unknown_place_never_falls_back_to_bengaluru():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"results": []}))
    ) as client:
        with pytest.raises(LocationError):
            await OpenMeteo(client).locate("no-such-place-xyz")


async def test_retries_transient_provider_error_but_stops_after_three_attempts():
    attempts = []

    def respond(request):
        attempts.append(request)
        return httpx.Response(503, json={"error": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ProviderError):
            await OpenMeteo(client).locate("Paris")
    assert len(attempts) == 3
