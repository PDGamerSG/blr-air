"""Opt-in checks against real APIs and local uAgents HTTP transports.

Run from the repository after `uv sync --extra dev`:
    uv run python scripts/check_live.py --run-live

Requires the existing Docker agent at 127.0.0.1:8001 and an ASI1_API_KEY in
.env/environment. These checks make real API requests and increment Docker usage
counters. They never modify identities, register an agent publicly, stop Docker,
or count local development calls as outside-user evidence. The separate chat
agent has a disposable identity, working directory, SQLite database, and ports.
"""

import argparse
import asyncio
import json
import os
import signal
import socket
import sqlite3
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from aiohttp import web
from dotenv import load_dotenv
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
)
from uagents_core.envelope import Envelope
from uagents_core.identity import Identity
from uagents_core.models import ERROR_MESSAGE_DIGEST, Model

from blr_air.domain import AirError, LocationError, RequestSpec
from blr_air.models import PlanRequest, PlanResponse, WindowRequest, WindowResponse
from blr_air.parsing import parse_local, parse_request
from blr_air.providers import AIR_URL, GEOCODING_URL, WEATHER_URL, OpenMeteo
from blr_air.service import SOURCE, AirService

ROOT = Path(__file__).resolve().parents[1]
V1_SCHEMA_DIGESTS = {
    WindowRequest: "model:0120780fa23b79594e5351f987e35d8d33245c1f39144acef9781a9a342267c2",
    WindowResponse: "model:6479714ec5e5c0d5a82fe621b1f884ddb8ea192f5e2f54746c7dabecbe350cb1",
}
PERIODS = {"any": (5, 21), "morning": (5, 12), "afternoon": (12, 17), "evening": (17, 21)}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stats_from_sqlite(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        counts = dict(db.execute("SELECT name, value FROM counts"))
        senders = db.execute("SELECT COUNT(*) FROM senders").fetchone()[0]
    return {
        **{
            name: counts.get(name, 0)
            for name in (
                "queries",
                "successful_queries",
                "failed_queries",
                "chat_queries",
                "typed_queries",
            )
        },
        "unique_senders": senders,
    }


async def docker_stats():
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "exec",
        "-T",
        "agent",
        "blr-air",
        "stats",
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), 15)
    require(proc.returncode == 0, "Docker aggregate-counter command failed")
    return json.loads(stdout)


def make_envelope(identity, target, message, *, session=None, raw=None):
    env = Envelope(
        version=1,
        sender=identity.address,
        target=target,
        session=session or uuid4(),
        schema_digest=Model.build_schema_digest(message),
        expires=int(time.time()) + 35,
    )
    env.encode_payload(raw if raw is not None else message.model_dump_json())
    env.sign(identity)
    require(env.verify(), "Outgoing envelope signature did not verify")
    return env


async def post_envelope(client, endpoint, env, *, sync=False):
    headers = {"content-type": "application/json"}
    if sync:
        headers["x-uagents-connection"] = "sync"
    response = await client.post(
        endpoint, content=env.model_dump_json(), headers=headers, timeout=38
    )
    response.raise_for_status()
    return response


def verify_window(start, end, timezone, request, now):
    tz = ZoneInfo(timezone)
    require(
        start.utcoffset() is not None and end.utcoffset() is not None,
        "Returned window timestamps must include UTC offsets",
    )
    start, end = start.astimezone(tz), end.astimezone(tz)
    require(
        end.astimezone(UTC) - start.astimezone(UTC) == timedelta(hours=request.hours),
        "Returned duration differs from requested elapsed hours",
    )
    require(
        start >= now and end <= now + timedelta(hours=48),
        "Returned window lies outside the next 48 elapsed hours",
    )
    low, high = PERIODS[request.period]
    require(
        start.date() == end.date()
        and start.hour >= low
        and (end.hour < high or (end.hour == high and end.minute == 0)),
        "Returned window violates local activity/period hours",
    )
    if request.day != "next48":
        expected = now.astimezone(tz).date() + timedelta(days=request.day == "tomorrow")
        require(start.date() == expected, "Returned window violates requested local day")


