"""Answer "where and when?": search real places, read their air, and pick one.

Place data comes from OpenStreetMap (scripts/build_spots.py). The ranking is a transparent
preference heuristic built on the shared window score, not a health or safety rating.
"""

import asyncio
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from delhi_air.domain import AirError, Location, NoWindowError, ProviderError, RequestSpec
from delhi_air.localities import closest_location, local_location
from delhi_air.parsing import parse_local
from delhi_air.scoring import select_windows
from delhi_air.stations import StationFeed, distance_km

SPOTS = json.loads(Path(__file__).with_name("spots.json").read_text(encoding="utf-8"))
MAX_CANDIDATES = 8
RADII_KM = (4, 8, 15)
HERE = {"me", "here", "my home", "my house", "home", "my place", "my location"}
NOT_A_PLACE = {"morning", "afternoon", "evening", "night", "a", "an", "the", "bit", "while"}

ACTIVITY = re.compile(
    r"\b(?:walk|walking|stroll|run|running|jog|jogging|cycle|cycling|bike|biking|bicycle|"
    r"ride|kids?|children|child|playground|picnic|exercise|workout|yoga)\b",
    re.I,
)
WANTS_PLACE = re.compile(
    r"\b(?:near|nearby|around|close to|area|region|side|where|somewhere|place|spot|park|"
    r"suggest|recommend|i want|i wanna|i'd like|i would like|go for a|take my|take the|"
    r"looking for|planning)\b",
    re.I,
)
NOT_A_SEARCH = re.compile(r"\b(?:window|compare|versus|vs|reviews?|ratings?|commute)\b", re.I)
ANCHOR = re.compile(
    r"\b(?:near|around|close to|in|at|by)\s+(?:the\s+)?(.+?)"
    r"(?:\s+(?:area|region|side|locality|neighbou?rhood))?"
    r"(?=\s+(?:today|tomorrow|tonight|this|for|during|with|morning|afternoon|evening|in|at|near|around|close)\b"
    r"|[?.!,]|$)",
    re.I,
)


SUGGEST = re.compile(
    r"\b(?:what (?:can|should|could|shall) i do|what to do|suggest something|"
    r"recommend something|surprise me|anything (?:good )?to do|plan my (?:day|morning|evening)|"
    r"should i go out)\b",
    re.I,
)
ACTIVITY_NAMES = {
    "walk": "walk",
    "run": "run",
    "cycle": "bike ride",
    "kids": "outing with the kids",
}
LEVELS = {
    "go": "Good to go",
    "care": "Go with care",
    "short": "Keep it short",
    "stay": "Better to stay in",
}


def wants_suggestion(text: str) -> bool:
    """A request with nothing chosen yet, so the agent decides what to do as well."""
    return bool(SUGGEST.search(text))


def level(activity: str, aqi: float) -> str:
    """Children and hard exercise get the stricter reading, as the AQI guidance advises."""
    if aqi > 200 or (activity in ("run", "cycle", "kids") and aqi > 150):
        return "stay"
    if aqi > 150:
        return "short"
    return "care" if aqi > 100 else "go"


def wants_place(text: str) -> bool:
    """An open request: an outing and an area, rather than a time at a place already chosen."""
    return bool(
        ACTIVITY.search(text) and WANTS_PLACE.search(text) and not NOT_A_SEARCH.search(text)
    )


def find_anchor(text: str) -> str | None:
    """The area named in a request, preferring 'near X' over a looser 'in X'."""
    found = [match[1].strip(" .,?!") for match in ANCHOR.finditer(text)]
    named = [place for place in found if place.casefold() not in NOT_A_PLACE]
    return named[0] if named else None


def understand(text: str) -> RequestSpec:
    """Reuse the planner's parser for activity, duration, day, period and limits."""
    plain = re.sub(r"\b(?:ride|bicycle)\b", "cycling", text, flags=re.I)
    plain = re.sub(r"\bstroll\b", "walk", plain, flags=re.I)
    return parse_local(f"{plain} in Delhi").model_copy(update={"place": "Delhi", "places": []})


