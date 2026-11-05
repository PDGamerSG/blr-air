"""Generate Kotlin parity fixtures from the real Python implementation.

Run from the repository root:
    .venv/Scripts/python watch/tools/gen_parity.py
The watch's ParityTest must reproduce every expected value in the output.
"""

import json
import random
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from delhi_air.assessment import assess
from delhi_air.domain import (
    AirError,
    Forecast,
    Hour,
    Location,
    NoWindowError,
    RequestSpec,
)
from delhi_air.localities import ALIASES, LOCALITIES, local_location
from delhi_air.parsing import parse_local
from delhi_air.providers import merge_forecasts
from delhi_air.scoring import aqi_category, select_windows
from delhi_air.service import Recommendation

OUT = Path(__file__).parent.parent / "app/src/test/resources"
ZONES = ("Asia/Kolkata", "Asia/Kolkata", "Asia/Kolkata", "America/New_York", "Europe/London")
ACTIVITIES = ("run", "cycle", "walk", "commute", "kids")
SENTENCES = [
    "best 1-hour window to run in Hauz Khas",
    "best 2-hour cycling window in Dwarka tomorrow morning",
    "when is the air cleanest in Noida",
    "can I take kids outside in Saket tomorrow morning",
    "best time to commute in Okhla today",
    "walk near India Gate tomorrow evening",
    "best 2-hour walk in Melbourne, Australia",
    "best time to run in New York, US tomorrow morning",
    "compare Hauz Khas and Noida for a run tomorrow morning",
    "compare Gurgaon, Noida and Rohini for a walk",
    "Noida vs Gurugram for a run",
    "best window in Sector 62 Noida",
    "cp walk today",
    "cleanest time in gurgaon",
    "run in new delhi tomorrow",
    "run in Hauz Khas with AQI at most 150, rain at most 30%, daylight only",
    "walk in Lodhi Garden with feels like at most 86F and wind at most 10 mph",
    "cycle in Dwarka with uv at most 5 and wind under 20 km/h",
    "run with max aqi 200 in Rohini this afternoon",
    "best time for a jog",
    "a walk",
    "go for a bike ride in Paris, France this evening",
    "when should the kids play outside in Karol Bagh",
    "best 3-hour run in Delhi",
    "best four hour walk in Delhi",
    "run at 7 am in Saket",
    "walk on Monday in Noida",
    "run for 30 minutes in Delhi",
    "next week in Delhi",
    "run in Delhi with temperature at most 300K",
    "rain 30 in Delhi",
    "compare Noida",
    "compare Noida and Saket and Dwarka and Rohini",
    "@delhi-air best time to run in Noida",
    "@blr-air best time to run in Noida",
    "compare Hauz Khas, Delhi and Noida",
    "show reviews of Lodhi Garden tomorrow morning",
    "walk in India Gate and show reviews",
    "best window in the next 48 hours in Okhla",
    "smog in Anand Vihar today",
    "aqi for Faridabad",
    "ghaziabad evening walk",
]
PLACES = [
    *(f"{value[0]}" for value in LOCALITIES.values()),
    *ALIASES,
    "Delhi, India",
    "New Delhi, India",
    "Connaught Place, New Delhi",
    "Noida, Uttar Pradesh",
    "Gurugram, Haryana",
    "Sector 62, Noida",
    "Sector-18 Noida",
    "Dwarka Sector 21",
    "Rohini sec 7",
    "Rohini Sector 3, Delhi",
    "Dwarka Sector 10, New Delhi",
    "Delhi, Ontario",
    "Delhi, Canada",
    "Paris, France",
    "New",
    "South",
]


def epoch(value):
    return int(value.timestamp())


def random_rows(rng, start):
    rows = []
    time = start
    for _ in range(rng.randint(30, 96)):
        if rng.random() < 0.03:
            time += timedelta(hours=rng.randint(1, 3))
        rows.append(
            Hour(
                time,
                round(rng.uniform(40, 480), 1),
                round(rng.uniform(10, 300), 1),
                float(rng.choice([0, 0, 0, 5, 15, 40, 70, 95])),
                round(rng.uniform(4, 46), 1),
                None if rng.random() < 0.03 else round(rng.uniform(3, 50), 1),
                None if rng.random() < 0.03 else round(rng.uniform(0, 11), 1),
                None if rng.random() < 0.03 else round(rng.uniform(0, 40), 1),
            )
        )
        time += timedelta(hours=1)
    return rows


