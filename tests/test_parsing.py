import httpx
import pytest

from blr_air.domain import AirError
from blr_air.parsing import parse_local, parse_request


@pytest.mark.parametrize(
    "text,place,activity,hours,day,period",
    [
        (
            "@blr-air best 1-hour window to run in HSR Layout",
            "HSR Layout",
            "run",
            1,
            "next48",
            "any",
        ),
        ("best 2-hour cycling window in Koramangala", "Koramangala", "cycle", 2, "next48", "any"),
        ("When is the air cleanest in Whitefield?", "Whitefield", "walk", 1, "next48", "any"),
        (
            "Can I take the kids outside in Melbourne tomorrow morning?",
            "Melbourne",
            "kids",
            1,
            "tomorrow",
            "morning",
        ),
        ("run in Paris, France today", "Paris, France", "run", 1, "today", "any"),
        ("London", "London", "walk", 1, "next48", "any"),
        ("best time to run", "Bengaluru", "run", 1, "next48", "any"),
        ("AQI in Atlantis", "Atlantis", "walk", 1, "next48", "any"),
        ("walk in New York in the next 48 hours", "New York", "walk", 1, "next48", "any"),
    ],
)
def test_parses_documented_and_global_requests(text, place, activity, hours, day, period):
    q = parse_local(text)
    assert (q.place, q.activity, q.hours, q.day, q.period) == (place, activity, hours, day, period)


@pytest.mark.parametrize(
    "text",
    [
        "run for 3 hours in HSR Layout",
        "",
        "x" * 2001,
        "run in Paris next week",
        "run in HSR after 10pm",
    ],
)
def test_unsupported_requests_ask_for_supported_input(text):
    with pytest.raises(AirError):
        parse_local(text)


async def test_asi_failure_keeps_user_city_instead_of_defaulting():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(402, json={"error": "balance"})
        )
    ) as client:
        q = await parse_request("run in Delhi", client, api_key="test-key")
    assert q.place == "Delhi"


async def test_asi_can_parse_freeform_language_with_validated_json():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"place":"HSR Layout","hours":2,"activity":"run",'
                                '"day":"tomorrow","period":"morning"}'
                            }
                        }
                    ]
                },
            )
        )
    ) as client:
        q = await parse_request("HSR mein kal subah do ghante running", client, api_key="test-key")
    assert q.hours == 2
    assert q.day == "tomorrow"


async def test_invalid_asi_schema_falls_back_to_deterministic_parser():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"place":"Bengaluru","hours":999}'}}]},
            )
        )
    ) as client:
        q = await parse_request("cycle in London", client, api_key="test-key")
    assert q.place == "London"


@pytest.mark.parametrize(
    "text,city",
    [
        ("best window for Paris", "Paris"),
        ("London running window tomorrow morning", "London"),
        ("AQI London", "London"),
        ("best time to run in Runcorn", "Runcorn"),
    ],
)
def test_preserves_city_in_alternative_word_orders(text, city):
    assert parse_local(text).place == city


@pytest.mark.parametrize(
    "text",
    [
        "best 1-hour run between 6am and 8am in HSR Layout tomorrow",
        "best run day after tomorrow in HSR Layout",
        "best 90-minute walk in Paris",
        "walk in Paris from 6 to 8",
    ],
)
def test_does_not_silently_drop_unsupported_constraints(text):
    with pytest.raises(AirError):
        parse_local(text)


@pytest.mark.parametrize("content", ["{}", '{"activity":"run"}'])
async def test_incomplete_asi_extraction_cannot_overwrite_supplied_city(content):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": content}}]}
            )
        )
    ) as client:
        result = await parse_request("run in Delhi", client, api_key="test-key")
    assert result.place == "Delhi"


@pytest.mark.parametrize(
    "text,places",
    [
        ("compare HSR Layout and Koramangala for a run", ["HSR Layout", "Koramangala"]),
        ("best window in Whitefield vs Indiranagar", ["Whitefield", "Indiranagar"]),
    ],
)
def test_parses_local_place_comparisons(text, places):
    assert parse_local(text).places == places


async def test_asi_can_return_multiple_places():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"place":"HSR Layout",'
                                '"places":["HSR Layout","Whitefield"],'
                                '"hours":1,"activity":"run","day":"next48","period":"any"}'
                            }
                        }
                    ]
                },
            )
        )
    ) as client:
        result = await parse_request(
            "compare HSR Layout and Whitefield", client, api_key="test-key"
        )
    assert result.places == ["HSR Layout", "Whitefield"]


