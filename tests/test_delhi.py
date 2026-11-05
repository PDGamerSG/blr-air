"""Delhi-specific behaviour that a plain Bengaluru-to-Delhi rename would get wrong."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from delhi_air.demo import DemoProvider
from delhi_air.domain import Hour, RequestSpec
from delhi_air.localities import ALIASES, LOCALITIES, NCR_CITIES, local_location
from delhi_air.parsing import parse_local
from delhi_air.scoring import aqi_category, select_window


@pytest.mark.parametrize(
    "text,name",
    [
        ("Delhi", "Delhi"),
        ("delhi", "Delhi"),
        ("New Delhi", "Delhi"),
        ("new delhi, india", "Delhi"),
        ("Delhi, India", "Delhi"),
        ("Delhi NCR", "Delhi"),
        ("NCR", "Delhi"),
        ("Dilli", "Delhi"),
        ("CP", "Connaught Place, Delhi"),
        ("Rajiv Chowk", "Connaught Place, Delhi"),
        ("Connaught Place, New Delhi", "Connaught Place, Delhi"),
        ("Old Delhi", "Chandni Chowk, Delhi"),
        ("Lodi Gardens", "Lodhi Garden, Delhi"),
        ("Hauz Khas Village", "Hauz Khas, Delhi"),
        ("Gurgaon", "Gurugram, Delhi NCR"),
        ("Gurugram, Haryana", "Gurugram, Delhi NCR"),
        ("Noida", "Noida, Delhi NCR"),
        ("Noida, Uttar Pradesh", "Noida, Delhi NCR"),
        ("Sector 62, Noida", "Noida, Delhi NCR"),
        ("Sector-18 Noida", "Noida, Delhi NCR"),
        ("Dwarka Sector 21", "Dwarka, Delhi"),
        ("Rohini sec 7", "Rohini, Delhi"),
    ],
)
def test_delhi_names_resolve_without_the_geocoder(text, name):
    location = local_location(text)
    assert location is not None and location.name == name
    assert location.timezone == "Asia/Kolkata"


@pytest.mark.parametrize(
    "text", ["Delhi, Ontario", "Delhi, Canada", "Delhi, New York", "Paris, France", "New", "South"]
)
def test_other_places_are_not_captured_by_delhi_names(text):
    assert local_location(text) is None


def test_every_alias_targets_a_known_locality():
    assert set(ALIASES.values()) <= set(LOCALITIES)
    assert NCR_CITIES <= set(LOCALITIES)


def test_localities_are_inside_the_national_capital_region():
    for name, latitude, longitude in LOCALITIES.values():
        assert 28.3 <= latitude <= 28.9, name
        assert 76.9 <= longitude <= 77.6, name


def test_site_localities_match_the_python_table():
    source = Path(__file__).parent.parent / "site/src/config.ts"
    found = re.findall(
        r'\{ name: "([^"]+)", lat: ([\d.]+), lon: ([\d.]+) \}', source.read_text(encoding="utf-8")
    )
    site = {name: (float(lat), float(lon)) for name, lat, lon in found}
    assert site == {name: (lat, lon) for name, lat, lon in LOCALITIES.values()}


def test_watch_localities_match_the_python_table():
    source = Path(__file__).parent.parent / "watch/app/src/main/java/com/delhiair/watch/core"
    text = (source / "Localities.kt").read_text(encoding="utf-8")
    found = re.findall(r'Locality\("([^"]+)", "([^"]+)", ([\d.]+), ([\d.]+)\)', text)
    watch = {key: (name, float(lat), float(lon)) for key, name, lat, lon in found}
    assert watch == LOCALITIES
    assert dict(re.findall(r'"([^"]+)" to "([^"]+)"', text)) == ALIASES


@pytest.mark.parametrize(
    "text,place",
    [
        ("best 1-hour window to run in Hauz Khas", "Hauz Khas"),
        ("walk near India Gate tomorrow morning", "India Gate"),
        ("run in New Delhi tomorrow", "New Delhi"),
        ("best time to cycle in Sector 62 Noida", "Sector 62 Noida"),
        ("cp walk today", "CP"),
        ("cleanest time in gurgaon", "gurgaon"),
    ],
)
def test_local_parser_extracts_delhi_places(text, place):
    request = parse_local(text)
    assert request.place.casefold() == place.casefold()
    assert local_location(request.place) is not None


def test_parser_defaults_to_delhi():
    assert parse_local("best time to go for a walk").place == "Delhi"
    assert RequestSpec().place == "Delhi"


def test_compare_ncr_cities():
    request = parse_local("compare Noida and Gurgaon for a run tomorrow morning")
    assert request.places == ["Noida", "Gurgaon"]


async def test_demo_supports_ncr_and_rejects_other_cities():
    demo = DemoProvider()
    assert (await demo.locate("Gurgaon")).name == "Gurugram, Delhi NCR"
    with pytest.raises(Exception, match="Delhi"):
        await demo.locate("Mumbai")


@pytest.mark.parametrize(
    "aqi,category",
    [
        (211, "Very unhealthy"),
        (300, "Very unhealthy"),
        (301, "Hazardous"),
        (487, "Hazardous"),
        (640, "Hazardous"),
    ],
)
def test_delhi_smog_readings_keep_a_category(aqi, category):
    assert aqi_category(aqi) == category


def test_smog_flat_aqi_still_prefers_the_low_pm_afternoon():
    # Open-Meteo's US AQI is smoothed, so Delhi's daily swing shows up mostly in PM2.5.
    now = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)
    rows = []
    for offset in range(48):
        at = now + timedelta(hours=offset)
        ist_hour = (at + timedelta(hours=5, minutes=30)).hour
        pm = 97 if 12 <= ist_hour <= 15 else 165
        rows.append(Hour(at, 210, pm, 0, 24))
    window = select_window(rows, RequestSpec(day="today"), "Asia/Kolkata", now)
    assert 12 <= window.start.hour <= 15


async def test_clean_air_limit_is_refused_on_a_smoggy_day_rather_than_relaxed():
    import httpx

    from delhi_air.domain import NoWindowError
    from delhi_air.service import AirService

    async with httpx.AsyncClient() as client:
        service = AirService(DemoProvider(), client)
        with pytest.raises(NoWindowError, match="never relaxed"):
            await service.recommend(RequestSpec(place="Noida", max_aqi=100))


async def test_comparison_discloses_places_sharing_one_air_model_cell():
    import httpx

    from delhi_air.service import AirService, spoken_summary

    async with httpx.AsyncClient() as client:
        service = AirService(DemoProvider(), client)
        result = await service.compare(RequestSpec(), ["Hauz Khas", "Anand Vihar"])
    assert result.shared_air_model == [["Hauz Khas, Delhi", "Anand Vihar, Delhi"]]
    data = result.to_dict()
    assert data["shared_air_model"] == result.shared_air_model
    assert "cannot say which has cleaner air" in data["summary"]
    assert "not evidence of cleaner air" in data["summary"]
    assert "share one air model cell" in spoken_summary(result)


@pytest.mark.parametrize(
    "text,name",
    [
        ("Rohini Sector 3, Delhi", "Rohini, Delhi"),
        ("Dwarka Sector 10, New Delhi", "Dwarka, Delhi"),
    ],
)
def test_sector_inside_a_full_address(text, name):
    assert local_location(text).name == name


def test_compare_accepts_the_names_the_app_prints():
    assert parse_local("compare Hauz Khas, Delhi and Noida").places == ["Hauz Khas, Delhi", "Noida"]
    assert parse_local("compare Hauz Khas, Noida").places == ["Hauz Khas", "Noida"]


async def locate_with(results, place):
    import httpx

    from delhi_air.providers import OpenMeteo

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"results": results}))
    async with httpx.AsyncClient(transport=transport) as client:
        return await OpenMeteo(client).locate(place)


NCT = "National Capital Territory of Delhi"


async def test_geocoder_understands_delhi_as_a_qualifier():
    hit = {"name": "Pitampura", "admin1": NCT, "country": "India", "country_code": "IN"}
    found = await locate_with([{**hit, "latitude": 28.7, "longitude": 77.13}], "Pitampura, Delhi")
    assert found.latitude == 28.7


async def test_a_bare_name_prefers_the_one_in_delhi():
    far = {"name": "Mehrauli", "admin1": "Uttar Pradesh", "latitude": 25.5, "longitude": 83.43}
    near = {"name": "Mehrauli", "admin1": NCT, "latitude": 28.52, "longitude": 77.18}
    assert (await locate_with([far, near], "Mehrauli")).latitude == 28.52
    assert (await locate_with([far], "Mehrauli")).latitude == 25.5


async def test_a_bare_sector_asks_which_city():
    with pytest.raises(Exception, match="Which city"):
        await locate_with([{"name": "Sector 62", "latitude": 33.3, "longitude": 44.4}], "Sector 62")
