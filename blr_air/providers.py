import asyncio
import math
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from blr_air.domain import CurrentAir, Forecast, Hour, Location, LocationError, ProviderError
from blr_air.localities import local_location

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def number(value, *, minimum=0, maximum=10000):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and minimum <= value <= maximum
    )


def hourly_map(payload, fields):
    hourly = payload["hourly"]
    timestamps = hourly["time"]
    if not isinstance(timestamps, list) or any(
        not isinstance(hourly[field], list) or len(hourly[field]) != len(timestamps)
        for field in fields
    ):
        raise ValueError("Invalid hourly arrays")
    return {
        datetime.fromtimestamp(t, UTC): values
        for t, *values in zip(timestamps, *(hourly[field] for field in fields), strict=True)
        if number(t, maximum=4102444800)
    }


def merge_forecasts(aq: dict, wx: dict, fetched_at: datetime) -> Forecast:
    try:
        timezone = wx["timezone"]
        ZoneInfo(timezone)
        air = hourly_map(aq, ("us_aqi", "pm2_5"))
        weather = hourly_map(wx, ("precipitation_probability", "temperature_2m"))
        extra = {}
        for field in ("apparent_temperature", "uv_index", "wind_speed_10m"):
            if field in wx["hourly"]:
                extra[field] = hourly_map(wx, (field,))

        def optional(field, timestamp, minimum=0, maximum=200):
            value = extra.get(field, {}).get(timestamp, [None])[0]
            return value if number(value, minimum=minimum, maximum=maximum) else None

        daylight = []
        daily = wx.get("daily") or {}
        for rise, setting in zip(daily.get("sunrise", []), daily.get("sunset", []), strict=False):
            if (
                number(rise, minimum=1, maximum=4102444800)
                and number(setting, minimum=1, maximum=4102444800)
                and setting > rise
            ):
                daylight.append(
                    (datetime.fromtimestamp(rise, UTC), datetime.fromtimestamp(setting, UTC))
                )
        rows = []
        for timestamp, (aqi, pm) in sorted(air.items()):
            if timestamp not in weather:
                continue
            rain, temp = weather[timestamp]
            if (
                number(aqi)
                and number(pm)
                and number(rain, maximum=100)
                and number(temp, minimum=-100, maximum=70)
            ):
                rows.append(
                    Hour(
                        timestamp,
                        aqi,
                        pm,
                        rain,
                        temp,
                        optional("apparent_temperature", timestamp, -100, 100),
                        optional("uv_index", timestamp, 0, 100),
                        optional("wind_speed_10m", timestamp, 0, 500),
                    )
                )
        current = None
        raw = aq.get("current") or {}
        if (
            number(raw.get("time"), maximum=4102444800)
            and number(raw.get("us_aqi"))
            and number(raw.get("pm2_5"))
        ):
            current = CurrentAir(
                datetime.fromtimestamp(raw["time"], UTC), raw["us_aqi"], raw["pm2_5"]
            )
        if not rows:
            raise ValueError("No complete forecast hours")
        return Forecast(tuple(rows), current, timezone, fetched_at, daylight=tuple(daylight))
    except (KeyError, TypeError, ValueError, OverflowError, ZoneInfoNotFoundError) as exc:
        raise ProviderError(
            "Open-Meteo returned incomplete forecast data. Please try again shortly."
        ) from exc


class OpenMeteo:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self._cache: dict[tuple, tuple[float, Forecast]] = {}

    async def get_json(self, url: str, params: dict) -> dict:
        for attempt in range(3):
            try:
                response = await self.client.get(url, params=params, timeout=6)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or data.get("error"):
                    raise ValueError("Invalid provider response")
                return data
            except httpx.HTTPStatusError as exc:
                retry = exc.response.status_code in (429, 500, 502, 503, 504)
                if not retry or attempt == 2:
                    break
            except httpx.RequestError:
                if attempt == 2:
                    break
            except ValueError:
                break
            await asyncio.sleep(0.2 * (attempt + 1))
        raise ProviderError(
            "Open-Meteo is unavailable or rate-limited. Please try again in a minute."
        )

    async def locate(self, place: str) -> Location:
        if result := local_location(place):
            return result
        parts = [part.strip() for part in place.split(",") if part.strip()]
        data = await self.get_json(
            GEOCODING_URL, {"name": parts[0], "count": 10, "language": "en", "format": "json"}
        )
        for hit in data.get("results") or []:
            qualifiers = {
                str(hit.get(field, "")).casefold()
                for field in ("admin1", "admin2", "country", "country_code")
            }
            aliases = {"uk": "gb", "usa": "us", "u.s.": "us", "u.k.": "gb"}
            if any(
                aliases.get(part.casefold(), part.casefold()) not in qualifiers
                for part in parts[1:]
            ):
                continue
            if not number(hit.get("latitude"), minimum=-90, maximum=90) or not number(
                hit.get("longitude"), minimum=-180, maximum=180
            ):
                continue
            name = ", ".join(
                dict.fromkeys(
                    str(hit[key]) for key in ("name", "admin1", "country") if hit.get(key)
                )
            )
            return Location(name, hit["latitude"], hit["longitude"], hit.get("timezone"))
        raise LocationError(
            f"I couldn't find '{place}'. Try a city, 'city, country', or a Bengaluru locality "
            "such as HSR Layout or Whitefield."
        )

    async def forecast(self, location: Location) -> Forecast:
        key = (round(location.latitude, 4), round(location.longitude, 4))
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1]
        common = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "forecast_days": 4,
            "timezone": "auto",
            "timeformat": "unixtime",
        }
        aq, wx = await asyncio.gather(
            self.get_json(AIR_URL, {**common, "current": "us_aqi,pm2_5", "hourly": "us_aqi,pm2_5"}),
            self.get_json(
                WEATHER_URL,
                {
                    **common,
                    "hourly": "precipitation_probability,temperature_2m,"
                    "apparent_temperature,uv_index,wind_speed_10m",
                    "daily": "sunrise,sunset",
                    "wind_speed_unit": "kmh",
                },
            ),
        )
        forecast = merge_forecasts(aq, wx, datetime.now(UTC))
        if len(self._cache) >= 128:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (time.monotonic(), forecast)
        return forecast
