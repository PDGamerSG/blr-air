import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from math import isclose
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from blr_air.assessment import assess
from blr_air.conversation import chat_intent, clean_message, describe_conditions
from blr_air.domain import AirError, Forecast, Location, ProviderError, RequestSpec, Window
from blr_air.parsing import parse_request
from blr_air.providers import OpenMeteo
from blr_air.scoring import aqi_category, select_windows

SOURCE = "Open-Meteo Air Quality (CAMS) and Weather Forecast"
LIMITATION = "Model forecasts, not CPCB station readings or medical advice."
ACTIVITIES = {
    "run": "run",
    "walk": "walk",
    "cycle": "cycle",
    "commute": "commute",
    "kids": "take children outside",
}


def window_dict(window: Window) -> dict:
    return {
        **asdict(window),
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "aqi_category": aqi_category(window.max_aqi),
    }


@dataclass(frozen=True)
class Recommendation:
    request: RequestSpec
    location: Location
    forecast: Forecast
    window: Window
    backups: tuple[Window, ...] = ()
    venue: dict | None = None

    def to_dict(self):
        current = self.forecast.current
        return {
            "status": "ok",
            "mode": "synthetic-demo" if self.forecast.is_demo else "live",
            "location": asdict(self.location),
            "request": self.request.model_dump(),
            "timezone": self.forecast.timezone,
            "window": {**window_dict(self.window), "assessment": assess(self)},
            "backups": [
                {**window_dict(window), "assessment": assess(replace(self, window=window))}
                for window in self.backups
            ],
            "current": (
                {
                    "time": current.time.isoformat(),
                    "us_aqi": current.us_aqi,
                    "pm2_5": current.pm2_5,
                    "aqi_category": aqi_category(current.us_aqi),
                }
                if current
                else None
            ),
            "fetched_at": self.forecast.fetched_at.isoformat(),
            "source": "Synthetic offline demo" if self.forecast.is_demo else SOURCE,
            "limitation": LIMITATION,
            "summary": describe(self),
            "assessment": assess(self),
            "venue": self.venue,
        }


@dataclass(frozen=True)
class ComparisonItem:
    place: str
    recommendation: Recommendation | None = None
    error: str | None = None


@dataclass(frozen=True)
class ComparisonResult:
    request: RequestSpec
    items: tuple[ComparisonItem, ...]

    @property
    def winner(self) -> str | None:
        return next((item.place for item in self.items if item.recommendation), None)

    @property
    def tied_places(self) -> list[str]:
        valid = [item for item in self.items if item.recommendation]
        if not valid:
            return []
        tied = [
            item.place
            for item in valid
            if isclose(
                item.recommendation.window.score, valid[0].recommendation.window.score, abs_tol=1e-6
            )
        ]
        return tied if len(tied) > 1 else []

    def to_dict(self):
        return {
            "status": "ok" if self.winner else "error",
            "winner": self.winner,
            "partial": any(item.error for item in self.items),
            "tied_places": self.tied_places,
            "request": self.request.model_dump(),
            "summary": describe_comparison(self),
            "places": [
                {"place": item.place, "rank": rank, **item.recommendation.to_dict()}
                if item.recommendation
                else {"place": item.place, "rank": None, "status": "error", "error": item.error}
                for rank, item in enumerate(self.items, start=1)
            ],
        }


def request_prompt(request: RequestSpec) -> str:
    """A complete, stateless recheck request that retains the user's constraints."""
    activity = ACTIVITIES[request.activity]
    if len(request.places) > 1:
        prompt = f"compare {' and '.join(request.places)} for a {request.hours}-hour {activity}"
    else:
        prompt = f"best {request.hours}-hour window to {activity} in {request.place}"
    if request.day != "next48":
        prompt += " " + request.day
    if request.period != "any":
        prompt += " " + request.period
    limits = []
    for field, label, unit in (
        ("max_aqi", "AQI", ""),
        ("max_rain", "rain", "%"),
        ("max_temperature", "feels like", "C"),
        ("max_uv", "UV", ""),
        ("max_wind", "wind", " km/h"),
    ):
        value = getattr(request, field)
        if value is not None:
            limits.append(f"{label} at most {value:g}{unit}")
    if request.daylight_only:
        limits.append("daylight only")
    if request.include_venue:
        limits.append("reviews")
    if limits:
        prompt += " with " + ", ".join(limits)
    return "@blr-air " + prompt


