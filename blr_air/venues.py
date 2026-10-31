"""Request-scoped Google Places facts and attributed customer reviews.

The adapter never stores review content or treats a star rating as an air-quality
measurement. Consumers must render review text as text, with provider and author
attribution. A best search match still needs its address checked by the user.
"""

import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from blr_air.providers import number

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
FIELD_MASK = ",".join(
    "places." + field
    for field in (
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "rating",
        "userRatingCount",
        "reviews",
        "googleMapsUri",
        "websiteUri",
        "businessStatus",
        "currentOpeningHours",
        "accessibilityOptions",
        "attributions",
    )
)


def _string(value, limit=2048):
    return value if isinstance(value, str) and len(value) <= limit else None


def _object(value):
    return value if isinstance(value, dict) else {}


def _url(value):
    """Only navigable HTTP(S) links; never execute or fetch provider-supplied links."""
    value = _string(value)
    if not value or any(ord(c) < 33 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None
        return value
    except ValueError:
        return None


def _numeric(value, low, high):
    return value if number(value, minimum=low, maximum=high) else None


def _candidate(place):
    name = _string(_object(place.get("displayName")).get("text"), 512)
    point = _object(place.get("location"))
    lat = _numeric(point.get("latitude"), -90, 90)
    lon = _numeric(point.get("longitude"), -180, 180)
    if not name or lat is None or lon is None:
        return None
    return {
        "place_id": _string(place.get("id"), 512),
        "name": name,
        "address": _string(place.get("formattedAddress")),
        "latitude": lat,
        "longitude": lon,
        "google_maps_uri": _url(place.get("googleMapsUri")),
    }


def _reviews(value):
    result = []
    for raw in value[:5] if isinstance(value, list) else []:
        review = _object(raw)
        author = _object(review.get("authorAttribution"))
        name = _string(author.get("displayName"), 512)
        if not name:
            continue
        localized = _object(review.get("text"))
        text = _string(localized.get("text"), 20000)
        result.append(
            {
                "text": text or "",
                "language_code": _string(localized.get("languageCode"), 32),
                "rating": _numeric(review.get("rating"), 1, 5),
                "author": name,
                "author_url": _url(author.get("uri")),
                "author_photo_uri": _url(author.get("photoUri")),
                "published_at": _string(review.get("publishTime"), 64),
                "relative_time": _string(review.get("relativePublishTimeDescription"), 256),
                "google_maps_uri": _url(review.get("googleMapsUri")),
            }
        )
    return result


class GooglePlaces:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self.client = client
        self.api_key = api_key.strip()

    async def search(self, query: str) -> dict:
        """Look up up to three matches; expose the first valid match and its provenance."""
        base = {"source": "Google Maps", "fetched_at": datetime.now(UTC).isoformat()}

        def unavailable(message):
            return {**base, "status": "unavailable", "message": message}

        if not self.api_key:
            return unavailable(
                "Venue ratings and customer reviews require GOOGLE_PLACES_API_KEY "
                "with Places API (New) enabled and billing configured on the server."
            )
        if (
            not isinstance(query, str)
            or not 2 <= len(query.strip()) <= 500
            or any(ord(c) < 32 for c in query)
        ):
            return unavailable("Give a venue name and city, using 2–500 characters.")
        query = query.strip()
        try:
            async with (
                asyncio.timeout(12),
                self.client.stream(
                    "POST",
                    SEARCH_URL,
                    headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK},
                    json={"textQuery": query, "pageSize": 3, "languageCode": "en"},
                    timeout=httpx.Timeout(8, connect=4),
                    follow_redirects=False,
                ) as response,
            ):
                if response.status_code in (401, 403):
                    return unavailable(
                        "Google Places access was denied. Check the server key, "
                        "API restrictions, Places API (New) activation and billing."
                    )
                if response.status_code == 429:
                    return unavailable("Google Places quota is exhausted. Please try again later.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        return unavailable(
                            "Google Places returned too much data. Try a specific venue."
                        )
                    body.extend(chunk)
                payload = json.loads(body)
                if response.status_code == 400:
                    details = _object(_object(payload).get("error")).get("details")
                    reasons = (
                        {item.get("reason") for item in details if isinstance(item, dict)}
                        if isinstance(details, list)
                        else set()
                    )
                    if "API_KEY_INVALID" in reasons:
                        return unavailable(
                            "Google Places rejected the server API key. "
                            "Configure a valid Google Cloud key for Places API (New)."
                        )
                    return unavailable(
                        "Google Places could not accept this venue lookup. "
                        "Check the server API configuration."
                    )
                response.raise_for_status()
            if not isinstance(payload, dict) or payload.get("error"):
                raise ValueError("Invalid response")
            places = payload.get("places")
            if places is None or places == []:
                return {
                    **base,
                    "status": "not_found",
                    "query": query,
                    "message": "No matching venue found. Add the city or street to the venue name.",
                }
            if not isinstance(places, list):
                raise ValueError("Invalid places")
            valid = []
            for raw in places[:3]:
                place = _object(raw)
                candidate = _candidate(place)
                if candidate:
                    valid.append((place, candidate))
            if not valid:
                raise ValueError("No usable matches")
            place, candidate = valid[0]
            opening = _object(place.get("currentOpeningHours"))
            descriptions = opening.get("weekdayDescriptions")
            opening_hours = (
                [line for line in descriptions[:7] if _string(line, 1024)]
                if isinstance(descriptions, list)
                else []
            )
            accessible = _object(place.get("accessibilityOptions"))
            accessibility = {
                key: accessible[key]
                for key in (
                    "wheelchairAccessibleParking",
                    "wheelchairAccessibleEntrance",
                    "wheelchairAccessibleRestroom",
                    "wheelchairAccessibleSeating",
                )
                if type(accessible.get(key)) is bool
            }
            raw_attributions = place.get("attributions")
            attributions = (
                [
                    {
                        "provider": _string(item.get("provider"), 512),
                        "provider_uri": _url(item.get("providerUri")),
                    }
                    for item in raw_attributions
                    if isinstance(item, dict) and _string(item.get("provider"), 512)
                ]
                if isinstance(raw_attributions, list)
                else []
            )
            count = place.get("userRatingCount")
            return {
                **base,
                **candidate,
                "status": "ok",
                "query": query,
                "matched_name": candidate["name"],
                "match_notice": "First Google search match shown; check its name and address. "
                "Search relevance does not certify outdoor suitability.",
                "candidates": [item for _, item in valid],
                "rating": _numeric(place.get("rating"), 1, 5),
                "rating_count": count if type(count) is int and 0 <= count <= 100000000 else None,
                "reviews": _reviews(place.get("reviews")),
                "review_notice": "Up to five Google customer reviews, selected by relevance; "
                "this is a sample, not all reviews or a representative sentiment survey.",
                "website_uri": _url(place.get("websiteUri")),
                "business_status": _string(place.get("businessStatus"), 64),
                "opening_hours": opening_hours,
                "open_now": opening.get("openNow")
                if type(opening.get("openNow")) is bool
                else None,
                "hours_notice": "Opening status is for now, not the recommended forecast window. "
                "Confirm access hours with the venue before travelling.",
                "accessibility": accessibility,
                "attributions": attributions,
            }
        except (TimeoutError, httpx.TimeoutException):
            return unavailable("Google Places lookup timed out. Please try again.")
        except httpx.HTTPError:
            return unavailable("Google Places is unavailable. Please try again later.")
        except (ValueError, TypeError, KeyError, UnicodeError):
            return unavailable("Google Places returned incomplete venue data. Please try again.")
