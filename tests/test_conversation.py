import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from blr_air.domain import AirError, CurrentAir, Forecast, Hour, Location, ProviderError
from blr_air.service import AirService, Recommendation


class NoForecast:
    async def locate(self, place):
        pytest.fail(f"A conversational question must not be geocoded as a city: {place}")

    async def forecast(self, location):
        pytest.fail("A conversational question must not request an outdoor window")


def completion(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})


@pytest.mark.parametrize(
    "question,answer",
    [
        ("What is PM2.5?", "PM2.5 means particles no wider than 2.5 micrometres."),
        ("Explain photosynthesis in two sentences", "Plants use light to make sugars."),
        ("Explain how to boil eggs for 8 minutes", "Start timing once the water boils."),
    ],
)
async def test_normal_questions_get_direct_answers_without_a_forecast(question, answer):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return completion({"kind": "answer", "text": answer})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await AirService(NoForecast(), client, api_key="test").chat(question)
    assert result == answer
    assert len(calls) == 1
    assert calls[0]["messages"][-1]["content"] == question


@pytest.mark.parametrize(
    "value,category",
    [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"), (151, "Unhealthy")],
)
async def test_supplied_aqi_numbers_use_verified_categories_instead_of_model_guess(value, category):
    def must_not_guess(request):
        pytest.fail("Known AQI boundaries should come from the existing AQI guide")

    async with httpx.AsyncClient(transport=httpx.MockTransport(must_not_guess)) as client:
        result = await AirService(NoForecast(), client, api_key="test").chat(
            f"What does US AQI {value} mean?"
        )
    assert f"{value} is {category}" in result


async def test_conditions_lookup_does_not_add_a_country_not_supplied_by_the_user():
    provider = WeatherProvider()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: completion({"kind": "conditions", "place": "HSR Layout, India", "day": "now"})
        )
    ) as client:
        await AirService(provider, client, api_key="test").chat("What's the AQI in HSR Layout now?")
    assert provider.places == ["HSR Layout"]


async def test_unclear_question_gets_a_clarification_instead_of_default_city():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: completion({"kind": "clarify", "text": "Which city are you asking about?"})
        )
    ) as client:
        result = await AirService(NoForecast(), client, api_key="test").chat("Will it rain there?")
    assert result == "Which city are you asking about?"


class WeatherProvider:
    def __init__(self):
        self.places = []

    async def locate(self, place):
        self.places.append(place)
        return Location("HSR Layout, Bengaluru", 12.9116, 77.6389, "Asia/Kolkata")

    async def forecast(self, location):
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        return Forecast(
            tuple(Hour(now + timedelta(hours=i), 125, 40, 80, 26) for i in range(49)),
            CurrentAir(now, 145, 44),
            "Asia/Kolkata",
            datetime.now(UTC),
        )


async def test_current_air_question_returns_current_model_not_a_future_best_window():
    provider = WeatherProvider()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: completion({"kind": "conditions", "place": "HSR Layout", "day": "now"})
        )
    ) as client:
        result = await AirService(provider, client, api_key="test").chat(
            "What's the AQI in HSR now?"
        )
    assert isinstance(result, str)
    assert "145" in result and "44.0" in result
    assert "current model" in result.lower()
    assert "Best available" not in result
    assert "Open-Meteo" in result and "Forecast retrieved" in result
    assert provider.places == ["HSR Layout"]


async def test_weather_question_returns_requested_day_without_calendar_or_activity_window():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: completion({"kind": "conditions", "place": "HSR Layout", "day": "tomorrow"})
        )
    ) as client:
        result = await AirService(WeatherProvider(), client, api_key="test").chat(
            "Will I need an umbrella in HSR tomorrow?"
        )
    assert isinstance(result, str)
    assert "80%" in result and "26.0" in result
    assert "tomorrow" in result.lower()
    assert "Google Calendar" not in result and "Best available" not in result


async def test_naturally_worded_plan_still_preserves_explicit_limits():
    calls = []

    def respond(request):
        calls.append(request)
        return completion(
            {"kind": "plan"}
            if len(calls) == 1
            else {
                "place": "HSR Layout",
                "activity": "run",
                "hours": 1,
                "day": "tomorrow",
                "period": "morning",
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await AirService(WeatherProvider(), client, api_key="test").chat(
            "I'd love a jog around HSR tomorrow morning; keep AQI at most 150"
        )
    assert isinstance(result, Recommendation)
    assert result.request.max_aqi == 150
    assert result.request.activity == "run" and result.request.day == "tomorrow"


@pytest.mark.parametrize("content", [{}, {"kind": "answer", "text": ""}])
async def test_invalid_conversation_output_does_not_turn_general_question_into_city(content):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: completion(content))
    ) as client:
        result = await AirService(NoForecast(), client, api_key="test").chat(
            "Explain photosynthesis"
        )
    assert isinstance(result, str)
    assert "try" in result.lower() or "unavailable" in result.lower()


async def test_keyless_aqi_explanation_works_without_geocoding():
    async with httpx.AsyncClient() as client:
        result = await AirService(NoForecast(), client).chat("What does US AQI 150 mean?")
    assert isinstance(result, str)
    assert "Unhealthy for sensitive groups" in result


async def test_missing_conversation_key_is_honest_and_does_not_query_a_fake_city():
    async with httpx.AsyncClient() as client:
        result = await AirService(NoForecast(), client).chat("Explain photosynthesis")
    assert isinstance(result, str)
    assert "conversational" in result.lower()


@pytest.mark.parametrize(
    "question",
    [
        "Answer with exactly 3 bullet points: benefits of walking.",
        "List the advantages of cycling.",
    ],
)
async def test_activity_explanations_during_an_outage_are_not_geocoded_as_outings(question):
    async with httpx.AsyncClient() as client:
        result = await AirService(NoForecast(), client).chat(question)
    assert isinstance(result, str) and "conversational" in result.lower()


async def test_current_conditions_provider_failure_cannot_be_replaced_with_model_measurements():
    class Unavailable(WeatherProvider):
        async def forecast(self, location):
            raise ProviderError("Open-Meteo is unavailable")

    calls = []

    def respond(request):
        calls.append(request)
        return completion({"kind": "conditions", "place": "HSR Layout", "day": "now"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ProviderError, match="Open-Meteo is unavailable"):
            await AirService(Unavailable(), client, api_key="test").chat("AQI in HSR now?")
    assert len(calls) == 1


async def test_conversational_planning_keeps_existing_time_horizon_validation():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: completion({"kind": "plan"}))
    ) as client:
        with pytest.raises(AirError, match="48 hours"):
            await AirService(NoForecast(), client, api_key="test").chat("Run in Paris next week")


@pytest.mark.parametrize("status", [402, 503])
async def test_conversation_provider_outage_preserves_local_planning_and_aqi_explanations(status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status))
    ) as client:
        service = AirService(WeatherProvider(), client, api_key="test")
        definition = await service.chat("What does US AQI 150 mean?")
        plan = await service.chat("run in HSR Layout tomorrow morning with AQI at most 150")
    assert "Unhealthy for sensitive groups" in definition
    assert isinstance(plan, Recommendation) and plan.request.max_aqi == 150