def verify_plan(response, request, now):
    require(
        response.status == "ok" and not response.partial, "Plan returned an error or partial data"
    )
    require(len(response.results) == len(request.places), "Plan omitted a requested place")
    require(response.winner == response.results[0].place, "Plan winner differs from first rank")
    scores = []
    for rank, place in enumerate(response.results, start=1):
        require(
            place.status == "ok" and place.rank == rank and place.source == SOURCE,
            "Plan result status, rank or live source is incorrect",
        )
        require(place.timezone == "Asia/Kolkata", "Bengaluru plan returned a different timezone")
        require(
            bool(place.resolved_name) and bool(place.fetched_at),
            "Plan omitted resolved location or retrieval time",
        )
        require(1 <= len(place.backups) <= 2, "Broad plan did not return backup windows")
        intervals = []
        for option in [place.window, *place.backups]:
            require(option is not None, "Plan omitted its primary window")
            start, end = datetime.fromisoformat(option.start), datetime.fromisoformat(option.end)
            verify_window(start, end, place.timezone, request, now)
            for previous_start, previous_end in intervals:
                require(
                    end <= previous_start or start >= previous_end,
                    "Plan backup overlaps another returned window",
                )
            intervals.append((start, end))
            for field, maximum in (
                ("max_aqi", request.max_aqi),
                ("rain_probability", request.max_rain),
                ("apparent_temperature", request.max_temperature),
                ("uv_index", request.max_uv),
                ("wind_speed", request.max_wind),
            ):
                if maximum is not None:
                    value = getattr(option, field)
                    require(
                        value is not None and value <= maximum,
                        "Plan relaxed a requested hard limit or used missing data",
                    )
            if request.daylight_only:
                require(option.daylight is True, "Plan returned a window outside full daylight")
        require(
            place.window.score <= min(option.score for option in place.backups),
            "Plan backup outranks its chosen primary window",
        )
        scores.append(place.window.score)
    require(scores == sorted(scores), "Plan comparison is not ranked by score")


