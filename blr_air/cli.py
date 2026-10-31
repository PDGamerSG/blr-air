import argparse
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from blr_air.demo import DemoProvider
from blr_air.domain import AirError, Location, RequestSpec
from blr_air.parsing import parse_request
from blr_air.providers import OpenMeteo, number
from blr_air.service import AirService, ComparisonResult, describe
from blr_air.venues import GooglePlaces


def initialize(path: Path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"{path} already exists; existing identity preserved.")
        return
    with os.fdopen(fd, "w") as handle:
        handle.write(
            f"AGENT_SEED_PHRASE={secrets.token_urlsafe(48)}\n"
            f"CALLER_SEED={secrets.token_urlsafe(48)}\n"
            "ASI1_API_KEY=\nASI1_BASE_URL=https://api.asi1.ai/v1\n"
            "SARVAM_API_KEY=\n"
            "BLR_AIR_ADDRESS=\nAGENT_PORT=8001\nDATA_DIR=data\n"
        )
    print(f"Created private {path}. Back it up: changing AGENT_SEED_PHRASE changes the address.")


def doctor():
    from uagents_core.identity import Identity

    seed = os.getenv("AGENT_SEED_PHRASE")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Agent identity: {'configured' if seed else 'missing; run python -m blr_air init'}")
    if seed:
        print(f"Agent address: {Identity.from_seed(seed, 0).address}")
    print(
        f"ASI:One parser: {'configured' if os.getenv('ASI1_API_KEY') else 'keyless local parsing'}"
    )
    print("Live data: keyless Open-Meteo APIs")
    print(f"Sarvam speech: {'configured' if os.getenv('SARVAM_API_KEY') else 'not configured'}")
    print("Mailbox registration: verify Active status in Agentverse after connecting Inspector")
    return 0 if seed else 1


async def run(args):
    async with httpx.AsyncClient() as client:
        query = args.query
        voice = None
        if args.audio_input or args.audio_output:
            from blr_air.voice import SarvamVoice

            if args.demo:
                raise AirError("Voice calls use a live API; omit --demo for audio.")
            voice = SarvamVoice(client, os.getenv("SARVAM_API_KEY", ""))
        if args.audio_input:
            if query is not None:
                raise AirError("Supply either a text request or --audio-input, not both.")
            query = await voice.transcribe(args.audio_input, language=args.audio_language)
        key = None if args.demo else os.getenv("ASI1_API_KEY")
        q = (
            await parse_request(
                query,
                client,
                api_key=key,
                base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
            )
            if query
            else RequestSpec()
        )
        overrides = {
            name: getattr(args, name)
            for name in (
                "place",
                "hours",
                "activity",
                "day",
                "period",
                "max_aqi",
                "max_rain",
                "max_temperature",
                "max_uv",
                "max_wind",
                "daylight_only",
            )
            if getattr(args, name) is not None
        }
        if args.compare:
            overrides.update(places=args.compare, place=args.compare[0])
        if args.place and not args.compare:
            overrides["places"] = []
        q = RequestSpec.model_validate({**q.model_dump(), **overrides})
        location = None
        if args.latitude is not None:
            if q.places:
                raise AirError("Use either coordinates or place comparison in one request.")
            if not number(args.latitude, minimum=-90, maximum=90) or not number(
                args.longitude, minimum=-180, maximum=180
            ):
                raise AirError("Latitude must be -90…90 and longitude -180…180, both finite.")
            location = Location(
                f"{args.latitude:.4f}, {args.longitude:.4f}", args.latitude, args.longitude
            )
        provider = DemoProvider() if args.demo else OpenMeteo(client)
        service = AirService(
            provider,
            client,
            venues=GooglePlaces(client, os.getenv("GOOGLE_PLACES_API_KEY", ""))
            if not args.demo
            else None,
        )
        result = (
            await service.compare(q, q.places)
            if len(q.places) > 1
            else await service.recommend(q, location=location)
        )
        data = result.to_dict()
        selected = (
            next((item.recommendation for item in result.items if item.recommendation), None)
            if isinstance(result, ComparisonResult)
            else result
        )
        if args.audio_input:
            data["transcript"] = query
        if args.calendar:
            from blr_air.calendar_export import write_calendar

            if selected is None:
                raise AirError("No eligible window to export to a calendar.")
            data["calendar_file"] = str(write_calendar(selected, args.calendar))
        if args.audio_output:
            from blr_air.service import spoken_summary

            data["audio_file"] = str(
                await voice.synthesize(spoken_summary(result), args.audio_output)
            )
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else describe(result))
        if not args.json:
            for name in ("calendar_file", "audio_file"):
                if name in data:
                    print(f"Saved: {data[name]}")
        if data["status"] == "error":
            raise SystemExit(1)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Best outdoor window from air quality, rain and heat"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Natural-language request, or init / doctor / stats",
    )
    parser.add_argument("--place", help="City or Bengaluru locality")
    parser.add_argument("--compare", action="append", help="Compare 2–3 places; repeat this option")
    parser.add_argument("--hours", type=int, choices=(1, 2))
    parser.add_argument("--activity", choices=("run", "cycle", "walk", "commute", "kids"))
    parser.add_argument("--day", choices=("next48", "today", "tomorrow"))
    parser.add_argument("--period", choices=("any", "morning", "afternoon", "evening"))
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    parser.add_argument("--demo", action="store_true", help="Synthetic offline Bengaluru demo")
    parser.add_argument("--max-aqi", type=float, help="Maximum hourly US AQI")
    parser.add_argument("--max-rain", type=float, help="Maximum hourly rain probability (%)")
    parser.add_argument("--max-temperature", type=float, help="Maximum feels-like temperature (°C)")
    parser.add_argument("--max-uv", type=float, help="Maximum hourly UV index")
    parser.add_argument("--max-wind", type=float, help="Maximum wind speed (km/h)")
    parser.add_argument("--daylight-only", action="store_true", default=None)
    parser.add_argument("--calendar", type=Path, help="Save selected window to a new .ics file")
    parser.add_argument(
        "--audio-input", type=Path, help="Transcribe a local PCM .wav (up to 30 sec)"
    )
    parser.add_argument(
        "--audio-output", type=Path, help="Save spoken English answer to a new .wav"
    )
    parser.add_argument("--audio-language", default="unknown", help="Input language, e.g. hi-IN")
    args = parser.parse_args()
    if (args.latitude is None) != (args.longitude is None):
        parser.error("--latitude and --longitude must be supplied together")
    if args.demo and args.latitude is not None:
        parser.error("--demo uses synthetic Bengaluru data; omit coordinates")
    if args.compare and not 2 <= len(args.compare) <= 3:
        parser.error("Repeat --compare for two or three places")
    if args.compare and args.place:
        parser.error("Use --place or --compare")
    if args.query == "init":
        initialize(Path(".env"))
        return
    if args.query == "doctor":
        sys.exit(doctor())
    if args.query == "stats":
        from blr_air.telemetry import Usage

        seed = os.getenv("AGENT_SEED_PHRASE")
        if not seed:
            parser.error("Run python -m blr_air init first")
        stats = Usage(Path(os.getenv("DATA_DIR", "data")) / "usage.sqlite", seed).stats()
        print(json.dumps(stats, indent=2))
        return
    try:
        asyncio.run(run(args))
    except (AirError, ValidationError) as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