def fits(spot: dict, activity: str) -> bool:
    kind, area = spot["kind"], spot["area_m2"]
    if activity == "cycle":
        return spot["cycling"] and (kind == "track" or area >= 150_000)
    if activity == "run":
        return kind in ("track", "stadium") or area >= 30_000
    if activity == "kids":
        return kind in ("park", "garden") and 15_000 <= area <= 1_500_000
    return kind != "stadium"


def preference(spot: dict, activity: str, km: float) -> float:
    """Lower is better: closer, larger, and purpose-built for the activity."""
    size = 6 * math.log10(max(spot["area_m2"], 10_000) / 10_000)
    purpose = 30 if activity == "cycle" and "cycle" in spot["name"].casefold() else 0
    return 2.5 * km - size - purpose


@dataclass(frozen=True)
class Candidate:
    spot: dict
    km: float
    window: object
    backups: tuple
    forecast: object
    measured: object
    score: float
    activity: str = "walk"


class Advisor:
    def __init__(self, provider, client):
        self.provider = provider
        self.stations = StationFeed(client)

    async def anchor(self, text: str, near) -> Location | None:
        named = find_anchor(text)
        if named and named.casefold() not in HERE:
            known = local_location(named) or closest_location(named)
            return known or await self.provider.locate(named)
        if near:
            return Location("your area", near[0], near[1])
        return None

    def search(self, anchor: Location, activity: str):
        """The closest suitable places, widening the search until there's a real choice."""
        for radius in RADII_KM:
            scored = []
            for spot in SPOTS:
                km = distance_km(
                    anchor.latitude, anchor.longitude, spot["latitude"], spot["longitude"]
                )
                if km <= radius and fits(spot, activity):
                    scored.append((preference(spot, activity, km), km, spot))
            if len(scored) >= 3 or radius == RADII_KM[-1]:
                scored.sort(key=lambda item: item[0])
                return scored[:MAX_CANDIDATES], len(scored), radius
        return [], 0, RADII_KM[-1]

    async def suggest(self, text: str, *, near=None, now=None):
        from delhi_air.service import Recommendation

        request = understand(text)
        anchor = await self.anchor(text, near)
        if anchor is None:
            return "Which area should I search? Try 'a walk near Rohini'."
        found, total, radius = self.search(anchor, request.activity)
        if not found:
            raise AirError(
                f"I couldn't find a suitable place within {radius} km of "
                f"{anchor.name}. I know Delhi NCR best; try another area."
            )
        now = now or datetime.now(UTC)
        try:
            async with asyncio.timeout(30):
                ranked = await self.analyse(found, request, now)
        except TimeoutError as exc:
            raise ProviderError("The search took too long. Please try again.") from exc
        if not ranked:
            raise NoWindowError(
                "No complete outdoor window matches this request in the next 48 hours. "
                "Try another part of the day; limits are never relaxed automatically."
            )
        best = ranked[0]
        name = f"{best.spot['name']}, near {anchor.name.split(',')[0]}"
        location = Location(
            name, best.spot["latitude"], best.spot["longitude"], best.forecast.timezone
        )
        return Recommendation(
            request.model_copy(update={"place": name}),
            location,
            best.forecast,
            best.window,
            best.backups,
            search=findings(best, ranked, anchor, total, request),
        )

    async def auto(self, *, text="", near=None, activities=(), usual_hours=(), now=None):
        """Decide unprompted: what to do, when, where and why, from live air and known habits."""
        from delhi_air.service import Recommendation

        anchor = await self.anchor(text, near)
        if anchor is None:
            return "Which area should I plan around? Try 'what should I do near Rohini'."
        now = now or datetime.now(UTC)
        order = list(dict.fromkeys([*activities, "walk", "run", "cycle"]))[:3]
        plans = []
        try:
            async with asyncio.timeout(30):
                for activity in order:
                    request = RequestSpec(activity=activity)
                    found, total, _ = self.search(anchor, activity)
                    ranked = await self.analyse(found, request, now) if found else []
                    if ranked:
                        plans.append((request, ranked, total))
                here = await self.stations.near(anchor.latitude, anchor.longitude)
        except TimeoutError as exc:
            raise ProviderError("The search took too long. Please try again.") from exc
        if not plans:
            raise NoWindowError("No complete outdoor window is available in the next 48 hours.")
        options = [
            (request, ranked, total, *pick_time(ranked[0], usual_hours, now))
            for request, ranked, total in plans
        ]
        chosen = next((item for item in options if item[5] != "stay"), None)
        stay_in = chosen is None
        # When nothing is advisable, the gentlest outing is still worth knowing about.
        chosen = chosen or next((i for i in options if i[0].activity == "walk"), options[0])
        request, ranked, total, window, backups, kind = chosen
        best = replace(ranked[0], window=window, backups=backups)
        name = f"{best.spot['name']}, near {anchor.name.split(',')[0]}"
        location = Location(
            name, best.spot["latitude"], best.spot["longitude"], best.forecast.timezone
        )
        current = best.forecast.current
        now_aqi = here.aqi if here else (current.us_aqi if current else None)
        return Recommendation(
            request.model_copy(update={"place": name}),
            location,
            best.forecast,
            window,
            backups,
            search=findings(best, ranked, anchor, total, request),
            suggestion=explain(
                best, request, kind, stay_in, activities, usual_hours, now_aqi, bool(here), now
            ),
        )

    async def analyse(self, found, request: RequestSpec, now) -> list[Candidate]:
        # Nearby parks share a model cell, so each cell is fetched once.
        cells = {(round(spot["latitude"], 1), round(spot["longitude"], 1)) for _, _, spot in found}
        forecasts = dict(
            zip(
                cells,
                await asyncio.gather(
                    *(self.provider.forecast(Location("cell", *cell)) for cell in cells)
                ),
                strict=True,
            )
        )
        readings = await asyncio.gather(
            *(self.stations.near(spot["latitude"], spot["longitude"]) for _, _, spot in found)
        )
        ranked = []
        for (fit, km, spot), measured in zip(found, readings, strict=True):
            forecast = forecasts[(round(spot["latitude"], 1), round(spot["longitude"], 1))]
            try:
                windows = select_windows(
                    forecast.hours,
                    request,
                    forecast.timezone,
                    now,
                    limit=3,
                    daylight=forecast.daylight,
                )
            except NoWindowError:
                continue
            excess = 0.0
            if measured and forecast.current:
                excess = max(0.0, measured.aqi - forecast.current.us_aqi)
            score = windows[0].score + 0.5 * excess + fit
            ranked.append(
                Candidate(
                    spot,
                    km,
                    windows[0],
                    tuple(windows[1:]),
                    forecast,
                    measured,
                    score,
                    request.activity,
                )
            )
        return sorted(ranked, key=lambda item: item.score)