def recheck_guidance(request: RequestSpec) -> str:
    return (
        "**Get an update**\n\n"
        "Send this full request again before leaving:\n\n"
        f"```text\n{request_prompt(request)}\n```\n\n"
        "If you recheck on the outing date, change `tomorrow` to `today`. "
        "Forecasts may be cached for up to 5 minutes. No automatic alerts are scheduled. "
        "Send `@blr-air help` for examples or `@blr-air updates` for reminder options."
    )


def calendar_guidance(result: Recommendation) -> str:
    window, forecast = result.window, result.forecast
    # The reminder is read on the event date, when the original "tomorrow" is "today".
    prompt = request_prompt(result.request.model_copy(update={"day": "today"}))
    details = (
        "Recheck BLR Air before leaving. On the event date, send:\n"
        + prompt
        + "\n\nThis event is a forecast snapshot and does not update itself. "
        + f"Forecast retrieved {forecast.fetched_at.astimezone(UTC):%d %b %Y %H:%M UTC}. "
        + LIMITATION
    )
    if forecast.is_demo:
        details = "OFFLINE DEMO: synthetic data; do not use for outdoor decisions.\n" + details
    query = urlencode(
        {
            "action": "TEMPLATE",
            "text": f"{'DEMO — ' if forecast.is_demo else ''}BLR Air: "
            f"{ACTIVITIES[result.request.activity]} · {result.location.name}",
            "dates": f"{window.start.astimezone(UTC):%Y%m%dT%H%M%SZ}/"
            f"{window.end.astimezone(UTC):%Y%m%dT%H%M%SZ}",
            "ctz": forecast.timezone,
            "location": result.location.name,
            "details": details,
        }
    )
    return (
        "**Save a recheck reminder**\n\n"
        f"[Add this window to Google Calendar](https://calendar.google.com/calendar/render?{query})"
        "\n\nBefore saving, set a notification **1 hour before** to recheck the forecast. "
        "The event description includes your recheck prompt. Nothing is saved until you "
        "confirm it in your calendar. The website's calendar download includes a "
        "one-hour reminder when imported."
    )


def window_time(window: Window, timezone: str) -> str:
    zone = ZoneInfo(timezone)
    start, end = window.start.astimezone(zone), window.end.astimezone(zone)
    return f"{start:%a %d %b %Y} · {start:%H:%M}–{end:%H:%M} ({start:%z})"


def condition_lines(window: Window) -> str:
    return "\n".join(
        [
            f"- **Air:** US AQI {window.us_aqi:.0f} average; "
            f"worst hour {window.max_aqi:.0f} ({aqi_category(window.max_aqi)}).",
            f"- **PM2.5:** {window.pm2_5:.1f} µg/m³ average.",
            f"- **Weather:** rain {window.rain_probability:.0f}% peak hourly chance; "
            f"temperature up to {window.temperature:.1f}°C.",
            "- " + weather_context(window),
        ]
    )


def before_leaving(result: Recommendation) -> str:
    assessment = assess(result)
    notes = [assessment["aqi"]["advice"]]
    # Keep activity-specific precautions, without repeating the generic recheck/access notes.
    notes.extend(assessment["checklist"][2:])
    if result.window.rain_probability >= 70:
        notes.append("Rain is still likely in this window; keep an indoor backup.")
    return "**Before you go**\n\n" + "\n".join("- " + note for note in notes)


