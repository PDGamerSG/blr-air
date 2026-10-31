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