def pick_time(best: Candidate, usual_hours, now):
    """The best time for this person: clean air, soon, and in their usual hours if possible."""
    zone = ZoneInfo(best.forecast.timezone)

    def cost(window):
        wait = (window.start - now).total_seconds() / 3600
        usual = window.start.astimezone(zone).hour in usual_hours
        return window.score + 0.5 * wait - (25 if usual else 0)

    windows = sorted((best.window, *best.backups), key=cost)
    excess = 0.0
    if best.measured and best.forecast.current:
        excess = max(0.0, best.measured.aqi - best.forecast.current.us_aqi)
    # Part of a monitor's excess over the model is expected to persist into the window.
    expected = windows[0].max_aqi + 0.5 * excess
    return windows[0], tuple(windows[1:]), level_for(best, expected)


def level_for(best: Candidate, aqi: float) -> str:
    return level(best.activity, aqi)


def explain(best, request, kind, stay_in, liked, usual_hours, now_aqi, measured, now) -> dict:
    window = best.window
    zone = ZoneInfo(best.forecast.timezone)
    start = window.start.astimezone(zone)
    activity = request.activity
    label = ACTIVITY_NAMES.get(activity, "outing")
    place = best.spot["name"]
    reasons = []
    today = now.astimezone(zone).date() == start.date()
    moment = f"{start:%H:%M}" if today else f"{start:%a} {start:%H:%M}"
    if now_aqi is not None:
        source = "monitors read" if measured else "the forecast says"
        reasons.append(
            f"Right now {source} AQI {now_aqi:.0f}. The forecast's cleanest time is {moment}, "
            f"at about {window.us_aqi:.0f}."
        )
        forecast_now = best.forecast.current
        if measured and forecast_now and now_aqi - forecast_now.us_aqi >= 50:
            reasons.append("Monitors here are reading well above the forecast, so expect worse.")
    if liked and activity != liked[0]:
        reasons.append(
            f"A {ACTIVITY_NAMES.get(liked[0], liked[0])} isn't advised in this air, "
            f"so I picked a {label} instead."
        )
    elif liked:
        reasons.append(f"You go for a {label} most often.")
    if start.hour in usual_hours:
        reasons.append(f"It fits your usual {start:%H}:00 routine.")
    if best.km >= 0.1:
        reasons.append(f"{place} is {best.km:.1f} km away.")
    if stay_in:
        headline = "Better to stay in"
        detail = f"If you must go: {label}, {moment}, {place}"
    else:
        headline = (
            f"{label.capitalize()}, {moment}" if not today else f"{label.capitalize()} at {moment}"
        )
        detail = place
    return {
        "kind": "stay" if stay_in else kind,
        "label": LEVELS["stay" if stay_in else kind],
        "headline": headline,
        "detail": detail,
        "reasons": reasons,
        "activity": activity,
        "now_aqi": round(now_aqi) if now_aqi is not None else None,
        "window_aqi": round(window.us_aqi),
    }


