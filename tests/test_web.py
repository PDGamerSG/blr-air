from datetime import UTC, datetime, timedelta

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer

from blr_air.demo import DemoProvider
from blr_air.service import AirService


@pytest.fixture
async def browser(tmp_path):
    from blr_air.web import create_app

    async with httpx.AsyncClient() as http:
        service = AirService(DemoProvider(), http)
        app = create_app(service=service, static_dir=tmp_path, rate_limit=100)
        async with TestClient(TestServer(app)) as client:
            yield client


async def test_plan_returns_shared_numeric_results_and_selected_backup_calendar(browser):
    response = await browser.post("/api/plan", json={"request": {"place": "HSR Layout"}})
    assert response.status == 200
    data = await response.json()
    assert data["window"]["us_aqi"] > 0
    assert data["assessment"]["aqi"]["category"]
    assert len(data["backups"]) == 2
    export = await browser.get(f"/api/calendar/{data['plan_id']}?window_index=1")
    assert export.status == 200
    expected = datetime.fromisoformat(data["backups"][0]["start"]).astimezone(UTC)
    assert f"DTSTART:{expected:%Y%m%dT%H%M%SZ}" in await export.text()
    assert export.headers["Content-Type"].startswith("text/calendar")
    assert export.headers["Cache-Control"] == "no-store"


async def test_comparison_and_failed_lookup_are_explicit(browser):
    response = await browser.post("/api/plan", json={"query": "compare HSR Layout and Whitefield"})
    data = await response.json()
    assert response.status == 200
    assert len(data["places"]) == 2
    assert data["places"][0]["assessment"]["location"]["resolved_name"]
    bad = await browser.post("/api/plan", json={"query": "run in HSR Layout for 8 hours"})
    assert bad.status == 422
    assert "error" in await bad.json()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"query": ""},
        {"query": "run in HSR", "request": {}},
        {"request": {"hours": 3}},
        {"query": "x" * 2001},
        {"query": "run in HSR", "unknown": True},
    ],
)
async def test_invalid_requests_do_not_silently_run_default_plan(browser, payload):
    response = await browser.post("/api/plan", json=payload)
    assert response.status == 400
    assert (await response.json())["status"] == "error"


async def test_missing_voice_unknown_snapshot_and_bad_selection(browser):
    status = await (await browser.get("/api/status")).json()
    assert status["features"]["voice"] is False
    voice = await browser.post(
        "/api/transcribe", data=b"bad audio", headers={"Content-Type": "audio/wav"}
    )
    assert voice.status == 503
    unknown = await browser.get("/api/calendar/not-a-real-plan")
    assert unknown.status == 410
    data = await (await browser.post("/api/plan", json={"request": {"place": "HSR Layout"}})).json()
    wrong = await browser.get(f"/api/calendar/{data['plan_id']}?window_index=99")
    assert wrong.status == 400


async def test_cross_origin_post_is_rejected_before_work(browser):
    response = await browser.post(
        "/api/plan", json={"query": "run in HSR"}, headers={"Origin": "https://other.example"}
    )
    assert response.status == 403


async def test_rate_limit_bounds_requests_and_releases_after_window(tmp_path):
    from blr_air.web import create_app

    async with httpx.AsyncClient() as http:
        app = create_app(
            service=AirService(DemoProvider(), http), static_dir=tmp_path, rate_limit=1
        )
        async with TestClient(TestServer(app)) as client:
            first = await client.post("/api/plan", json={"request": {"place": "HSR Layout"}})
            assert first.status == 200
            second = await client.post("/api/plan", json={"request": {"place": "HSR Layout"}})
            assert second.status == 429
            assert second.headers["Retry-After"] == "60"


async def test_plan_store_expires_and_does_not_export_stale_plan():
    from blr_air.web import PlanStore

    store = PlanStore(ttl=1, capacity=2)
    now = datetime.now(UTC)
    key, _ = store.put("result", now=now)
    assert store.get(key, now=now) == "result"
    with pytest.raises(KeyError):
        store.get(key, now=now + timedelta(seconds=2))