class LiveChecks:
    def __init__(self, endpoint):
        self.endpoint = endpoint.rstrip("/")
        self.report = {
            "started_at": datetime.now(UTC).isoformat(),
            "scope": "Local development verification; not outside-user or Agentverse evidence",
            "checks": [],
            "http": [],
            "limitations": [
                "Health is process liveness, not public Agentverse registration.",
                "The SDK's synchronous HTTP response envelope is unsigned; requests are signed.",
            ],
        }

    async def audit(self, response):
        self.report["http"].append(
            {
                "method": response.request.method,
                "host": response.request.url.host,
                "path": response.request.url.path,
                "status": response.status_code,
            }
        )

    async def check(self, name, operation):
        started = time.monotonic()
        self.partial = {}
        try:
            details = await asyncio.wait_for(operation(), 110)
            item = {"name": name, "status": "passed", "details": details or {}}
        except Exception as exc:
            # No response bodies, headers, raw environments, seeds or API keys enter evidence.
            item = {
                "name": name,
                "status": "failed",
                "error_type": type(exc).__name__,
                "completed_evidence": self.partial,
            }
            if isinstance(exc, (AssertionError, AirError)):
                item["reason"] = str(exc)
        item["duration_seconds"] = round(time.monotonic() - started, 3)
        self.report["checks"].append(item)
        print(f"{item['status'].upper():6} {name}", flush=True)

    async def asi_parsing(self):
        key = os.getenv("ASI1_API_KEY")
        require(bool(key), "ASI1_API_KEY is required to prove the live parser succeeds")
        async with httpx.AsyncClient(event_hooks={"response": [self.audit]}) as client:
            with patch(
                "blr_air.parsing.parse_local",
                side_effect=AssertionError("ASI parsing fell back to deterministic parsing"),
            ):
                result = await parse_request(
                    "कल सुबह HSR Layout में दो घंटे साइकिल चलाने का सबसे अच्छा समय बताइए।",
                    client,
                    api_key=key,
                    base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
                )
        require(result.place.casefold() == "hsr layout", "ASI did not retain the requested place")
        require(
            (result.activity, result.hours, result.day, result.period)
            == ("cycle", 2, "tomorrow", "morning"),
            "ASI extracted different constraints",
        )
        return {
            "model": "asi1-mini",
            "language": "Hindi",
            "fallback_forbidden": True,
            "parsed": result.model_dump(),
        }

    async def recommendations(self):
        results = []
        async with httpx.AsyncClient(event_hooks={"response": [self.audit]}) as client:
            provider = OpenMeteo(client)
            service = AirService(provider, client)
            # Non-Indian zones include the US DST transition when run on 31 October 2026.
            cases = [
                RequestSpec(place="HSR Layout", activity="run", hours=1),
                RequestSpec(
                    place="Koramangala", activity="cycle", hours=2, day="tomorrow", period="morning"
                ),
                RequestSpec(
                    place="Melbourne, Australia",
                    activity="kids",
                    hours=2,
                    day="tomorrow",
                    period="morning",
                ),
                RequestSpec(
                    place="New York, US",
                    activity="walk",
                    hours=1,
                    day="tomorrow",
                    period="afternoon",
                ),
                RequestSpec(
                    place="Paris, France",
                    activity="commute",
                    hours=2,
                    day="tomorrow",
                    period="evening",
                ),
            ]
            for request in cases:
                now = datetime.now(UTC)
                result = await service.recommend(request, now=now)
                require(
                    result.forecast.timezone
                    == {
                        "HSR Layout": "Asia/Kolkata",
                        "Koramangala": "Asia/Kolkata",
                        "Melbourne, Australia": "Australia/Melbourne",
                        "New York, US": "America/New_York",
                        "Paris, France": "Europe/Paris",
                    }[request.place],
                    "Global location returned an unexpected IANA timezone",
                )
                verify_window(
                    result.window.start, result.window.end, result.forecast.timezone, request, now
                )
                payload = result.to_dict()
                require(
                    payload["mode"] == "live" and payload["source"] == SOURCE,
                    "Recommendation is not attributed live Open-Meteo data",
                )
                require(
                    result.window.max_aqi >= result.window.us_aqi,
                    "Worst hourly AQI must be at least the average",
                )
                results.append(
                    {
                        "request": request.model_dump(),
                        "location": result.location.name,
                        "timezone": result.forecast.timezone,
                        "window": payload["window"],
                        "fetched_at": payload["fetched_at"],
                        "source": payload["source"],
                        "complete_forecast_hours": len(result.forecast.hours),
                    }
                )
            calls_before_cache = len(self.report["http"])
            await service.recommend(cases[0])
            require(
                len(self.report["http"]) == calls_before_cache,
                "Repeated locality forecast did not use its fresh cache",
            )
        expected = {str(httpx.URL(url).host) for url in (AIR_URL, WEATHER_URL, GEOCODING_URL)}
        successful = {r["host"] for r in self.report["http"] if r["status"] == 200}
        require(expected <= successful, "One or more Open-Meteo APIs did not return HTTP 200")
        return {"cases": results, "all_three_open_meteo_apis": "HTTP 200", "cache_hit": True}

    async def invalid_requests(self):
        try:
            parse_local("best 3-hour window to run in HSR Layout")
        except AirError as exc:
            duration_reason = str(exc)
        else:
            raise AssertionError("Unsupported duration was accepted")
        async with httpx.AsyncClient(event_hooks={"response": [self.audit]}) as client:
            service = AirService(OpenMeteo(client), client)
            try:
                await service.recommend(RequestSpec(place="Zzxqvnotarealcity729"))
            except LocationError as exc:
                place_reason = str(exc)
            else:
                raise AssertionError("Unknown place was silently replaced with a location")
        return {"duration_error": duration_reason, "place_error": place_reason}

    async def docker_typed(self):
        before = await docker_stats()
        identity = Identity.generate()
        async with httpx.AsyncClient(event_hooks={"response": [self.audit]}) as client:
            health = await client.get(self.endpoint + "/healthz", timeout=5)
            health.raise_for_status()
            body = health.json()
            require(
                body["status"] == "ok" and body["mode"] == "mailbox",
                "Expected the existing healthy Docker mailbox agent",
            )
            target = body["address"]
            request = WindowRequest(
                latitude=12.9116,
                longitude=77.6389,
                hours=2,
                day="tomorrow",
                period="morning",
                activity="run",
            )
            now = datetime.now(UTC)
            env = make_envelope(identity, target, request)
            response = await post_envelope(client, self.endpoint + "/submit", env, sync=True)
            reply = Envelope.model_validate(response.json())
            require(
                reply.schema_digest == Model.build_schema_digest(WindowResponse),
                "Docker returned a different wire schema",
            )
            require(
                reply.sender == target
                and reply.target == identity.address
                and reply.session == env.session,
                "Docker reply envelope correlation failed",
            )
            result = WindowResponse.model_validate_json(reply.decode_payload())
            require(result.status == "ok", "Docker typed recommendation returned an error")
            verify_window(
                datetime.fromisoformat(result.start),
                datetime.fromisoformat(result.end),
                result.timezone,
                request,
                now,
            )
            require(result.source == SOURCE, "Docker response is not attributed to live data")
        after = await docker_stats()
        require(
            after["queries"] >= before["queries"] + 1
            and after["successful_queries"] >= before["successful_queries"] + 1
            and after["typed_queries"] >= before["typed_queries"] + 1,
            "Docker aggregate counters did not record the valid typed request",
        )
        return {
            "health": body,
            "request_signature_verified": True,
            "response_signature_present": bool(reply.signature),
            "response": result.model_dump(),
            "counters_before": before,
            "counters_after": after,
        }

    async def full_chat(self):
        for model, expected in V1_SCHEMA_DIGESTS.items():
            require(Model.build_schema_digest(model) == expected, "Legacy v1 schema digest changed")
        identity = Identity.generate()
        queue = asyncio.Queue()
        target = {"address": None}

        async def receive(request):
            try:
                env = Envelope.model_validate(await request.json())
                require(env.verify(), "Callback envelope signature did not verify")
                require(
                    env.sender == target["address"] and env.target == identity.address,
                    "Callback envelope sender/target mismatch",
                )
                await queue.put(env)
                return web.json_response({})
            except Exception as exc:
                await queue.put(exc)
                return web.json_response({"error": "Invalid signed callback"}, status=400)

        app = web.Application(client_max_size=32768)
        app.router.add_post("/submit", receive)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        receiver_port = free_port()
        await web.TCPSite(runner, "127.0.0.1", receiver_port).start()
        agent_port = free_port()
        process = None
        temporary = tempfile.TemporaryDirectory(prefix="blr-air-live-")
        try:
            work = Path(temporary.name)
            environment = os.environ.copy()
            for name in ("AGENT_SEED_PHRASE", "CALLER_SEED", "BLR_AIR_ADDRESS", "DATA_DIR"):
                environment.pop(name, None)
            environment["PYTHONPATH"] = str(ROOT)
            with (work / "agent.log").open("wb") as output:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(ROOT / "tests/support/local_agent.py"),
                    "--port",
                    str(agent_port),
                    "--receiver-address",
                    identity.address,
                    "--receiver-endpoint",
                    f"http://127.0.0.1:{receiver_port}/submit",
                    "--data-dir",
                    str(work / "data"),
                    cwd=work,
                    env=environment,
                    stdout=output,
                    stderr=output,
                )
                async with httpx.AsyncClient(event_hooks={"response": [self.audit]}) as client:
                    endpoint = f"http://127.0.0.1:{agent_port}"
                    deadline = time.monotonic() + 10
                    health = None
                    while time.monotonic() < deadline:
                        if process.returncode is not None:
                            raise AssertionError("Isolated local agent exited during startup")
                        try:
                            response = await client.get(endpoint + "/healthz", timeout=0.5)
                            if response.status_code == 200:
                                health = response.json()
                                break
                        except httpx.RequestError:
                            pass
                        await asyncio.sleep(0.1)
                    require(
                        health and health["mode"] == "local",
                        "Isolated local agent did not become healthy in 10 seconds",
                    )
                    target["address"] = health["address"]

                    async def next_message(expected, session):
                        received = await asyncio.wait_for(queue.get(), 35)
                        if isinstance(received, Exception):
                            raise received
                        require(received.session == session, "Callback session mismatch")
                        require(
                            received.schema_digest == Model.build_schema_digest(expected),
                            "Callback type/order differs from the chat protocol",
                        )
                        return expected.model_validate_json(received.decode_payload())

                    async def chat(text):
                        msg = ChatMessage(
                            timestamp=datetime.now(UTC),
                            msg_id=uuid4(),
                            content=[TextContent(type="text", text=text)],
                        )
                        env = make_envelope(identity, target["address"], msg)
                        await post_envelope(client, endpoint + "/submit", env)
                        ack = await next_message(ChatAcknowledgement, env.session)
                        require(
                            ack.acknowledged_msg_id == msg.msg_id,
                            "Chat acknowledgement refers to a different message",
                        )
                        answer = await next_message(ChatMessage, env.session)
                        require(
                            any(isinstance(part, EndSessionContent) for part in answer.content),
                            "Chat response did not contain EndSessionContent",
                        )
                        text = "\n".join(
                            part.text for part in answer.content if isinstance(part, TextContent)
                        )
                        require(bool(text), "Chat did not return a text answer")
                        return msg, text

                    valid, answer = await chat("best 1-hour window to run in HSR Layout")
                    require(
                        "Best available" in answer and "Open-Meteo" in answer,
                        "Chat did not return a successful live recommendation",
                    )
                    self.partial["successful_chat_ack_text_end_session"] = True
                    _, duration_error = await chat("best 3-hour window to run in HSR Layout")
                    require(
                        "1" in duration_error and "2" in duration_error,
                        "Chat did not explain its unsupported duration",
                    )
                    self.partial["invalid_duration_reply"] = duration_error
                    _, place_error = await chat("best window in Zzxqvnotarealcity729")
                    require(
                        "couldn't find" in place_error,
                        "Unknown-place chat did not return the expected error: " + place_error,
                    )
                    self.partial["invalid_place_reply"] = place_error
                    duplicate = make_envelope(identity, target["address"], valid)
                    await post_envelope(client, endpoint + "/submit", duplicate)
                    await next_message(ChatAcknowledgement, duplicate.session)
                    ending = ChatMessage(
                        timestamp=datetime.now(UTC),
                        msg_id=uuid4(),
                        content=[EndSessionContent(type="end-session")],
                    )
                    end_env = make_envelope(identity, target["address"], ending)
                    await post_envelope(client, endpoint + "/submit", end_env)
                    await next_message(ChatAcknowledgement, end_env.session)
                    ack = ChatAcknowledgement(
                        timestamp=datetime.now(UTC), acknowledged_msg_id=uuid4()
                    )
                    await post_envelope(
                        client,
                        endpoint + "/submit",
                        make_envelope(identity, target["address"], ack),
                    )
                    # A serially processed typed response is a barrier: previous no-reply
                    # handlers have completed, avoiding arbitrary sleeps to infer silence.
                    typed = WindowRequest(latitude=12.9116, longitude=77.6389)
                    barrier = make_envelope(identity, target["address"], typed)
                    await post_envelope(client, endpoint + "/submit", barrier)
                    typed_answer = await next_message(WindowResponse, barrier.session)
                    require(typed_answer.status == "ok", "Local typed barrier failed")
                    require(queue.empty(), "Duplicate/end/ack created an extra reply")
                    counters = stats_from_sqlite(work / "data/usage.sqlite")
                    require(
                        counters
                        == {
                            "queries": 4,
                            "successful_queries": 2,
                            "failed_queries": 2,
                            "chat_queries": 3,
                            "typed_queries": 1,
                            "unique_senders": 1,
                        },
                        "Chat counters include duplicates, acknowledgements or termination",
                    )
                    require(
                        identity.address.encode() not in (work / "data/usage.sqlite").read_bytes(),
                        "Usage SQLite stored the raw sender address",
                    )
                    self.partial["chat_counters"] = counters
                    invalid = make_envelope(
                        identity,
                        target["address"],
                        typed,
                        raw=json.dumps({**typed.model_dump(), "hours": 3}),
                    )
                    # Probe malformed wire input only on the disposable agent: an SDK
                    # regression must not kill the production message queue.
                    invalid.expires = int(time.time()) + 5
                    invalid.sign(identity)
                    response = await post_envelope(client, endpoint + "/submit", invalid, sync=True)
                    error = Envelope.model_validate(response.json())
                    error_text = json.loads(error.decode_payload()).get("error", "")
                    require(
                        error.schema_digest == ERROR_MESSAGE_DIGEST,
                        "Invalid duration did not return a wire error",
                    )
                    require(
                        "does not conform" in error_text,
                        "Invalid wire duration response: " + error_text,
                    )
                    recovery = make_envelope(identity, target["address"], typed)
                    await post_envelope(client, endpoint + "/submit", recovery)
                    recovered = await next_message(WindowResponse, recovery.session)
                    require(
                        recovered.status == "ok",
                        "Message queue did not recover after malformed input",
                    )
                    counters = stats_from_sqlite(work / "data/usage.sqlite")
                    require(
                        counters["queries"] == 5 and counters["typed_queries"] == 2,
                        "Malformed wire input was counted as a valid query",
                    )
                    plans = []
                    for request in (
                        PlanRequest(
                            places=["HSR Layout"],
                            hours=2,
                            daylight_only=True,
                            max_aqi=500,
                            max_rain=100,
                            max_temperature=70,
                            max_uv=30,
                            max_wind=200,
                        ),
                        PlanRequest(places=["HSR Layout", "Whitefield"], daylight_only=True),
                    ):
                        now = datetime.now(UTC)
                        plan_env = make_envelope(identity, target["address"], request)
                        await post_envelope(client, endpoint + "/submit", plan_env)
                        plan = await next_message(PlanResponse, plan_env.session)
                        verify_plan(plan, request, now)
                        plans.append(
                            {"request": request.model_dump(), "response": plan.model_dump()}
                        )
                    self.partial["plans"] = plans
                    impossible = PlanRequest(places=["HSR Layout"], max_temperature=-80)
                    impossible_env = make_envelope(identity, target["address"], impossible)
                    await post_envelope(client, endpoint + "/submit", impossible_env)
                    impossible_reply = await next_message(PlanResponse, impossible_env.session)
                    require(
                        impossible_reply.status == "error"
                        and impossible_reply.winner is None
                        and not impossible_reply.results,
                        "An impossible hard limit was relaxed instead of refusing the plan",
                    )
                    legacy_env = make_envelope(identity, target["address"], typed)
                    await post_envelope(client, endpoint + "/submit", legacy_env)
                    legacy = await next_message(WindowResponse, legacy_env.session)
                    require(legacy.status == "ok", "Legacy v1 request failed after plan requests")
                    counters = stats_from_sqlite(work / "data/usage.sqlite")
                    require(
                        counters
                        == {
                            "queries": 9,
                            "successful_queries": 6,
                            "failed_queries": 3,
                            "chat_queries": 3,
                            "typed_queries": 6,
                            "unique_senders": 1,
                        },
                        "Plan/legacy responses were not reflected in usage counters",
                    )
                await stop_process(process)
                process = None
            return {
                "mode": "isolated-local",
                "all_callback_signatures_verified": True,
                "acknowledgement_then_text_then_end_session": True,
                "duplicate_end_only_ack_do_not_loop": True,
                "invalid_duration_reply": duration_error,
                "invalid_place_reply": place_error,
                "counters": counters,
                "raw_sender_not_persisted": True,
                "invalid_wire_duration_rejected_and_queue_survives": True,
                "plans": plans,
                "hard_limit_no_plan": impossible_reply.model_dump(),
                "v1_schema_digests_unchanged": True,
                "v1_request_passed_after_plan_requests": True,
            }
        finally:
            if process is not None:
                await stop_process(process)
            await runner.cleanup()
            temporary.cleanup()