def forecast_note(forecast: Forecast) -> str:
    zone = ZoneInfo(forecast.timezone)
    fetched = forecast.fetched_at.astimezone(zone)
    source = "Synthetic offline demo" if forecast.is_demo else SOURCE
    return (
        f"**Forecast retrieved:** {fetched:%d %b %Y, %H:%M} ({forecast.timezone}).\n\n"
        f"Source: {source}. {LIMITATION} Air quality is a regional estimate; "
        "nearby places may share the same forecast."
    )


def describe(result: Recommendation | ComparisonResult) -> str:
    if isinstance(result, ComparisonResult):
        return describe_comparison(result)
    w, q, forecast = result.window, result.request, result.forecast
    sections = [
        f"**{result.location.name}**\n\n"
        f"**Best available {q.hours}-hour window to {ACTIVITIES[q.activity]}**\n\n"
        f"{window_time(w, forecast.timezone)}\n\n"
        f"All times in {forecast.timezone}.",
        "**Conditions during your window**\n\n" + condition_lines(w),
        "**Why this time?**\n\n"
        "Ranked using AQI, PM2.5, rain and heat within your requested time range "
        "and the 05:00–21:00 activity hours.",
    ]
    if forecast.is_demo:
        sections.insert(0, "**OFFLINE DEMO — synthetic data; do not use for outdoor decisions.**")
    if any(key.startswith("max_") and value is not None for key, value in q.model_dump().items()):
        sections.append("Every selected hour meets your requested limits.")
    if q.daylight_only:
        sections.append("Your entire window and backups are in daylight.")
    sections.append(before_leaving(result))
    if result.backups:
        sections.append(
            "**Backup options**\n\n"
            + "\n".join(
                f"- {window_time(backup, forecast.timezone)} — "
                f"AQI {backup.us_aqi:.0f} average; rain {backup.rain_probability:.0f}% peak hourly."
                for backup in result.backups
            )
        )
    current = forecast.current
    if current:
        when = current.time.astimezone(ZoneInfo(forecast.timezone)).strftime("%d %b, %H:%M")
        stale = (
            " (older model estimate)"
            if forecast.fetched_at - current.time > timedelta(hours=3)
            else ""
        )
        sections.append(
            f"**Current model · {when}{stale}**\n\n"
            f"US AQI {current.us_aqi:.0f} ({aqi_category(current.us_aqi)}); "
            f"PM2.5 {current.pm2_5:.1f} µg/m³. These are current estimates, "
            "separate from the recommended window."
        )
    else:
        sections.append("Current air-quality estimate unavailable; the hourly forecast is shown.")
    sections.append(
        "Map: [Open location in Maps]("
        + assess(result)["location"]["maps_url"]
        + ")\n\nConfirm the location and venue opening hours before travelling."
    )
    if result.venue:
        sections.append("**Venue reviews**\n\n" + "\n\n".join(venue_description(result.venue)))
    sections.extend([forecast_note(forecast), calendar_guidance(result), recheck_guidance(q)])
    return "\n\n".join(sections)


def venue_description(venue: dict | None) -> list[str]:
    if not venue:
        return []
    if venue["status"] != "ok":
        return ["Venue reviews: " + venue.get("message", "Unavailable for this place.")]
    lines = ["Venue match: " + ", ".join(filter(None, (venue["name"], venue.get("address"))))]
    if venue.get("rating") is not None:
        count = venue.get("rating_count")
        count_text = (
            f"from {count} ratings"
            if type(count) is int and count > 0
            else "(rating count unavailable)"
        )
        lines.append(
            f"Google Maps customer rating: {venue['rating']}/5 "
            f"{count_text}. This is not an air-quality score."
        )
    if venue.get("match_notice"):
        lines.append(venue["match_notice"])
    lines.append(
        "Confirm venue opening hours for your selected date; "
        "an outdoor forecast does not establish access."
    )
    lines.extend(venue.get("opening_hours") or [])
    lines.append(
        venue.get(
            "review_notice", "Google Maps reviews are a relevance-ranked sample, not all reviews."
        )
    )
    for review in venue.get("reviews", [])[:2]:
        text = review.get("text", "")
        excerpt = text[:700] + ("… [excerpt]" if len(text) > 700 else "")
        lines.append(
            f"{review.get('author', 'Reviewer')} "
            f"({review.get('author_url') or 'Google Maps'}), "
            f"{review.get('published_at') or 'date unavailable'}: {excerpt}"
        )
        if review.get("author_photo_uri"):
            lines.append("Reviewer photo: " + review["author_photo_uri"])
    for attribution in venue.get("attributions", []):
        lines.append(
            "Attribution: "
            + str(
                attribution.get("provider")
                or attribution.get("display_name")
                or attribution.get("displayName")
                or "Google Maps"
            )
            + " "
            + str(attribution.get("provider_uri") or attribution.get("uri") or "")
        )
    if venue.get("google_maps_uri"):
        lines.append("Google Maps: " + venue["google_maps_uri"])
    return lines


