"""Same-origin website API. Provider credentials never enter the browser bundle."""

import argparse
import asyncio
import json
import logging
import os
import secrets
import tempfile
import time
from collections import OrderedDict, deque
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from aiohttp import web
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from blr_air.calendar_export import write_calendar
from blr_air.domain import AirError, ProviderError, RequestSpec
from blr_air.parsing import parse_request
from blr_air.providers import OpenMeteo
from blr_air.service import AirService, ComparisonResult, spoken_summary
from blr_air.venues import GooglePlaces
from blr_air.voice import MAX_INPUT_BYTES, SarvamVoice

LOG = logging.getLogger(__name__)


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str | None = Field(default=None, min_length=1, max_length=2000)
    request: RequestSpec | None = None
    include_venue: bool = Field(default=False, strict=True)
    venue_query: str | None = Field(default=None, min_length=2, max_length=160)

    @model_validator(mode="after")
    def one_input(self):
        if (self.query is None) == (self.request is None):
            raise ValueError("Provide either a text query or structured request.")
        return self


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=100)
    place_index: int = Field(default=0, ge=0, le=2, strict=True)
    window_index: int = Field(default=0, ge=0, le=2, strict=True)


class PlanStore:
    def __init__(self, ttl=900, capacity=128):
        self.ttl, self.capacity = ttl, capacity
        self.entries = OrderedDict()

    def put(self, result, *, now=None):
        now = now or datetime.now(UTC)
        self.entries = OrderedDict((k, v) for k, v in self.entries.items() if v[0] > now)
        while len(self.entries) >= self.capacity:
            self.entries.popitem(last=False)
        key, expires = secrets.token_urlsafe(32), now + timedelta(seconds=self.ttl)
        # Downloads need forecasts only. Do not retain customer review content in the store.
        if isinstance(result, ComparisonResult):
            result = replace(
                result,
                items=tuple(
                    replace(item, recommendation=replace(item.recommendation, venue=None))
                    if item.recommendation
                    else item
                    for item in result.items
                ),
            )
        elif hasattr(result, "venue"):
            result = replace(result, venue=None)
        self.entries[key] = (expires, result)
        return key, expires

    def get(self, key, *, now=None):
        expires, result = self.entries[key]
        if expires <= (now or datetime.now(UTC)):
            del self.entries[key]
            raise KeyError(key)
        return result


