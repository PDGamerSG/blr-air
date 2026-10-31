import argparse
import os
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.registration import AgentRegistrationPolicy

from blr_air.domain import AirError, Location, NoWindowError, ProviderError, RequestSpec
from blr_air.models import (
    ComparisonRequest,
    ComparisonResponse,
    HealthResponse,
    PlaceComparison,
    WindowOption,
    WindowRequest,
    WindowResponse,
)
from blr_air.providers import OpenMeteo
from blr_air.service import (
    SOURCE,
    AirService,
    ComparisonItem,
    ComparisonResult,
    describe,
    window_dict,
)
from blr_air.telemetry import Usage
from blr_air.transport import ResilientAgent


class AgentHandlers:
    def __init__(self, service: AirService, usage: Usage):
        self.service = service
        self.usage = usage
        self.seen = deque(maxlen=256)

    def track(self, ctx, sender, success, channel):
        try:
            self.usage.track(sender, success=success, channel=channel)
        except Exception:
            ctx.logger.exception("Usage counter unavailable")

    async def on_chat(self, ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(
            sender, ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id)
        )
        key = (sender, msg.msg_id)
        if key in self.seen:
            return
        self.seen.append(key)
        text = " ".join(part.text for part in msg.content if isinstance(part, TextContent)).strip()
        if not text and any(isinstance(part, EndSessionContent) for part in msg.content):
            return
        success = False
        if not text:
            reply = (
                "Ask me: 'best 1-hour window to run in HSR Layout'. I also support other cities."
            )
        else:
            try:
                result = await self.service.chat(text)
                reply = describe(result)
                success = not isinstance(result, ComparisonResult) or result.winner is not None
            except AirError as exc:
                reply = str(exc)
            except Exception:
                ctx.logger.exception("Chat request failed")
                reply = "I couldn't complete that forecast lookup. Please try again in a minute."
            self.track(ctx, sender, success, "chat")
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(UTC),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=reply),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )

    async def on_ack(self, ctx: Context, sender: str, msg: ChatAcknowledgement):
        return

    async def on_window(self, ctx: Context, sender: str, req: WindowRequest):
        try:
            request = RequestSpec(
                hours=req.hours, activity=req.activity, day=req.day, period=req.period
            )
            location = Location(
                f"{req.latitude:.4f}, {req.longitude:.4f}", req.latitude, req.longitude
            )
            result = await self.service.recommend(request, location=location)
            window = result.window
            reply = WindowResponse(
                status="ok",
                summary=describe(result),
                start=window.start.isoformat(),
                end=window.end.isoformat(),
                timezone=result.forecast.timezone,
                us_aqi=window.us_aqi,
                pm2_5=window.pm2_5,
                rain_probability=window.rain_probability,
                temperature=window.temperature,
                max_aqi=window.max_aqi,
                fetched_at=result.forecast.fetched_at.isoformat(),
                source=SOURCE,
            )
        except AirError as exc:
            code = (
                "no_window"
                if isinstance(exc, NoWindowError)
                else "provider_unavailable"
                if isinstance(exc, ProviderError)
                else "invalid_request"
            )
            reply = WindowResponse(status="error", summary=str(exc), error_code=code)
        except Exception:
            ctx.logger.exception("Typed request failed")
            reply = WindowResponse(
                status="error",
                summary="Forecast lookup failed. Please retry.",
                error_code="internal_error",
            )
        self.track(ctx, sender, reply.status == "ok", "typed")
        await ctx.send(sender, reply)

    async def on_compare(self, ctx: Context, sender: str, req: ComparisonRequest):
        try:
            request = RequestSpec.model_validate({**req.dict(), "place": req.places[0]})
            if len(req.places) == 1:
                recommendation = await self.service.recommend(request)
                result = ComparisonResult(request, (ComparisonItem(req.places[0], recommendation),))
            else:
                result = await self.service.compare(request, req.places)
            ranked = {
                item.place: rank
                for rank, item in enumerate(result.items, start=1)
                if item.recommendation is not None
            }
            results = []
            for item in result.items:
                if item.recommendation is None:
                    results.append(
                        PlaceComparison(
                            place=item.place,
                            status="error",
                            summary=item.error or "Forecast unavailable",
                            error_code="lookup_failed",
                        )
                    )
                    continue
                recommendation = item.recommendation
                data = recommendation.to_dict()
                results.append(
                    PlaceComparison(
                        place=item.place,
                        status="ok",
                        summary=describe(recommendation),
                        rank=ranked[item.place],
                        resolved_name=recommendation.location.name,
                        timezone=recommendation.forecast.timezone,
                        window=WindowOption(**window_dict(recommendation.window)),
                        backups=[
                            WindowOption(**window_dict(backup)) for backup in recommendation.backups
                        ],
                        fetched_at=data["fetched_at"],
                        source=data["source"],
                    )
                )
            reply = ComparisonResponse(
                status="ok" if result.winner else "error",
                summary=describe(result),
                winner=result.winner,
                results=results,
                partial=any(item.error for item in result.items),
                tied_places=result.tied_places,
            )
        except AirError as exc:
            reply = ComparisonResponse(status="error", summary=str(exc), error_code="no_plan")
        except Exception:
            ctx.logger.exception("Comparison request failed")
            reply = ComparisonResponse(
                status="error",
                summary="Planning failed. Please try again.",
                error_code="comparison_failed",
            )
        self.track(ctx, sender, reply.status == "ok", "typed")
        await ctx.send(sender, reply)