def weather_context(window: Window) -> str:
    parts = []
    for label, value, unit in (
        ("Feels like up to", window.apparent_temperature, "°C"),
        ("peak UV", window.uv_index, ""),
        ("wind up to", window.wind_speed, " km/h"),
    ):
        parts.append(f"{label} {value:.1f}{unit}" if value is not None else f"{label}: unavailable")
    parts.append(
        "fully in daylight"
        if window.daylight
        else "not entirely in daylight"
        if window.daylight is False
        else "daylight: unavailable"
    )
    return "; ".join(parts) + "."


def describe_comparison(result: ComparisonResult) -> str:
    lines = [
        f"**Best place: {result.winner or 'none available'}**",
        "Each place is compared at its own best time, using the same pollution/rain/heat score.",
    ]
    if result.tied_places:
        lines.append(
            "Score tie: "
            + ", ".join(result.tied_places)
            + ". The first requested place is shown first; forecasts do not distinguish them."
        )
    if any(item.error for item in result.items):
        lines.append(
            "Some places could not be evaluated; the recommendation covers available results only."
        )
    for rank, item in enumerate(result.items, start=1):
        if item.recommendation is None:
            lines.append(f"{rank}. {item.place}: unavailable — {item.error}")
            continue
        recommendation = item.recommendation
        window = recommendation.window
        lines.append(
            f"**{rank}. {recommendation.location.name}**\n\n"
            f"{window_time(window, recommendation.forecast.timezone)} · "
            f"{recommendation.forecast.timezone}\n\n" + condition_lines(window)
        )
        if recommendation.backups:
            lines.append(
                "**Backup options**\n\n"
                + "\n".join(
                    f"- {window_time(backup, recommendation.forecast.timezone)} — "
                    f"AQI {backup.us_aqi:.0f} average; "
                    f"rain {backup.rain_probability:.0f}% peak hourly."
                    for backup in recommendation.backups
                )
            )
        lines.append(before_leaving(recommendation))
        assessment = assess(recommendation)
        lines.append("Map: [Open location in Maps](" + assessment["location"]["maps_url"] + ")")
        lines.extend(venue_description(recommendation.venue))
        if recommendation.forecast.is_demo:
            lines.append("**OFFLINE DEMO — synthetic data; do not use for outdoor decisions.**")
        lines.append(forecast_note(recommendation.forecast))
        if rank == 1:
            lines.append(calendar_guidance(recommendation))
    lines.append(recheck_guidance(result.request))
    return "\n\n".join(lines)