async def test_plan_store_does_not_keep_customer_reviews():
    from dataclasses import replace

    from blr_air.domain import RequestSpec
    from blr_air.web import PlanStore

    async with httpx.AsyncClient() as http:
        result = await AirService(DemoProvider(), http).recommend(RequestSpec())
    result = replace(result, venue={"reviews": [{"text": "private review content"}]})
    store = PlanStore()
    key, _ = store.put(result)
    assert store.get(key).venue is None
    assert result.venue["reviews"][0]["text"] == "private review content"


async def test_static_server_serves_site_but_not_environment(tmp_path):
    from blr_air.web import create_app

    (tmp_path / "index.html").write_text("<h1>Planner</h1>")
    (tmp_path / ".env").write_text("private")
    async with httpx.AsyncClient() as http:
        async with TestClient(
            TestServer(create_app(service=AirService(DemoProvider(), http), static_dir=tmp_path))
        ) as client:
            assert "Planner" in await (await client.get("/")).text()
            assert (await client.get("/.env")).status == 404
            assert (await client.get("/api/no-such-route")).status == 404


async def test_chunked_json_request_is_read_completely(browser):
    import asyncio

    async def body():
        yield b'{"request":'
        await asyncio.sleep(0.01)
        yield b'{"place":"HSR Layout"}}'

    response = await browser.post(
        "/api/plan", data=body(), headers={"Content-Type": "application/json"}
    )
    assert response.status == 200


async def test_oversize_json_does_not_reach_planner(browser):
    response = await browser.post(
        "/api/plan", data=b" " * 32769, headers={"Content-Type": "application/json"}
    )
    assert response.status == 413


async def test_snapshot_stores_assessment_for_each_backup(browser):
    data = await (await browser.post("/api/plan", json={"request": {"place": "HSR Layout"}})).json()
    assert data["backups"][0]["assessment"]["aqi"]["worst_hourly"] == data["backups"][0]["max_aqi"]


async def test_voice_http_roundtrip_and_speech_selection_use_shared_service(tmp_path):
    import base64
    import io
    import json
    import wave

    from blr_air.voice import SarvamVoice
    from blr_air.web import create_app

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    wav = buffer.getvalue()
    spoken = []

    def provider(req):
        if req.url.path == "/speech-to-text":
            assert wav in req.content
            return httpx.Response(200, json={"transcript": "run in HSR Layout"})
        spoken.append(json.loads(req.content)["text"])
        return httpx.Response(200, json={"audios": [base64.b64encode(wav).decode()]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as http:
        service = AirService(DemoProvider(), http)
        voice = SarvamVoice(http, "test-private")
        async with TestClient(
            TestServer(create_app(service=service, voice=voice, static_dir=tmp_path))
        ) as client:
            transcript = await client.post(
                "/api/transcribe", data=wav, headers={"Content-Type": "audio/wav"}
            )
            assert (await transcript.json())["transcript"] == "run in HSR Layout"
            data = await (
                await client.post("/api/plan", json={"query": "run in HSR Layout"})
            ).json()
            reply = await client.post(
                "/api/speech", json={"plan_id": data["plan_id"], "window_index": 1}
            )
            assert reply.status == 200
            assert await reply.read() == wav
            start = datetime.fromisoformat(data["backups"][0]["start"])
            assert start.strftime("%H:%M") in spoken[0]
            assert "synthetic" in spoken[0]
            invalid = await client.post(
                "/api/transcribe", data=b"not a wave", headers={"Content-Type": "audio/wav"}
            )
            assert invalid.status == 422


async def test_venue_lookup_budget_limits_paid_searches(tmp_path):
    from blr_air.web import create_app

    class CountingVenues:
        api_key = "test"

        def __init__(self):
            self.calls = 0

        async def search(self, query):
            self.calls += 1
            return {"status": "unavailable", "message": "provider unavailable"}

    async with httpx.AsyncClient() as http:
        venues = CountingVenues()
        app = create_app(
            service=AirService(DemoProvider(), http, venues=venues),
            static_dir=tmp_path,
            rate_limit=100,
            venue_rate_limit=1,
        )
        async with TestClient(TestServer(app)) as client:
            first = await client.post(
                "/api/plan", json={"request": {"place": "HSR Layout"}, "include_venue": True}
            )
            second = await client.post(
                "/api/plan", json={"request": {"place": "Whitefield"}, "include_venue": True}
            )
    assert first.status == 200
    assert second.status == 429
    assert venues.calls == 1
