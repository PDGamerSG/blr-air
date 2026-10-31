import asyncio
import json
from uuid import uuid4

from uagents import Protocol
from uagents_core.models import Model

from blr_air.agent_runtime import LocalRegistration
from blr_air.models import WindowRequest
from blr_air.transport import ResilientAgent


async def test_malformed_message_returns_error_and_does_not_kill_message_queue(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    agent = ResilientAgent(
        name="test",
        seed="disposable-test-identity",
        port=0,
        registration_policy=LocalRegistration(),
        enable_agent_inspector=False,
        publish_agent_details=False,
        report_events=False,
    )
    errors = []
    completed = asyncio.Event()
    received = []

    class ErrorContext:
        async def send_raw(self, **kwargs):
            errors.append(json.loads(kwargs["message_body"]))

    monkeypatch.setattr(agent, "_build_context", lambda: ErrorContext())
    protocol = Protocol(name="test")

    @protocol.on_message(model=WindowRequest)
    async def handle(ctx, sender, msg):
        received.append(msg.hours)
        completed.set()

    agent.include(protocol, publish_manifest=False)
    digest = Model.build_schema_digest(WindowRequest)
    await agent._message_queue.put(
        (digest, agent.address, '{"latitude":12.9,"longitude":77.6,"hours":3}', uuid4())
    )
    await agent._message_queue.put(
        (digest, agent.address, '{"latitude":12.9,"longitude":77.6,"hours":1}', uuid4())
    )
    task = asyncio.create_task(agent._process_message_queue())
    try:
        await asyncio.wait_for(completed.wait(), timeout=2)
        assert not task.done()
        assert received == [1]
        assert len(errors) == 1 and "schema" in errors[0]["error"].lower()
    finally:
        task.cancel()
        await task