def spoken_summary(result: Recommendation | ComparisonResult) -> str:
    """A bounded English response for speech; include risk and source, not every backup."""
    if isinstance(result, ComparisonResult):
        selected = next((item.recommendation for item in result.items if item.recommendation), None)
        if selected is None:
            return (
                "No complete outdoor window meets your request. "
                "Please adjust your limits or try again."
            )
        prefix = f"Of the {len(result.items)} places requested, the best available option is "
        if result.tied_places:
            prefix = "The available options are tied. First requested option: "
        if any(item.error for item in result.items):
            prefix = "Some requested places were unavailable. " + prefix
    else:
        selected, prefix = result, "Best available option: "
    w = selected.window
    risk = (
        " Conditions are still adverse; consider an indoor alternative."
        if (w.max_aqi > 100 or w.temperature >= 35 or w.rain_probability >= 70)
        else ""
    )
    source = "synthetic demo data" if selected.forecast.is_demo else "Open Meteo model forecasts"
    return (
        f"{prefix}{selected.location.name}, {w.start:%A %d %B}, "
        f"{w.start:%H:%M} to {w.end:%H:%M}, {selected.forecast.timezone} local time. "
        f"Average US air quality index {w.us_aqi:.0f}, worst hourly category "
        f"{aqi_category(w.max_aqi)}. Maximum hourly rain chance {w.rain_probability:.0f} percent, "
        f"temperature {w.temperature:.0f} degrees Celsius.{risk} "
        f"Source: {source}, retrieved {selected.forecast.fetched_at:%d %B %H:%M} UTC. "
        "Not station readings or medical advice. Forecasts can change."
    )


class AirService:
    def __init__(
        self,
        provider: OpenMeteo,
        client: httpx.AsyncClient,
        *,
        api_key: str | None = None,
        base_url="https://api.asi1.ai/v1",
        venues=None,
    ):
        self.provider = provider
        self.client = client
        self.api_key = api_key
        self.base_url = base_url
        self.venues = venues

    async def recommend(
        self, request: RequestSpec, *, location: Location | None = None, now: datetime | None = None
    ) -> Recommendation:
        venue = None
        if request.include_venue:
            venue = (
                await self.venues.search(request.place)
                if self.venues
                else {
                    "status": "unavailable",
                    "message": "Customer reviews require Google Places access on this server. "
                    "Air and weather forecasts remain available.",
                }
            )
            if venue["status"] == "ok" and location is None:
                location = Location(
                    ", ".join(filter(None, (venue["name"], venue.get("address")))),
                    venue["latitude"],
                    venue["longitude"],
                )
        try:
            async with asyncio.timeout(23):
                location = location or await self.provider.locate(request.place)
                forecast = await self.provider.forecast(location)
                windows = select_windows(
                    forecast.hours,
                    request,
                    forecast.timezone,
                    now or datetime.now(UTC),
                    limit=3,
                    daylight=forecast.daylight,
                )
                return Recommendation(
                    request, location, forecast, windows[0], tuple(windows[1:]), venue
                )
        except TimeoutError as exc:
            raise ProviderError("Forecast lookup timed out. Please try again in a minute.") from exc

    async def compare(
        self, request: RequestSpec, places: list[str], *, now=None
    ) -> ComparisonResult:
        validated = RequestSpec.model_validate({**request.model_dump(), "places": places})
        if not 2 <= len(validated.places) <= 3:
            raise AirError("Compare two or three distinct places.")
        base_now = now or datetime.now(UTC)

        async def one(place):
            try:
                item = await self.recommend(
                    request.model_copy(update={"place": place, "places": []}), now=base_now
                )
                return ComparisonItem(place, item, None)
            except AirError as exc:
                return ComparisonItem(place, None, str(exc))

        items = tuple(await asyncio.gather(*(one(place) for place in places)))
        valid = [item for item in items if item.recommendation is not None]
        valid.sort(key=lambda item: item.recommendation.window.score)
        return ComparisonResult(
            validated, tuple(valid + [item for item in items if item.recommendation is None])
        )

    async def chat(self, text: str) -> Recommendation | ComparisonResult | str:
        text = clean_message(text)
        intent = await chat_intent(text, self)
        if intent.kind in ("answer", "clarify"):
            return intent.text
        if intent.kind == "conditions":
            # Keep unsupported forecast dates/times out of live conditions, too.
            from blr_air.parsing import validate_text

            validate_text(text)
            return await describe_conditions(self, intent)
        request = await parse_request(
            text, self.client, api_key=self.api_key, base_url=self.base_url
        )
        if len(request.places) > 1:
            return await self.compare(request, request.places)
        return await self.recommend(request)