def random_request(rng):
    def maybe(low, high):
        return round(rng.uniform(low, high), 1) if rng.random() < 0.2 else None

    return RequestSpec(
        activity=rng.choice(ACTIVITIES),
        hours=rng.choice((1, 2)),
        day=rng.choice(("next48", "today", "tomorrow")),
        period=rng.choice(("any", "morning", "afternoon", "evening")),
        max_aqi=maybe(150, 480),
        max_rain=maybe(10, 90),
        max_temperature=maybe(20, 48),
        max_uv=maybe(3, 11),
        max_wind=maybe(10, 40),
        daylight_only=rng.random() < 0.2,
    )


def window_json(window):
    data = asdict(window)
    data["start"], data["end"] = epoch(window.start), epoch(window.end)
    return data


def hour_json(row):
    return {**asdict(row), "time": epoch(row.time)}


def request_json(request):
    data = request.model_dump()
    data.pop("include_venue", None)
    return data


def scoring_cases(rng, count):
    cases = []
    for _ in range(count):
        # Include the 2026 US and UK clock changes so elapsed hours are exercised.
        base = rng.choice(
            (
                datetime(2026, 11, 4, 0, tzinfo=UTC),
                datetime(2026, 10, 31, 12, tzinfo=UTC),
                datetime(2026, 3, 7, 18, tzinfo=UTC),
                datetime(2026, 5, 20, 0, tzinfo=UTC),
            )
        )
        rows = random_rows(rng, base)
        request = random_request(rng)
        zone = rng.choice(ZONES)
        now = base + timedelta(minutes=rng.randint(-120, 600))
        daylight = []
        if rng.random() < 0.8:
            for day in range(5):
                rise = base + timedelta(days=day, hours=1, minutes=rng.randint(0, 90))
                daylight.append((rise, rise + timedelta(hours=11)))
        case = {
            "rows": [hour_json(row) for row in rows],
            "request": request_json(request),
            "timezone": zone,
            "now": epoch(now),
            "daylight": [[epoch(a), epoch(b)] for a, b in daylight],
        }
        try:
            windows = select_windows(rows, request, zone, now, limit=3, daylight=tuple(daylight))
        except NoWindowError:
            case["windows"] = None
            cases.append(case)
            continue
        case["windows"] = [window_json(window) for window in windows]
        forecast = Forecast(tuple(rows), None, zone, now, daylight=tuple(daylight))
        location = Location("Test", 28.6, 77.2, zone)
        case["assessments"] = []
        for window in windows:
            result = assess(Recommendation(request, location, forecast, window))
            case["assessments"].append(
                {
                    "verdict": result["verdict"],
                    "category": result["aqi"]["category"],
                    "advice": result["aqi"]["advice"],
                    "warnings": result["warnings"],
                    "checklist": result["checklist"],
                }
            )
        cases.append(case)
    return cases


def parser_cases():
    cases = []
    for text in SENTENCES:
        try:
            cases.append({"text": text, "request": request_json(parse_local(text))})
        except AirError as exc:
            cases.append({"text": text, "error": str(exc)})
    return cases


def main():
    rng = random.Random(2026)
    air = json.loads((OUT / "air_delhi.json").read_text(encoding="utf-8"))
    weather = json.loads((OUT / "weather_delhi.json").read_text(encoding="utf-8"))
    merged = merge_forecasts(air, weather, datetime(2026, 11, 4, 13, 0, tzinfo=UTC))
    cases = {
        "scoring": scoring_cases(rng, 600),
        "parser": parser_cases(),
        "locations": [
            {"text": text, **(asdict(location) if (location := local_location(text)) else {})}
            for text in PLACES
        ],
        "categories": [
            {"aqi": aqi, "category": aqi_category(aqi)}
            for aqi in (0, 50, 50.5, 100, 101, 150, 151, 200, 201, 300, 301, 500, 640)
        ],
        "forecast": {
            "hours": [hour_json(row) for row in merged.hours],
            "timezone": merged.timezone,
            "current": (
                {**asdict(merged.current), "time": epoch(merged.current.time)}
                if merged.current
                else None
            ),
            "daylight": [[epoch(a), epoch(b)] for a, b in merged.daylight],
        },
    }
    (OUT / "parity.json").write_text(json.dumps(cases), encoding="utf-8")
    with_windows = sum(1 for case in cases["scoring"] if case["windows"])
    print(
        f"{len(cases['scoring'])} scoring cases ({with_windows} with windows), "
        f"{len(cases['parser'])} sentences, {len(cases['locations'])} places, "
        f"{len(merged.hours)} forecast hours"
    )


if __name__ == "__main__":
    main()