def test_extracts_user_limits_without_geocoding_constraint_words():
    q = parse_local(
        "run in Paris with AQI at most 100, rain at most 20%, "
        "feels like at most 30C, UV at most 3, wind at most 20 km/h, daylight only"
    )
    assert q.place == "Paris"
    assert (q.max_aqi, q.max_rain, q.max_temperature, q.max_uv, q.max_wind) == (100, 20, 30, 3, 20)
    assert q.daylight_only is True


def test_comparison_can_use_global_city_and_country_names():
    q = parse_local("compare Paris, France and London, UK for a walk tomorrow")
    assert q.places == ["Paris, France", "London, UK"]
    assert q.day == "tomorrow"


async def test_asi_cannot_drop_explicit_local_limits():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"place":"Paris","hours":1,"activity":"run",'
                                '"day":"next48","period":"any"}'
                            }
                        }
                    ]
                },
            )
        )
    ) as client:
        q = await parse_request("run in Paris with AQI at most 50", client, api_key="test")
    assert q.max_aqi == 50


@pytest.mark.parametrize("wording", ["AQI less than 50", "maximum AQI 50", "AQI no more than 50"])
def test_common_maximum_phrasings_never_silently_drop_a_limit(wording):
    assert parse_local(f"run in HSR Layout with {wording}").max_aqi == 50


def test_repeated_limits_choose_stricter_bound():
    assert parse_local("run in HSR Layout with AQI under 100 and AQI under 50").max_aqi == 50


def test_unparsed_numeric_limit_is_rejected_instead_of_ignored():
    with pytest.raises(AirError):
        parse_local("run in HSR Layout with AQI between 50 and 80")


async def test_asi_comparison_cannot_be_contaminated_by_limit_clause():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"place":"HSR Layout",'
                                '"places":["HSR Layout","Whitefield"],'
                                '"hours":1,"activity":"run","day":"next48","period":"any","max_aqi":50}'
                            }
                        }
                    ]
                },
            )
        )
    ) as client:
        result = await parse_request(
            "compare HSR Layout and Whitefield AQI under 50", client, api_key="test"
        )
    assert result.places == ["HSR Layout", "Whitefield"]


def test_local_three_locality_comparison_accepts_comma_list():
    result = parse_local("compare HSR Layout, Whitefield and Koramangala for a run")
    assert result.places == ["HSR Layout", "Whitefield", "Koramangala"]


@pytest.mark.parametrize(
    "text,field,expected",
    [
        ("feels like under 50 F", "max_temperature", 10),
        ("temperature at most 86°F", "max_temperature", 30),
        ("maximum temperature 30 Celsius", "max_temperature", 30),
        ("wind under 10 mph", "max_wind", 16.09344),
        ("wind at most 5 m/s", "max_wind", 18),
    ],
)
def test_converts_explicit_user_units(text, field, expected):
    q = parse_local("run in New York with " + text)
    assert getattr(q, field) == pytest.approx(expected)


async def test_asi_fahrenheit_conversion_is_not_overridden_with_celsius_number():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"place":"New York","hours":1,"activity":"run",'
                                '"day":"next48",'
                                '"period":"any","max_temperature":10}'
                            }
                        }
                    ]
                },
            )
        )
    ) as client:
        q = await parse_request(
            "run in New York with feels like under 50 F", client, api_key="test"
        )
    assert q.max_temperature == 10


@pytest.mark.parametrize(
    "text,place",
    [
        ("reviews of Central Park, New York", "Central Park, New York"),
        ("walk in Cubbon Park tomorrow with customer reviews", "Cubbon Park"),
        ("show ratings for Lalbagh", "Lalbagh"),
    ],
)
def test_venue_review_intent_retains_location(text, place):
    q = parse_local(text)
    assert q.place == place
    assert q.include_venue is True


def test_review_phrase_cannot_consume_following_limits_and_date():
    q = parse_local("run in Cubbon Park with reviews tomorrow morning AQI at most 30")
    assert (q.day, q.period, q.max_aqi) == ("tomorrow", "morning", 30)


@pytest.mark.parametrize(
    "text",
    [
        "show opening hours for Royal Botanic Gardens, Melbourne tomorrow morning",
        "accessibility of Royal Botanic Gardens, Melbourne tomorrow morning",
    ],
)
def test_venue_facility_intent_preserves_exact_named_place(text):
    q = parse_local(text)
    assert q.place == "Royal Botanic Gardens, Melbourne"
    assert q.include_venue and q.day == "tomorrow" and q.period == "morning"
