"""Measured air from nearby monitors, through the World Air Quality Index project.

The feed answers every query with *some* station (its demo token returns Shanghai for Delhi),
so a reading only counts when the station is close to the place being asked about.
"""

import math
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

FEED_URL = "https://api.waqi.info/feed/geo:{latitude};{longitude}/"
LOCAL_KM = 6.0
MAX_AGE = timedelta(hours=3)
CACHE_SECONDS = 600


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class StationReading:
    name: str
    aqi: int
    distance_km: float


def parse_station(payload: dict, latitude: float, longitude: float, now: datetime):
    """A usable nearby reading, or None; a missing station is never treated as clean air."""
    try:
        if payload.get("status") != "ok":
            return None
        data = payload["data"]
        aqi = data["aqi"]
        if isinstance(aqi, bool) or not isinstance(aqi, int) or not 0 <= aqi <= 2000:
            return None
        lat, lon = data["city"]["geo"]
        distance = distance_km(latitude, longitude, lat, lon)
        if distance > LOCAL_KM or now - datetime.fromisoformat(data["time"]["iso"]) > MAX_AGE:
            return None
        return StationReading(data["city"]["name"].split(",")[0], aqi, distance)
    except (KeyError, TypeError, ValueError):
        return None


class StationFeed:
    def __init__(self, client: httpx.AsyncClient, token: str | None = None):
        self.client = client
        self.token = (token if token is not None else os.getenv("WAQI_TOKEN", "")).strip()
        self._cache: dict[tuple, tuple[float, StationReading | None]] = {}

    async def near(self, latitude: float, longitude: float) -> StationReading | None:
        if not self.token:
            return None
        key = (round(latitude, 3), round(longitude, 3))
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            response = await self.client.get(
                FEED_URL.format(latitude=latitude, longitude=longitude),
                params={"token": self.token},
                timeout=8,
            )
            response.raise_for_status()
            reading = parse_station(response.json(), latitude, longitude, datetime.now(UTC))
        except (httpx.HTTPError, ValueError):
            # Stations add evidence; losing one must not block the recommendation.
            return None
        if len(self._cache) >= 256:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (time.monotonic(), reading)
        return reading