def when(window, timezone: str) -> str:
    start = window.start.astimezone(ZoneInfo(timezone))
    end = window.end.astimezone(ZoneInfo(timezone))
    return f"{start:%a %d %b}, {start:%H:%M}–{end:%H:%M}"


def findings(best: Candidate, ranked, anchor: Location, total: int, request) -> dict:
    spot = best.spot
    area = anchor.name.split(",")[0]
    hectares = spot["area_m2"] / 10_000
    reason = f"{spot['name']} is {best.km:.1f} km from {area}, about {hectares:.0f} hectares."
    if request.activity == "cycle" and "cycle" in spot["name"].casefold():
        reason = f"{spot['name']} is a dedicated cycle track, {best.km:.1f} km from {area}."
    measured = None
    if best.measured:
        measured = {"aqi": best.measured.aqi, "station": best.measured.name}
        reason += f" The nearest monitor, {best.measured.name}, reads {best.measured.aqi} now."
        current = best.forecast.current
        if current and best.measured.aqi - current.us_aqi >= 50:
            reason += " That's well above the forecast model, so expect worse air than shown."
    if request.activity == "cycle" and "cycle" not in spot["name"].casefold():
        reason += " Check that cycling is allowed there."
    return {
        "area": area,
        "searched": total,
        "checked": len(ranked),
        "place": spot["name"],
        "kind": spot["kind"],
        "distance_km": round(best.km, 1),
        "why": reason,
        "measured": measured,
        "maps_url": "https://www.google.com/maps/search/?"
        + urlencode({"api": 1, "query": f"{spot['latitude']},{spot['longitude']}"}),
        "alternatives": [
            {
                "place": other.spot["name"],
                "distance_km": round(other.km, 1),
                "when": when(other.window, other.forecast.timezone),
                "us_aqi": round(other.window.us_aqi),
                "measured_aqi": other.measured.aqi if other.measured else None,
            }
            for other in ranked[1:3]
        ],
        "credit": "Places from OpenStreetMap contributors.",
    }


def search_summary(result) -> str:
    """The where-and-when answer that leads the agent's reply."""
    found, forecast = result.search, result.forecast
    advice = result.suggestion
    lines = []
    if advice:
        lines.append(f"**{advice['headline']}**")
        lines.append(advice["detail"])
        lines.append("\n".join("- " + reason for reason in advice["reasons"]))
    lines += [
        f"**Best place: {found['place']}**",
        f"**Best time: {when(result.window, forecast.timezone)}**",
        f"{found['why']}",
        f"I compared {found['checked']} of {found['searched']} suitable places "
        f"near {found['area']}.",
    ]
    if found["alternatives"]:
        lines.append(
            "**Other options**\n\n"
            + "\n".join(
                f"- {item['place']} ({item['distance_km']} km): {item['when']}, "
                f"AQI {item['us_aqi']}"
                + (f", monitor {item['measured_aqi']}" if item["measured_aqi"] else "")
                for item in found["alternatives"]
            )
        )
    lines.append(f"[Open in Maps]({found['maps_url']}) · {found['credit']}")
    return "\n\n".join(lines)