async def stop_process(process):
    if process.returncode is None:
        process.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.wait(), 5)


async def main(args):
    load_dotenv(ROOT / ".env", override=False)
    checks = LiveChecks(args.endpoint)
    for name, operation in (
        ("asi_live_multilingual_no_fallback", checks.asi_parsing),
        ("open_meteo_recommendations_and_constraints", checks.recommendations),
        ("invalid_place_and_duration", checks.invalid_requests),
        ("docker_signed_typed_request_and_counters", checks.docker_typed),
        ("full_signed_chat_plan_callbacks_and_counters", checks.full_chat),
    ):
        await checks.check(name, operation)
    checks.report["finished_at"] = datetime.now(UTC).isoformat()
    checks.report["status"] = (
        "passed"
        if all(item["status"] == "passed" for item in checks.report["checks"])
        else "failed"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(checks.report, ensure_ascii=False, indent=2) + "\n")
    print(f"Sanitized evidence: {args.report}")
    return 0 if checks.report["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-live",
        action="store_true",
        help="Opt in to real APIs and incrementing local Docker usage counters",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8001")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/live-checks.json")
    arguments = parser.parse_args()
    if not arguments.run_live:
        parser.error("Pass --run-live to explicitly enable network and local agent checks")
    try:
        sys.exit(asyncio.run(main(arguments)))
    except KeyboardInterrupt:
        sys.exit(130)
