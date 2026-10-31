import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from blr_air.domain import Forecast, Location, ProviderError, RequestSpec, Window
from blr_air.parsing import parse_request
from blr_air.providers import OpenMeteo
from blr_air.scoring import aqi_category, select_window

SOURCE = "Open-Meteo Air Quality (CAMS) and Weather Forecast"
LIMITATION = "Model forecasts, not CPCB station readings or medical advice."


@dataclass(frozen=True)
class Recommendation:
    request: RequestSpec
    location: Location
    forecast: Forecast
    window: Window

    def to_dict(self):
        current = self.forecast.current
        return {
            "status": "ok",
            "mode": "synthetic-demo" if self.forecast.is_demo else "live",
            "location": asdict(self.location),
            "request": self.request.model_dump(),
            "timezone": self.forecast.timezone,
            "window": {
                **asdict(self.window),
                "start": self.window.start.isoformat(),
                "end": self.window.end.isoformat(),
                "aqi_category": aqi_category(self.window.max_aqi),
            },
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


def describe(result: Recommendation) -> str:
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
    if w.max_aqi > 100:
        lines.append(
            "This is the least-bad available slot; consider an indoor alternative, "
            "especially for children or people sensitive to air pollution."
        )
    if w.temperature >= 35:
        lines.append("Significant heat is forecast even in this slot; consider an indoor activity.")
    if w.rain_probability >= 70:
        lines.append("Rain is still likely in this slot; keep an indoor alternative.")
    lines.extend(
        [
            f"Data: {'Synthetic offline demo' if forecast.is_demo else SOURCE}. "
            f"Retrieved {forecast.fetched_at:%d %b %Y %H:%M UTC}.",
            LIMITATION,
            "Try next: 'best 2-hour cycling window in Koramangala tomorrow morning'.",
        ]
    )
    return "\n".join(lines)


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
                window = select_window(
                    forecast.hours, request, forecast.timezone, now or datetime.now(UTC)
                )
                return Recommendation(request, location, forecast, window)
        except TimeoutError as exc:
            raise ProviderError("Forecast lookup timed out. Please try again in a minute.") from exc

    async def chat(self, text: str) -> Recommendation:
        request = await parse_request(
            text, self.client, api_key=self.api_key, base_url=self.base_url
        )
        return await self.recommend(request)
