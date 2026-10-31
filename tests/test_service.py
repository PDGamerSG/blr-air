from datetime import UTC, datetime, timedelta

import httpx

from blr_air.domain import CurrentAir, Forecast, Hour, Location, RequestSpec
from blr_air.service import AirService, describe

NOW = datetime(2026, 10, 31, 1, 10, tzinfo=UTC)


class ForecastProvider:
    async def locate(self, place):
        return Location("HSR Layout, Bengaluru", 12.9116, 77.6389, "Asia/Kolkata")

    async def forecast(self, location):
        return Forecast(
            tuple(
                Hour(NOW.replace(minute=0) + timedelta(hours=h), 160, 70, 20, 33) for h in (1, 2)
            ),
            CurrentAir(NOW.replace(minute=0), 180, 90),
            "Asia/Kolkata",
            NOW,
        )


async def test_service_renders_current_and_window_with_source_timezone_and_risk():
    async with httpx.AsyncClient() as client:
        result = await AirService(ForecastProvider(), client).recommend(
            RequestSpec(hours=2, activity="kids"), now=NOW
        )
    text = describe(result)
    assert "180" in text and "160" in text
    assert "Asia/Kolkata" in text
    assert "Open-Meteo" in text and "CAMS" in text
    assert "Unhealthy" in text
    assert "indoor" in text.lower()
    assert result.to_dict()["window"]["end"] == "2026-10-31T09:30:00+05:30"


async def test_coordinate_requests_do_not_run_geocoding():
    class CoordinateProvider(ForecastProvider):
        async def locate(self, place):
            raise AssertionError("Coordinates should bypass geocoding")

    async with httpx.AsyncClient() as client:
        result = await AirService(CoordinateProvider(), client).recommend(
            RequestSpec(), location=Location("Coordinates", 12.91, 77.64), now=NOW
        )
    assert result.location.name == "Coordinates"