def create_app(*, service=None, voice=None, static_dir=None, rate_limit=30, venue_rate_limit=10):
    client = None
    if service is None:
        client = httpx.AsyncClient(follow_redirects=False)
        service = AirService(
            OpenMeteo(client),
            client,
            api_key=os.getenv("ASI1_API_KEY"),
            base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
            venues=GooglePlaces(client, os.getenv("GOOGLE_PLACES_API_KEY", "")),
        )
        if os.getenv("SARVAM_API_KEY"):
            voice = SarvamVoice(client, os.environ["SARVAM_API_KEY"])
    directory = Path(static_dir or os.getenv("SITE_DIR", "site/dist")).resolve()
    store, slots = PlanStore(), asyncio.Semaphore(4)
    traffic = OrderedDict()
    venue_traffic = OrderedDict()
    venue_global_traffic = deque()
    global_traffic = deque()

    @web.middleware
    async def guard(request, handler):
        if request.path.startswith("/api/"):
            if request.method == "POST":
                origin = request.headers.get("Origin")
                allowed = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
                if (
                    origin
                    and origin != allowed
                    and (
                        urlsplit(origin).netloc != request.host
                        or urlsplit(origin).scheme != request.scheme
                    )
                ):
                    return error("This website origin is not allowed.", 403)
                now = time.monotonic()
                key = request.remote or "unknown"
                while global_traffic and now - global_traffic[0] >= 60:
                    global_traffic.popleft()
                history = traffic.setdefault(key, deque())
                while history and now - history[0] >= 60:
                    history.popleft()
                if len(history) >= rate_limit or len(global_traffic) >= 120:
                    return error(
                        "Too many requests. Please wait a minute.", 429, {"Retry-After": "60"}
                    )
                history.append(now)
                global_traffic.append(now)
                traffic.move_to_end(key)
                if len(traffic) > 4096:
                    traffic.popitem(last=False)
            try:
                response = await handler(request)
            except (ValidationError, json.JSONDecodeError, UnicodeDecodeError):
                response = error(
                    "Invalid input. Use a short request, 1–2 hours, and valid limits.", 400
                )
            except web.HTTPException as exc:
                response = error(exc.reason, exc.status)
            except ProviderError as exc:
                response = error(str(exc), 502)
            except AirError as exc:
                response = error(str(exc), 422)
            except TimeoutError:
                response = error("The lookup took too long. Please try again.", 504)
            except Exception:
                LOG.exception("Website request failed")
                response = error("The request could not be completed. Please try again.", 500)
            response.headers["Cache-Control"] = "no-store"
        else:
            response = await handler(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "microphone=(self), geolocation=(self)"
        return response

    def error(message, status, headers=None):
        return web.json_response(
            {"status": "error", "error": message},
            status=status,
            headers={"Cache-Control": "no-store", **(headers or {})},
        )

    def reserve_venue_budget(request, lookups):
        """Bound paid venue searches separately from free forecast requests."""
        now = time.monotonic()
        key = request.remote or "unknown"
        while venue_global_traffic and now - venue_global_traffic[0] >= 60:
            venue_global_traffic.popleft()
        history = venue_traffic.setdefault(key, deque())
        while history and now - history[0] >= 60:
            history.popleft()
        if len(history) + lookups > venue_rate_limit or len(venue_global_traffic) + lookups > 60:
            return False
        history.extend([now] * lookups)
        venue_global_traffic.extend([now] * lookups)
        venue_traffic.move_to_end(key)
        if len(venue_traffic) > 4096:
            venue_traffic.popitem(last=False)
        return True

    async def json_body(request):
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(reason="Send application/json.")
        data = bytearray()
        async with asyncio.timeout(15):
            async for chunk in request.content.iter_chunked(8192):
                data.extend(chunk)
                if len(data) > 32768:
                    raise web.HTTPRequestEntityTooLarge(max_size=32768, actual_size=len(data))
        return json.loads(data)

    async def status(request):
        return web.json_response(
            {
                "status": "ok",
                "features": {
                    "language": bool(service.api_key),
                    "voice": voice is not None,
                    "venues": bool(service.venues and service.venues.api_key),
                    "calendar": True,
                    "comparisons": True,
                },
            }
        )

    async def plan(request):
        payload = PlanInput.model_validate(await json_body(request))
        if slots.locked():
            return error("The planner is busy. Please retry shortly.", 503, {"Retry-After": "5"})
        async with slots, asyncio.timeout(50):
            spec = payload.request or await parse_request(
                payload.query, service.client, api_key=service.api_key, base_url=service.base_url
            )
            if payload.include_venue or payload.venue_query:
                spec = spec.model_copy(update={"include_venue": True})
            if payload.venue_query:
                if len(spec.places) > 1:
                    raise AirError(
                        "Use the compared venue names in your request, "
                        "without a separate venue query."
                    )
                spec = spec.model_copy(update={"place": payload.venue_query, "places": []})
            if spec.include_venue and getattr(service.venues, "api_key", ""):
                venue_lookups = len(spec.places) if spec.places else 1
                if not reserve_venue_budget(request, venue_lookups):
                    return error(
                        "Venue lookups are temporarily limited because they use a paid provider. "
                        "Please retry later.",
                        429,
                        {"Retry-After": "60"},
                    )
            result = (
                await service.compare(spec, spec.places)
                if len(spec.places) > 1
                else await service.recommend(spec)
            )
            data = result.to_dict()
            if data["status"] == "ok":
                token, expires = store.put(result)
                data.update(plan_id=token, expires_at=expires.isoformat())
            return web.json_response(data, status=200 if data["status"] == "ok" else 422)

    def selected(selection):
        try:
            result = store.get(selection.plan_id)
        except KeyError:
            raise web.HTTPGone(
                reason="This plan expired. Run the request again for a fresh forecast."
            ) from None
        if isinstance(result, ComparisonResult):
            try:
                result = result.items[selection.place_index].recommendation
            except IndexError:
                result = None
        elif selection.place_index != 0:
            result = None
        if result is None:
            raise web.HTTPBadRequest(reason="That place has no available forecast.")
        try:
            window = (result.window, *result.backups)[selection.window_index]
        except IndexError:
            raise web.HTTPBadRequest(reason="That backup window is unavailable.") from None
        if window.start <= datetime.now(UTC):
            raise web.HTTPGone(reason="That window has started. Request an updated plan.")
        return replace(result, window=window, backups=())

    async def calendar(request):
        try:
            selection = Selection(
                plan_id=request.match_info["token"],
                place_index=int(request.query.get("place_index", 0)),
                window_index=int(request.query.get("window_index", 0)),
            )
        except ValueError:
            raise web.HTTPBadRequest(reason="Choose a valid place and window.") from None
        result = selected(selection)
        with tempfile.TemporaryDirectory(prefix="blr-calendar-") as folder:
            path = write_calendar(result, Path(folder) / "outdoor-window.ics")
            data = path.read_bytes()
        return web.Response(
            body=data,
            content_type="text/calendar",
            headers={"Content-Disposition": 'attachment; filename="outdoor-window.ics"'},
        )

    async def transcribe(request):
        if voice is None:
            return error("Voice is not configured on this server. Type your request instead.", 503)
        if request.content_type not in (
            "audio/wav",
            "audio/wave",
            "audio/x-wav",
            "application/octet-stream",
        ):
            raise web.HTTPUnsupportedMediaType(
                reason="Upload a PCM WAV recording of up to 30 seconds."
            )
        if slots.locked():
            return error("Voice is busy. Please retry shortly.", 503)
        async with slots, asyncio.timeout(70):
            data = await request.read()
            with tempfile.TemporaryDirectory(prefix="blr-speech-") as folder:
                path = Path(folder) / "request.wav"
                path.write_bytes(data)
                transcript = await voice.transcribe(path)
            return web.json_response({"transcript": transcript})

    async def speech(request):
        if voice is None:
            return error(
                "Speech is not configured on this server. The written answer is available.", 503
            )
        selection = Selection.model_validate(await json_body(request))
        result = selected(selection)
        if slots.locked():
            return error("Speech is busy. Please retry shortly.", 503)
        async with slots, asyncio.timeout(70):
            with tempfile.TemporaryDirectory(prefix="blr-answer-") as folder:
                path = await voice.synthesize(spoken_summary(result), Path(folder) / "answer.wav")
                data = path.read_bytes()
        return web.Response(
            body=data,
            content_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="outdoor-answer.wav"'},
        )

    async def static(request):
        part = request.match_info.get("path", "") or "index.html"
        path = (directory / part).resolve()
        if (
            part.startswith("api/")
            or any(x.startswith(".") for x in Path(part).parts)
            or not path.is_relative_to(directory)
            or not path.is_file()
        ):
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    app = web.Application(middlewares=[guard], client_max_size=MAX_INPUT_BYTES)
    app.add_routes(
        [
            web.get("/api/status", status),
            web.post("/api/plan", plan),
            web.get("/api/calendar/{token}", calendar),
            web.post("/api/transcribe", transcribe),
            web.post("/api/speech", speech),
            web.get("/{path:.*}", static),
        ]
    )
    if client:

        async def close(app):
            await client.aclose()

        app.on_cleanup.append(close)
    return app


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Serve the BLR Air website and private API")
    parser.add_argument("--host", default=os.getenv("WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    parser.add_argument("--site-dir", default=os.getenv("SITE_DIR", "site/dist"))
    args = parser.parse_args()
    web.run_app(
        create_app(static_dir=args.site_dir), host=args.host, port=args.port, access_log=None
    )


if __name__ == "__main__":
    main()
