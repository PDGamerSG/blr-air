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
from blr_air.service import AirService, describe


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
    print("Mailbox registration: verify Active status in Agentverse after connecting Inspector")
    return 0 if seed else 1


async def run(args):
    async with httpx.AsyncClient() as client:
        key = None if args.demo else os.getenv("ASI1_API_KEY")
        q = await parse_request(
            args.query,
            client,
            api_key=key,
            base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
        )
        overrides = {
            name: getattr(args, name)
            for name in ("place", "hours", "activity", "day", "period")
            if getattr(args, name) is not None
        }
        q = RequestSpec.model_validate({**q.model_dump(), **overrides})
        location = None
        if args.latitude is not None:
            if not number(args.latitude, minimum=-90, maximum=90) or not number(
                args.longitude, minimum=-180, maximum=180
            ):
                raise AirError("Latitude must be -90…90 and longitude -180…180, both finite.")
            location = Location(
                f"{args.latitude:.4f}, {args.longitude:.4f}", args.latitude, args.longitude
            )
        provider = DemoProvider() if args.demo else OpenMeteo(client)
        result = await AirService(provider, client).recommend(q, location=location)
        print(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            if args.json
            else describe(result)
        )


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Best outdoor window from air quality, rain and heat"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="best window in Bengaluru",
        help="Natural-language request, or init / doctor / stats",
    )
    parser.add_argument("--place", help="City or Bengaluru locality")
    parser.add_argument("--hours", type=int, choices=(1, 2))
    parser.add_argument("--activity", choices=("run", "cycle", "walk", "commute", "kids"))
    parser.add_argument("--day", choices=("next48", "today", "tomorrow"))
    parser.add_argument("--period", choices=("any", "morning", "afternoon", "evening"))
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    parser.add_argument("--demo", action="store_true", help="Synthetic offline Bengaluru demo")
    args = parser.parse_args()
    if (args.latitude is None) != (args.longitude is None):
        parser.error("--latitude and --longitude must be supplied together")
    if args.demo and args.latitude is not None:
        parser.error("--demo uses synthetic Bengaluru data; omit coordinates")
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