class LocalRegistration(AgentRegistrationPolicy):
    """Local development must not register or publish an agent."""

    async def register(self, *args, **kwargs):
        return


def create_agent(
    seed: str, *, port=8001, local=False, data_dir=Path("data"), resolver=None
) -> Agent:
    client = httpx.AsyncClient()
    service = AirService(
        OpenMeteo(client),
        client,
        api_key=os.getenv("ASI1_API_KEY"),
        base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
    )
    handlers = AgentHandlers(service, Usage(data_dir / "usage.sqlite", seed))
    readme = Path(__file__).with_name("AGENT_README.md")
    agent = ResilientAgent(
        name="blr-air",
        seed=seed,
        port=port,
        mailbox=not local,
        endpoint=f"http://127.0.0.1:{port}/submit" if local else None,
        registration_policy=LocalRegistration() if local else None,
        resolve=resolver,
        readme_path=str(readme),
        publish_agent_details=not local,
        enable_agent_inspector=not local,
        store_message_history=False,
        report_events=not local,
        mark_inactive_on_shutdown=not local,
        description="Best outdoor window by AQI, PM2.5, rain and heat in Bengaluru or any city.",
    )
    chat = Protocol(spec=chat_protocol_spec)
    chat.on_message(ChatMessage)(handlers.on_chat)
    chat.on_message(ChatAcknowledgement)(handlers.on_ack)
    api = Protocol(name="blr-air-window", version="0.1.0")
    api.on_message(model=WindowRequest, replies=WindowResponse)(handlers.on_window)
    planning = Protocol(name="blr-air-plan", version="0.1.0")
    planning.on_message(model=ComparisonRequest, replies=ComparisonResponse)(handlers.on_compare)
    agent.include(chat, publish_manifest=not local)
    agent.include(api, publish_manifest=not local)
    agent.include(planning, publish_manifest=not local)

    @agent.on_rest_get("/healthz", HealthResponse)
    async def health(ctx: Context):
        return HealthResponse(address=agent.address, mode="local" if local else "mailbox")

    @agent.on_event("shutdown")
    async def shutdown(ctx: Context):
        await client.aclose()

    @agent.on_event("startup")
    async def startup(ctx: Context):
        ctx.logger.info(
            "BLR Air ready at %s; %s mode",
            agent.address,
            "local" if local else "mailbox (connect Inspector to Agentverse)",
        )

    return agent


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the BLR Air uAgent")
    parser.add_argument(
        "--local", action="store_true", help="Direct local HTTP; skip public registration"
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("AGENT_PORT", "8001")))
    args = parser.parse_args()
    seed = os.getenv("AGENT_SEED_PHRASE")
    if not seed:
        parser.error("Missing AGENT_SEED_PHRASE. Run python -m blr_air init first.")
    create_agent(
        seed, port=args.port, local=args.local, data_dir=Path(os.getenv("DATA_DIR", "data"))
    ).run()
