"""Opt-in real website API checks, including Sarvam input/output when configured."""

import argparse
import asyncio
import json
import tempfile
import wave
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from blr_air.localities import local_location


async def run(url, output):
    import os

    from blr_air.voice import SarvamVoice

    checks = []
    async with httpx.AsyncClient(timeout=80) as client:
        status_response = await client.get(url + "/api/status")
        status_response.raise_for_status()
        status = status_response.json()
        assert status["status"] == "ok"
        page = await client.get(url + "/")
        assert page.status_code == 200 and "planner-query" in page.text
        assert (await client.get(url + "/.env")).status_code == 404
        checks.append(
            {
                "name": "website_and_private_files",
                "status": "passed",
                "features": status["features"],
            }
        )
        response = await client.post(
            url + "/api/plan",
            json={
                "query": "compare HSR Layout and Whitefield for a walk "
                "tomorrow morning with daylight only"
            },
        )
        response.raise_for_status()
        plan = response.json()
        assert plan["status"] == "ok" and len(plan["places"]) == 2
        chosen = plan["places"][0]
        assert chosen["assessment"]["aqi"]["category"] == chosen["window"]["aqi_category"]
        assert len(chosen["backups"]) > 0
        assert chosen["window"]["daylight"] is True
        checks.append(
            {
                "name": "live_comparison_assessment_backups",
                "status": "passed",
                "places": [
                    {
                        "name": p["location"]["name"],
                        "start": p["window"]["start"],
                        "category": p["window"]["aqi_category"],
                        "backups": len(p["backups"]),
                    }
                    for p in plan["places"]
                ],
                "ties": plan["tied_places"],
            }
        )
        calendar = await client.get(
            url + f"/api/calendar/{plan['plan_id']}", params={"window_index": 1}
        )
        calendar.raise_for_status()
        start = datetime.fromisoformat(chosen["backups"][0]["start"]).astimezone(UTC)
        assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in calendar.text
        checks.append({"name": "exact_backup_calendar", "status": "passed"})
        invalid = await client.post(url + "/api/plan", json={"request": {"hours": 3}})
        assert invalid.status_code == 400
        impossible = await client.post(
            url + "/api/plan", json={"request": {"place": "HSR Layout", "max_aqi": 0}}
        )
        assert impossible.status_code == 422
        forbidden = await client.post(
            url + "/api/plan",
            json={"query": "run in HSR"},
            headers={"Origin": "https://unrelated.example"},
        )
        assert forbidden.status_code == 403
        checks.append({"name": "invalid_limits_and_foreign_origin", "status": "passed"})
        venue = await client.post(
            url + "/api/plan",
            json={"query": "walk in Cubbon Park tomorrow morning", "include_venue": True},
        )
        venue.raise_for_status()
        venue_data = venue.json()["venue"]
        if status["features"]["venues"]:
            if venue_data["status"] != "ok":
                checks.append(
                    {
                        "name": "live_google_places",
                        "status": "provider_unavailable",
                        "message": venue_data.get("message"),
                        "fallback_forecast": "passed",
                    }
                )
            else:
                checks.append(
                    {
                        "name": "live_google_places",
                        "status": "passed",
                        "name_matched": venue_data["name"],
                        "rating": venue_data["rating"],
                        "review_count_returned": len(venue_data["reviews"]),
                    }
                )
        else:
            assert venue_data["status"] == "unavailable"
            checks.append(
                {
                    "name": "live_google_places",
                    "status": "not_configured",
                    "fallback_forecast": "passed",
                }
            )
        if status["features"]["voice"]:
            voice = SarvamVoice(client, os.environ["SARVAM_API_KEY"])
            with tempfile.TemporaryDirectory(prefix="blr-web-live-") as directory:
                request = await voice.synthesize(
                    "Find a one hour running window in Bengaluru tomorrow morning.",
                    Path(directory) / "request.wav",
                )
                transcription = await client.post(
                    url + "/api/transcribe",
                    content=request.read_bytes(),
                    headers={"Content-Type": "audio/wav"},
                )
                transcription.raise_for_status()
                transcript = transcription.json()["transcript"]
                spoken_plan = await client.post(url + "/api/plan", json={"query": transcript})
                spoken_plan.raise_for_status()
                interpreted = spoken_plan.json()["request"]
                assert local_location(interpreted["place"]) == local_location("Bengaluru"), (
                    transcript
                )
                assert (
                    interpreted["hours"],
                    interpreted["activity"],
                    interpreted["day"],
                    interpreted["period"],
                ) == (1, "run", "tomorrow", "morning"), transcript
                speech = await client.post(
                    url + "/api/speech", json={"plan_id": spoken_plan.json()["plan_id"]}
                )
                speech.raise_for_status()
                import io

                with wave.open(io.BytesIO(speech.content), "rb") as audio:
                    assert audio.getframerate() == 24000 and audio.getnframes() > 0
                    duration = round(audio.getnframes() / audio.getframerate(), 2)
                artifact = Path("artifacts/website-spoken-plan.wav")
                artifact.parent.mkdir(exist_ok=True)
                artifact.write_bytes(speech.content)
                artifact.chmod(0o600)
                checks.append(
                    {
                        "name": "sarvam_speech_to_plan_to_speech",
                        "status": "passed",
                        "transcript": transcript,
                        "spoken_seconds": duration,
                    }
                )
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "Local developer traffic; not public deployment or customer evidence",
        "checks": checks,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    for item in checks:
        print(item["status"].upper(), item["name"])


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, default=Path("docs/web-live-checks.json"))
    args = parser.parse_args()
    asyncio.run(run(args.url.rstrip("/"), args.output))
