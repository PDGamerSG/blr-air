import json

import httpx
import pytest


def venue():
    return {
        "id": "park-123",
        "displayName": {"text": "Cubbon Park", "languageCode": "en"},
        "formattedAddress": "Bengaluru, Karnataka, India",
        "location": {"latitude": 12.9763, "longitude": 77.5929},
        "rating": 4.4,
        "userRatingCount": 201,
        "googleMapsUri": "https://maps.google.com/?cid=123",
        "websiteUri": "https://example.org/park",
        "businessStatus": "OPERATIONAL",
        "currentOpeningHours": {"openNow": False, "weekdayDescriptions": ["Monday: 6–18"]},
        "accessibilityOptions": {"wheelchairAccessibleEntrance": True},
        "attributions": [{"provider": "Example provider", "providerUri": "https://example.org"}],
        "reviews": [
            {
                "text": {"text": "Shaded paths. Busy at weekends.", "languageCode": "en"},
                "originalText": {"text": "Shaded paths. Busy at weekends.", "languageCode": "en"},
                "rating": 4,
                "authorAttribution": {
                    "displayName": "Reviewer",
                    "uri": "https://maps.google.com/user/1",
                    "photoUri": "https://example.org/avatar.png",
                },
                "publishTime": "2026-10-01T10:00:00Z",
                "relativePublishTimeDescription": "a month ago",
                "googleMapsUri": "https://maps.google.com/reviews/1",
            }
        ],
    }


async def test_search_uses_authenticated_fixed_host_and_preserves_real_review_attribution():
    from blr_air.venues import GooglePlaces

    def respond(request):
        assert str(request.url) == "https://places.googleapis.com/v1/places:searchText"
        assert request.headers["x-goog-api-key"] == "private-test-key"
        mask = set(request.headers["x-goog-fieldmask"].split(","))
        assert {
            "places.reviews",
            "places.attributions",
            "places.location",
            "places.currentOpeningHours",
            "places.accessibilityOptions",
        } <= mask
        assert "*" not in mask
        assert json.loads(request.content) == {
            "textQuery": "Cubbon Park, Bengaluru",
            "pageSize": 3,
            "languageCode": "en",
        }
        return httpx.Response(200, json={"places": [venue()]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await GooglePlaces(client, "private-test-key").search(" Cubbon Park, Bengaluru ")
    assert result["status"] == "ok"
    assert result["latitude"] == 12.9763 and result["longitude"] == 77.5929
    assert result["rating"] == 4.4 and result["rating_count"] == 201
    assert result["matched_name"] == "Cubbon Park"
    assert result["query"] == "Cubbon Park, Bengaluru"
    assert result["reviews"][0]["text"] == "Shaded paths. Busy at weekends."
    assert result["reviews"][0]["author"] == "Reviewer"
    assert result["reviews"][0]["author_photo_uri"] == "https://example.org/avatar.png"
    assert result["open_now"] is False
    assert result["accessibility"]["wheelchairAccessibleEntrance"] is True
    assert result["source"] == "Google Maps"
    assert result["fetched_at"]


async def test_missing_key_never_calls_google():
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("network"))
    ) as client:
        result = await GooglePlaces(client, "").search("Cubbon Park")
    assert result["status"] == "unavailable" and "GOOGLE_PLACES_API_KEY" in result["message"]


@pytest.mark.parametrize("payload", [{}, {"places": []}, {"places": None}])
async def test_no_results_never_invents_a_venue(payload):
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Unfindable park")
    assert result["status"] == "not_found"


@pytest.mark.parametrize(
    "payload",
    [[], {"places": "bad"}, {"places": [None]}, {"places": [{}]}, {"error": {"message": "SECRET"}}],
)
async def test_malformed_response_fails_explicitly(payload):
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "unavailable"
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_http_failures_are_sanitized(status):
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, text="private-test-key"))
    ) as client:
        result = await GooglePlaces(client, "private-test-key").search("Cubbon Park")
    assert result["status"] == "unavailable"
    assert "private-test-key" not in json.dumps(result)


async def test_timeout_is_actionable():
    from blr_air.venues import GooglePlaces

    def respond(request):
        raise httpx.ReadTimeout("secret", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "unavailable" and "timed out" in result["message"]
    assert "secret" not in json.dumps(result)


async def test_redirect_is_not_followed_even_if_client_allows_it():
    from blr_air.venues import GooglePlaces

    def respond(request):
        assert request.url.host == "places.googleapis.com"
        return httpx.Response(302, headers={"location": "https://attacker.invalid/"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "unavailable"


async def test_missing_fields_remain_unknown_and_unsafe_links_are_removed():
    from blr_air.venues import GooglePlaces

    item = venue()
    item.update(
        rating=True, userRatingCount=-5, currentOpeningHours=None, accessibilityOptions=None
    )
    item["websiteUri"] = "javascript:alert(1)"
    item["googleMapsUri"] = "https://user:password@example.org/"
    item["reviews"][0]["authorAttribution"]["uri"] = "data:text/html,bad"
    item["reviews"][0]["text"]["text"] = "<script>untrusted review</script>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"places": [item]}))
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "ok"
    assert result["rating"] is None and result["rating_count"] is None
    assert result["open_now"] is None and result["accessibility"] == {}
    assert result["website_uri"] is None and result["google_maps_uri"] is None
    assert result["reviews"][0]["author_url"] is None
    assert result["reviews"][0]["text"] == "<script>untrusted review</script>"


async def test_candidate_and_review_counts_are_bounded_and_explain_relevance_sample():
    from blr_air.venues import GooglePlaces

    item = venue()
    item["reviews"] *= 10
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"places": [item] * 10}))
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Park")
    assert len(result["reviews"]) == 5
    assert len(result["candidates"]) == 3
    assert "relevance" in result["review_notice"]
    assert "match" in result["match_notice"]


@pytest.mark.parametrize("query", ["", "a", "x" * 501, "park\x00"])
async def test_invalid_query_does_not_issue_paid_request(query):
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("network"))
    ) as client:
        result = await GooglePlaces(client, "test-key").search(query)
    assert result["status"] == "unavailable"


async def test_unbounded_response_is_stopped():
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        )
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "unavailable"


async def test_reviews_without_author_are_not_rendered_as_customer_evidence():
    from blr_air.venues import GooglePlaces

    item = venue()
    item["reviews"][0]["authorAttribution"] = None
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"places": [item]}))
    ) as client:
        result = await GooglePlaces(client, "test-key").search("Cubbon Park")
    assert result["status"] == "ok" and result["reviews"] == []


async def test_google_invalid_key_400_is_actionable_without_echoing_provider_body():
    from blr_air.venues import GooglePlaces

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                400,
                json={
                    "error": {"message": "private-key", "details": [{"reason": "API_KEY_INVALID"}]}
                },
            )
        )
    ) as client:
        result = await GooglePlaces(client, "private-key").search("Cubbon Park")
    assert result["status"] == "unavailable"
    assert "key" in result["message"].lower()
    assert "private-key" not in str(result)
