import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from math import isclose
from zoneinfo import ZoneInfo

import httpx

from blr_air.domain import AirError, Forecast, Location, ProviderError, RequestSpec, Window
from blr_air.parsing import parse_request
from blr_air.providers import OpenMeteo
from blr_air.scoring import aqi_category, select_windows

SOURCE = "Open-Meteo Air Quality (CAMS) and Weather Forecast"
LIMITATION = "Model forecasts, not CPCB station readings or medical advice."


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

    def to_dict(self):
        current = self.forecast.current
        return {
            "status": "ok",
            "mode": "synthetic-demo" if self.forecast.is_demo else "live",
            "location": asdict(self.location),
            "request": self.request.model_dump(),
            "timezone": self.forecast.timezone,
            "window": window_dict(self.window),
            "backups": [window_dict(window) for window in self.backups],
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


def describe(result: Recommendation | ComparisonResult) -> str:
    if isinstance(result, ComparisonResult):
        return describe_comparison(result)
    w, q, forecast = result.window, result.request, result.forecast
    activity = {
        "run": "run",
        "walk": "walk",
        "cycle": "cycle",
        "commute": "commute",
        "kids": "take children outside",
    }[q.activity]
    lines = [f"{result.location.name} · {forecast.timezone}"]
    if forecast.is_demo:
        lines.insert(0, "OFFLINE DEMO — synthetic data; do not use for outdoor decisions.")
    current = forecast.current
    if current:
        when = current.time.astimezone(ZoneInfo(forecast.timezone)).strftime("%d %b %H:%M")
        stale = (
            " (older model estimate)"
            if forecast.fetched_at - current.time > timedelta(hours=3)
            else ""
        )
        lines.append(
            f"Current model at {when}{stale}: US AQI {current.us_aqi:.0f} "
            f"({aqi_category(current.us_aqi)}), PM2.5 {current.pm2_5:.1f} µg/m³."
        )
    else:
        lines.append("Current air-quality estimate unavailable; hourly forecast shown below.")
    lines.extend(
        [
            f"Best available {q.hours}-hour window to {activity}: "
            f"{w.start:%a %d %b %Y, %H:%M}–{w.end:%H:%M} ({w.start:%z}).",
            f"Average US AQI {w.us_aqi:.0f}; PM2.5 {w.pm2_5:.1f} µg/m³. "
            f"Peak hourly rain chance {w.rain_probability:.0f}%; "
            f"temperature up to {w.temperature:.1f}°C.",
            f"Worst hourly AQI: {w.max_aqi:.0f} ({aqi_category(w.max_aqi)}).",
            "Ranked by air pollution, rain and heat among complete windows "
            "between 05:00–21:00 local.",
        ]
    )
    if result.backups:
        lines.append("Backup windows:")
        lines.extend(
            f"- {backup.start:%a %d %b %H:%M}–{backup.end:%H:%M} ({backup.start:%z}), "
            f"avg AQI {backup.us_aqi:.0f}, peak rain {backup.rain_probability:.0f}%"
            for backup in result.backups
        )
    lines.append(weather_context(w))
    active_limits = {
        key: value
        for key, value in q.model_dump().items()
        if key.startswith("max_") and value is not None
    }
    if active_limits or q.daylight_only:
        lines.append(
            "All selected windows meet your requested limits"
            + (" and lie entirely between sunrise and sunset." if q.daylight_only else ".")
        )
    if w.max_aqi > 100:
        lines.append(
            "This is the least-bad available slot; consider an indoor alternative, "
            "especially for children or people sensitive to air pollution."
        )
    if w.temperature >= 35:
        lines.append("Significant heat is forecast even in this slot; consider an indoor activity.")
    if w.rain_probability >= 70:
        lines.append("Rain is still likely in this slot; keep an indoor alternative.")
    if w.uv_index is not None and w.uv_index >= 3:
        lines.append("UV index is 3 or above: plan shade and sun protection.")
    lines.extend(
        [
            f"Data: {'Synthetic offline demo' if forecast.is_demo else SOURCE}. "
            f"Retrieved {forecast.fetched_at:%d %b %Y %H:%M UTC}.",
            LIMITATION,
            "Try next: 'best 2-hour cycling window in Koramangala tomorrow morning'.",
        ]
    )
    return "\n".join(lines)


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
        f"Best place: {result.winner or 'none available'}",
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
            f"{rank}. {recommendation.location.name} · {recommendation.forecast.timezone}: "
            f"{window.start:%a %d %b %H:%M}–{window.end:%H:%M} ({window.start:%z}), "
            f"avg AQI {window.us_aqi:.0f}, PM2.5 {window.pm2_5:.1f} µg/m³, "
            f"peak rain {window.rain_probability:.0f}%, temperature {window.temperature:.1f}°C. "
            f"Worst AQI: {aqi_category(window.max_aqi)}."
        )
        for backup in recommendation.backups:
            lines.append(
                f"  Backup: {backup.start:%a %d %b %H:%M}–{backup.end:%H:%M} "
                f"({backup.start:%z}), avg AQI {backup.us_aqi:.0f}, "
                f"peak rain {backup.rain_probability:.0f}%."
            )
        lines.append("  " + weather_context(window))
        if window.max_aqi > 100 or window.temperature >= 35 or window.rain_probability >= 70:
            lines.append("  Conditions remain adverse; consider an indoor alternative.")
        lines.append(
            f"  Data: {'Synthetic offline demo' if recommendation.forecast.is_demo else SOURCE}. "
            f"Retrieved {recommendation.forecast.fetched_at:%d %b %Y %H:%M UTC}."
        )
    lines.append(LIMITATION)
    return "\n".join(lines)


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
    ):
        self.provider = provider
        self.client = client
        self.api_key = api_key
        self.base_url = base_url

    async def recommend(
        self, request: RequestSpec, *, location: Location | None = None, now: datetime | None = None
    ) -> Recommendation:
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
                return Recommendation(request, location, forecast, windows[0], tuple(windows[1:]))
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

    async def chat(self, text: str) -> Recommendation | ComparisonResult:
        request = await parse_request(
            text, self.client, api_key=self.api_key, base_url=self.base_url
        )
        if len(request.places) > 1:
            return await self.compare(request, request.places)
        return await self.recommend(request)
