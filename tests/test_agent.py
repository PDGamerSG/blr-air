from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic.v1 import ValidationError
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
)

from blr_air.agent_runtime import AgentHandlers
from blr_air.domain import ProviderError
from blr_air.models import ComparisonRequest, ComparisonResponse, WindowRequest, WindowResponse
from blr_air.telemetry import Usage


class Context:
    def __init__(self):
        self.sent = []
        self.logger = SimpleNamespace(exception=lambda *args: None)

    async def send(self, sender, message):
        self.sent.append(message)


class BrokenService:
    async def chat(self, text):
        raise ProviderError("Forecast service unavailable. Try again shortly.")

    async def recommend(self, *args, **kwargs):
        raise ProviderError("Forecast service unavailable. Try again shortly.")


async def test_chat_acknowledges_then_returns_error_text_and_closes_session(tmp_path):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    incoming = ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="run in HSR Layout")],
    )
    await handler.on_chat(ctx, "agent-test", incoming)
    assert isinstance(ctx.sent[0], ChatAcknowledgement)
    assert ctx.sent[0].acknowledged_msg_id == incoming.msg_id
    assert "unavailable" in ctx.sent[1].content[0].text
    assert isinstance(ctx.sent[1].content[-1], EndSessionContent)
    assert handler.usage.stats()["failed_queries"] == 1


async def test_acknowledgements_and_end_only_messages_do_not_create_reply_loops(tmp_path):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    await handler.on_ack(
        ctx,
        "agent-test",
        ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=uuid4()),
    )
    assert ctx.sent == []
    await handler.on_chat(
        ctx,
        "agent-test",
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[EndSessionContent(type="end-session")],
        ),
    )
    assert len(ctx.sent) == 1  # Only acknowledge termination; don't start another conversation.
    assert handler.usage.stats()["queries"] == 0


@pytest.mark.parametrize("prompt", ["hello", "@blr-air help", "How do I use this?"])
async def test_welcome_and_help_explain_usage_without_attempting_a_forecast(tmp_path, prompt):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    await handler.on_chat(
        ctx,
        "agent-test",
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=prompt)],
        ),
    )
    reply = ctx.sent[1]
    assert "@blr-air" in reply.content[0].text
    assert "1-hour" in reply.content[0].text and "tomorrow morning" in reply.content[0].text
    assert "updates" in reply.content[0].text.lower()
    assert "unavailable" not in reply.content[0].text.lower()
    assert isinstance(reply.content[-1], EndSessionContent)
    assert handler.usage.stats()["queries"] == 0


@pytest.mark.parametrize("prompt", ["@blr-air updates", "Remind me before my run"])
async def test_update_guidance_does_not_pretend_to_schedule_a_notification(tmp_path, prompt):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    await handler.on_chat(
        ctx,
        "agent-test",
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=prompt)],
        ),
    )
    text = ctx.sent[1].content[0].text
    assert "same full request" in text.lower()
    assert "5 minutes" in text
    assert "automatic alerts" in text.lower()
    assert "calendar" in text.lower()
    assert handler.usage.stats()["queries"] == 0


async def test_conversational_answer_keeps_acknowledgement_one_reply_and_end_session(tmp_path):
    class QuestionService:
        async def chat(self, text):
            assert text == "Explain photosynthesis"
            return "Plants use light energy to turn water and carbon dioxide into sugars."

    ctx = Context()
    handler = AgentHandlers(QuestionService(), Usage(tmp_path / "usage.sqlite", "salt"))
    incoming = ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="Explain photosynthesis")],
    )
    await handler.on_chat(ctx, "caller", incoming)
    assert len(ctx.sent) == 2
    assert isinstance(ctx.sent[0], ChatAcknowledgement)
    assert ctx.sent[0].acknowledged_msg_id == incoming.msg_id
    answer = ctx.sent[1]
    assert "Plants use light energy" in answer.content[0].text
    assert "Best available" not in answer.content[0].text
    assert isinstance(answer.content[-1], EndSessionContent)
    assert handler.usage.stats()["successful_queries"] == 1


async def test_different_questions_reach_the_model_and_receive_their_own_answers(tmp_path):
    import json

    import httpx

    from blr_air.service import AirService

    answers = {
        "Can you remind me what photosynthesis means?": "Plants turn light into chemical energy.",
        "Explain how apps notify me about messages": "Apps use push notifications.",
        "Write a sentence containing 'send me alerts'": "Please send me alerts about new books.",
        "What is 24 multiplied by 17?": "24 multiplied by 17 is 408.",
    }
    received = []

    def respond(request):
        question = json.loads(request.content)["messages"][-1]["content"]
        received.append(question)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"kind": "answer", "text": answers[question]})
                        }
                    }
                ]
            },
        )

    ctx = Context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        handler = AgentHandlers(
            AirService(None, client, api_key="test"), Usage(tmp_path / "usage.sqlite", "salt")
        )
        for question in answers:
            await handler.on_chat(
                ctx,
                "caller",
                ChatMessage(
                    timestamp=datetime.now(UTC),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text=question)],
                ),
            )
    assert received == list(answers)
    assert [
        message.content[0].text for message in ctx.sent if isinstance(message, ChatMessage)
    ] == list(answers.values())
    assert handler.usage.stats()["successful_queries"] == len(answers)


