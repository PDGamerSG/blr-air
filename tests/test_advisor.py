"""The agent's open question: where and when should I go?"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from delhi_air.advisor import (
    SPOTS,
    find_anchor,
    fits,
    level,
    understand,
    wants_place,
    wants_suggestion,
)
from delhi_air.demo import DemoProvider
from delhi_air.domain import AirError, Location
from delhi_air.localities import closest_location, local_location
from delhi_air.service import AirService, Recommendation, describe
from delhi_air.stations import StationReading, parse_station


@pytest.mark.parametrize(
    "text",
    [
        "i want to go for a walk near rohini area",
        "go for a bike ride near Dwarka tomorrow evening",
        "where can i take my kids near Saket",
        "looking for a place to jog around Gurugram",
        "suggest somewhere for a stroll near Hauz Khas",
    ],
)
def test_open_requests_are_recognised(text):
    assert wants_place(text)


@pytest.mark.parametrize(
    "text",
    [
        "best 2-hour cycling window in Dwarka tomorrow morning",
        "compare Noida and Saket for a walk",
        "what is the AQI in Rohini right now",
        "what are the benefits of walking",
        "reviews of parks for a walk near Saket",
    ],
)
def test_other_requests_keep_their_existing_path(text):
    assert not wants_place(text)


@pytest.mark.parametrize(
    "text,anchor",
    [
        ("i want to go for a walk near rohini area", "rohini"),
        ("a walk in the evening near Saket", "Saket"),
        ("go for a run around Sector 62, Noida tomorrow", "Sector 62"),
        ("bike ride close to India Gate this evening", "India Gate"),
        ("i want to go for a walk", None),
    ],
)
def test_the_area_is_found(text, anchor):
    assert find_anchor(text) == anchor


@pytest.mark.parametrize(
    "text,activity,day,period",
    [
        ("go for a bike ride near Dwarka tomorrow evening", "cycle", "tomorrow", "evening"),
        ("a ride around Noida", "cycle", "next48", "any"),
        ("take my kids out near Saket today", "kids", "today", "any"),
        ("a jog near Rohini tomorrow morning", "run", "tomorrow", "morning"),
        ("a stroll near Rohini", "walk", "next48", "any"),
    ],
)
def test_the_outing_is_understood(text, activity, day, period):
    request = understand(text)
    assert (request.activity, request.day, request.period) == (activity, day, period)


def test_places_suit_the_activity():
    forest = {"kind": "nature_reserve", "area_m2": 900_000, "cycling": True}
    pocket = {"kind": "park", "area_m2": 8_000, "cycling": True}
    stadium = {"kind": "stadium", "area_m2": 50_000, "cycling": True}
    assert fits(forest, "cycle") and not fits(pocket, "cycle")
    assert fits(pocket, "walk") and not fits(pocket, "run")
    assert fits(stadium, "run") and not fits(stadium, "walk")
    assert not fits(forest, "kids")
    assert not fits({**forest, "cycling": False}, "cycle")


def test_place_data_is_real_and_inside_the_region():
    names = {spot["name"] for spot in SPOTS}
    assert len(SPOTS) > 300
    assert {"Swarn Jayanti Park", "DDA Dwarka Cycle Track", "Deer Park"} <= names
    for spot in SPOTS:
        assert 28.3 <= spot["latitude"] <= 28.9
        assert 76.9 <= spot["longitude"] <= 77.6


@pytest.fixture
async def service():
    async with httpx.AsyncClient() as client:
        yield AirService(DemoProvider(), client)


async def test_a_walk_near_rohini_returns_a_real_park_and_a_time(service):
    result = await service.chat("i want to go for a walk near rohini area")
    assert isinstance(result, Recommendation)
    assert result.location.name.endswith(", near Rohini")
    assert result.search["place"] in {spot["name"] for spot in SPOTS}
    assert result.search["distance_km"] <= 8
    assert len(result.search["alternatives"]) == 2
    assert result.window.end > result.window.start
    assert result.to_dict()["search"] == result.search
    text = describe(result)
    assert text.startswith(f"**Best place: {result.search['place']}**")
    assert "Best time:" in text and "OpenStreetMap" in text


async def test_a_bike_ride_prefers_a_cycle_track(service):
    result = await service.chat("go for a bike ride near Dwarka tomorrow evening")
    assert result.search["place"] == "DDA Dwarka Cycle Track"
    assert result.request.activity == "cycle"
    assert result.window.start.hour >= 17


async def test_no_area_asks_rather_than_guesses(service):
    assert "Which area" in await service.chat("i want to go for a walk")


async def test_near_me_uses_the_askers_position(service):
    result = await service.chat("a walk near me", near=(28.7366, 77.1132))
    assert result.location.name.endswith(", near your area")
    assert (
        await service.chat("a walk near me")
        == "Which area should I search? Try 'a walk near Rohini'."
    )


async def test_an_unknown_area_is_not_silently_replaced(service):
    with pytest.raises(Exception, match="Delhi"):
        await service.chat("a walk near Atlantis")


async def test_a_hard_limit_is_never_relaxed(service):
    with pytest.raises(Exception, match="never relaxed"):
        await service.chat("a walk near Rohini with AQI at most 10")


async def test_monitors_steer_the_choice_away_from_a_hotspot(service):
    class Stations:
        async def near(self, latitude, longitude):
            hotspot = latitude > 28.73
            return StationReading("Test", 600 if hotspot else 180, 1.0)

    calm = await service.chat("a walk near Rohini")
    service.advisor.stations = Stations()
    steered = await service.chat("a walk near Rohini")
    assert steered.search["measured"]["aqi"] == 180
    assert calm.search["measured"] is None


def station_payload(aqi=300, age_hours=0.5, geo=(28.73, 77.11)):
    moment = datetime(2026, 11, 5, 12, tzinfo=UTC) - timedelta(hours=age_hours)
    return {
        "status": "ok",
        "data": {
            "aqi": aqi,
            "city": {"name": "Rohini, Delhi", "geo": list(geo)},
            "time": {"iso": moment.isoformat()},
        },
    }


@pytest.mark.parametrize(
    "payload,usable",
    [
        (station_payload(), True),
        (station_payload(aqi="-"), False),
        (station_payload(age_hours=5), False),
        (station_payload(geo=(31.2, 121.4)), False),
        ({"status": "error", "data": "Invalid key"}, False),
    ],
)
def test_only_near_fresh_stations_count(payload, usable):
    now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    assert (parse_station(payload, 28.7366, 77.1132, now) is not None) is usable


@pytest.mark.parametrize(
    "heard,name",
    [
        ("socket", "Saket, Delhi"),
        ("house cause", "Hauz Khas, Delhi"),
        ("rohani", "Rohini, Delhi"),
        ("dwarika", "Dwarka, Delhi"),
        ("noyda", "Noida, Delhi NCR"),
        ("mayor vihar", "Mayur Vihar, Delhi"),
        ("bhavana", "Bawana, Delhi"),
        ("Havana", "Bawana, Delhi"),
    ],
)
def test_misheard_delhi_names_are_corrected(heard, name):
    assert closest_location(heard).name == name


@pytest.mark.parametrize("word", ["Paris", "Tokyo", "Melbourne", "Mumbai"])
def test_other_cities_are_not_bent_into_delhi_names(word):
    assert closest_location(word) is None


async def test_a_misheard_area_still_finds_a_place(service):
    result = await service.chat("i want to go for a walk near socket")
    assert result.location.name.endswith(", near Saket")


def test_the_planner_keeps_real_towns_with_similar_names():
    assert local_location("Okha") is None


@pytest.mark.parametrize(
    "text",
    ["what should i do today", "what can i do near Saket", "suggest something", "surprise me"],
)
def test_open_ended_requests_leave_the_choice_to_the_agent(text):
    assert wants_suggestion(text)


@pytest.mark.parametrize(
    "activity,aqi,expected",
    [
        ("walk", 80, "go"),
        ("walk", 130, "care"),
        ("walk", 180, "short"),
        ("run", 180, "stay"),
        ("kids", 180, "stay"),
        ("walk", 260, "stay"),
    ],
)
def test_levels_are_stricter_for_hard_exercise_and_children(activity, aqi, expected):
    assert level(activity, aqi) == expected


async def test_the_agent_decides_what_when_where_and_why(service):
    result = await service.advisor.auto(near=(28.7366, 77.1132), activities=("walk",))
    advice = result.suggestion
    assert advice["kind"] in ("short", "care", "go", "stay")
    assert advice["reasons"] and advice["headline"]
    assert result.search["place"] in advice["detail"]
    assert result.to_dict()["suggestion"] == advice
    assert describe(result).startswith(f"**{advice['headline']}**")


async def test_a_favourite_run_is_downgraded_when_the_air_is_too_bad(service):
    # The demo's cleanest air is about AQI 170: too high for running, fine for a short walk.
    result = await service.advisor.auto(near=(28.7366, 77.1132), activities=("run",))
    assert result.request.activity == "walk"
    assert any("isn't advised" in reason for reason in result.suggestion["reasons"])


async def test_usual_hours_pull_the_time_towards_the_routine(service):
    near = (28.7366, 77.1132)
    plain = await service.advisor.auto(near=near, activities=("walk",))
    wanted = (plain.backups[0].start.hour,)
    routine = await service.advisor.auto(near=near, activities=("walk",), usual_hours=wanted)
    assert routine.window.start.hour == wanted[0]
    assert any("usual" in reason for reason in routine.suggestion["reasons"])


async def test_bad_air_everywhere_says_stay_in_but_still_gives_the_least_bad_option(service):
    class Stations:
        async def near(self, latitude, longitude):
            return StationReading("Test", 600, 1.0)

    service.advisor.stations = Stations()
    result = await service.advisor.auto(near=(28.7366, 77.1132))
    assert result.suggestion["kind"] == "stay"
    assert result.suggestion["headline"] == "Better to stay in"
    assert result.request.activity == "walk"


async def test_chat_can_ask_the_agent_to_decide(service):
    result = await service.chat("what should i do near Rohini")
    assert isinstance(result, Recommendation) and result.suggestion
    assert "Which area" in await service.chat("what should i do")


class Abroad(DemoProvider):
    """Finds one city outside Delhi NCR, where there is no place data."""

    async def locate(self, place):
        if place.casefold().startswith("lisbon"):
            return Location("Lisbon, Portugal", 38.722, -9.139, "Europe/Lisbon")
        return await super().locate(place)


@pytest.mark.parametrize(
    "text",
    [
        "I actually want to go around Lisbon area and tell me what is best for me",
        "go for a walk near Lisbon",
    ],
)
async def test_outside_delhi_gives_the_best_time_and_says_why_no_place(text):
    async with httpx.AsyncClient() as client:
        result = await AirService(Abroad(), client).chat(text)
    assert isinstance(result, Recommendation)
    assert result.location.name == "Lisbon, Portugal"
    assert result.search is None
    assert result.suggestion["detail"] == "Lisbon"
    assert any("only know specific places" in reason for reason in result.suggestion["reasons"])


async def test_bawana_is_found_however_the_watch_hears_it(service):
    for heard in ("Bhavana", "Havana", "Bawana"):
        result = await service.chat(f"I want to go around {heard} area, what is best for me")
        assert isinstance(result, Recommendation)
        assert result.location.name.endswith(", near Bawana")


def test_an_area_ends_where_the_rest_of_the_sentence_begins():
    assert find_anchor("go around Saket area and tell me what is best for me") == "Saket"


async def test_going_around_a_delhi_area_gets_a_real_place(service):
    result = await service.chat("I want to go around Saket area and tell me what is best for me")
    assert isinstance(result, Recommendation)
    assert result.search["place"] in {spot["name"] for spot in SPOTS}


async def test_a_named_activity_is_kept_when_asking_what_is_best(service):
    result = await service.chat("a run near Saket, what is best for me")
    assert result.request.activity == "run"


async def test_no_places_near_the_wearer_stays_an_error():
    async with httpx.AsyncClient() as client:
        with pytest.raises(AirError, match="suitable place"):
            await AirService(Abroad(), client).chat("what should i do", near=(38.722, -9.139))
