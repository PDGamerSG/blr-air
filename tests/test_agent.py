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
from blr_air.models import WindowRequest, WindowResponse
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


async def test_typed_provider_failure_returns_structured_error(tmp_path):
    ctx = Context()
    handler = AgentHandlers(BrokenService(), Usage(tmp_path / "usage.sqlite", "test-salt"))
    await handler.on_window(ctx, "planner", WindowRequest(latitude=12.91, longitude=77.64))
    reply = ctx.sent[0]
    assert isinstance(reply, WindowResponse)
    assert reply.status == "error" and reply.error_code == "provider_unavailable"
    assert reply.start is None and reply.us_aqi is None


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