async def test_typed_provider_failure_returns_structured_error(tmp_path):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    await handler.on_window(ctx, "planner", WindowRequest(latitude=12.91, longitude=77.64))
    reply = ctx.sent[0]
    assert isinstance(reply, WindowResponse)
    assert reply.status == "error" and reply.error_code == "provider_unavailable"
    assert reply.start is None and reply.us_aqi is None


async def test_typed_comparison_returns_ranked_places(tmp_path):
    import httpx

    from blr_air.demo import DemoProvider
    from blr_air.service import AirService

    ctx = Context()
    async with httpx.AsyncClient() as client:
        handler = AgentHandlers(
            AirService(DemoProvider(), client), Usage(tmp_path / "usage.sqlite", "test-salt")
        )
        await handler.on_compare(
            ctx, "planner", ComparisonRequest(places=["HSR Layout", "Whitefield"])
        )
    reply = ctx.sent[0]
    assert isinstance(reply, ComparisonResponse)
    assert reply.status == "ok" and reply.winner == "HSR Layout"
    assert [item.place for item in reply.results] == ["HSR Layout", "Whitefield"]
    assert reply.results[0].backups[0].start
    assert reply.results[0].source == "Synthetic offline demo"


async def test_typed_plan_exposes_assessment_and_venue_status(tmp_path):
    import httpx

    from blr_air.demo import DemoProvider
    from blr_air.models import DetailedPlanRequest
    from blr_air.service import AirService
    from blr_air.venues import GooglePlaces

    ctx = Context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(403))
    ) as client:
        handler = AgentHandlers(
            AirService(DemoProvider(), client, venues=GooglePlaces(client, "test")),
            Usage(tmp_path / "usage.sqlite", "test-salt"),
        )
        await handler.on_compare(
            ctx, "planner", DetailedPlanRequest(places=["Cubbon Park"], include_venue=True)
        )
    item = ctx.sent[0].results[0]
    assert item.assessment and item.assessment["aqi"]["category"]
    assert item.venue and item.venue["status"] == "unavailable"


async def test_single_place_plan_enforces_limits(tmp_path):
    import httpx

    from blr_air.demo import DemoProvider
    from blr_air.models import PlanRequest
    from blr_air.service import AirService

    ctx = Context()
    async with httpx.AsyncClient() as client:
        handler = AgentHandlers(
            AirService(DemoProvider(), client), Usage(tmp_path / "usage.sqlite", "test-salt")
        )
        await handler.on_compare(ctx, "planner", PlanRequest(places=["HSR Layout"], max_aqi=1))
    assert ctx.sent[0].status == "error"
    assert ctx.sent[0].results == []


async def test_chat_review_request_returns_aqi_guidance_and_honest_provider_failure(tmp_path):
    import httpx

    from blr_air.demo import DemoProvider
    from blr_air.service import AirService
    from blr_air.venues import GooglePlaces

    ctx = Context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(403))
    ) as client:
        handler = AgentHandlers(
            AirService(DemoProvider(), client, venues=GooglePlaces(client, "test")),
            Usage(tmp_path / "usage.sqlite", "salt"),
        )
        await handler.on_chat(
            ctx,
            "caller",
            ChatMessage(
                timestamp=datetime.now(UTC),
                msg_id=uuid4(),
                content=[
                    TextContent(
                        type="text",
                        text="walk in Cubbon Park tomorrow with reviews and AQI at most 150",
                    )
                ],
            ),
        )
    assert isinstance(ctx.sent[0], ChatAcknowledgement)
    text = ctx.sent[1].content[0].text
    assert "AQI" in text and "Backup" in text
    assert "Google Places access was denied" in text
    assert "synthetic" in text.lower()
    assert isinstance(ctx.sent[1].content[-1], EndSessionContent)


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": 91},
        {"longitude": -181},
        {"hours": 3},
        {"hours": True},
        {"latitude": float("nan")},
        {"hours": "2"},
    ],
)
def test_typed_contract_validates_coordinates_and_duration(overrides):
    with pytest.raises(ValidationError):
        WindowRequest(**{"latitude": 12.91, "longitude": 77.64, **overrides})


def test_usage_persists_counts_without_storing_raw_sender_or_prompt(tmp_path):
    path = tmp_path / "usage.sqlite"
    usage = Usage(path, "a-secret-salt")
    usage.track("real-user-address", success=True, channel="chat")
    usage.track("real-user-address", success=False, channel="chat")
    usage.track("planner-address", success=True, channel="typed")
    assert Usage(path, "a-secret-salt").stats() == {
        "queries": 3,
        "successful_queries": 2,
        "failed_queries": 1,
        "unique_senders": 2,
        "chat_queries": 2,
        "typed_queries": 1,
    }
    assert b"real-user-address" not in path.read_bytes()
