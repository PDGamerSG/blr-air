from datetime import UTC, datetime, timedelta

import httpx

from blr_air.domain import CurrentAir, Forecast, Hour, Location, RequestSpec
from blr_air.service import AirService, describe, describe_comparison

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


class ComparisonProvider(ForecastProvider):
    async def locate(self, place):
        return Location(place, 12.9116, 77.6389, "Asia/Kolkata")

    async def forecast(self, location):
        base = 10 if location.name == "HSR Layout" else 60
        return Forecast(
            tuple(
                Hour(NOW.replace(minute=0) + timedelta(hours=h), base + h, 10, 0, 25)
                for h in range(1, 9)
            ),
            CurrentAir(NOW.replace(minute=0), base, 10),
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


async def test_comparison_ranks_places_and_keeps_backup_windows():
    async with httpx.AsyncClient() as client:
        service = AirService(ComparisonProvider(), client)
        result = await service.compare(RequestSpec(hours=1), ["HSR Layout", "Whitefield"], now=NOW)
    assert result.items[0].recommendation.location.name == "HSR Layout"
    assert result.items[0].recommendation.backups
    assert (
        result.items[1].recommendation.window.us_aqi > result.items[0].recommendation.window.us_aqi
    )
    text = describe_comparison(result)
    assert "Best place" in text and "Backup" in text


async def test_one_invalid_place_does_not_hide_successful_comparison_results():
    from blr_air.domain import LocationError

    class PartialProvider(ComparisonProvider):
        async def locate(self, place):
            if place == "Unknown":
                raise LocationError("Place not found")
            return await super().locate(place)

    async with httpx.AsyncClient() as client:
        result = await AirService(PartialProvider(), client).compare(
            RequestSpec(), ["Unknown", "HSR Layout"], now=NOW
        )
    data = result.to_dict()
    assert data["status"] == "ok" and data["partial"] is True
    assert data["winner"] == "HSR Layout"
    assert data["places"][1]["status"] == "error"


async def test_spoken_answer_preserves_bad_air_warning_and_source():
    from blr_air.service import spoken_summary

    async with httpx.AsyncClient() as client:
        result = await AirService(ForecastProvider(), client).recommend(RequestSpec(), now=NOW)
    answer = spoken_summary(result)
    assert "Unhealthy" in answer and "indoor" in answer
    assert "Open Meteo" in answer and "retrieved" in answer
    assert len(answer) < 2500


async def test_comparison_discloses_tied_scores_and_partial_coverage():
    from blr_air.domain import LocationError

    class TiedProvider(ComparisonProvider):
        async def locate(self, place):
            if place == "Unknown":
                raise LocationError("Place not found")
            return await super().locate(place)

    async with httpx.AsyncClient() as client:
        result = await AirService(TiedProvider(), client).compare(
            RequestSpec(), ["Whitefield", "Koramangala", "Unknown"], now=NOW
        )
    assert result.to_dict()["tied_places"] == ["Whitefield", "Koramangala"]
    assert "tie" in describe_comparison(result).lower()
    assert "could not" in describe_comparison(result).lower()
