# Venue ratings and customer reviews

Research date: **31 October 2026**. This is a bounded review of official Google
Places documentation for the requested venue feature, not an exhaustive vendor
comparison or proof that live account access has been configured.

## Implementation decision

Use **Google Places API (New), Text Search** for a user-supplied venue name and
city. One server-side request returns at most three matches, a matched name and
address, coordinates, rating/count, up to five attributed customer reviews,
Google Maps and venue links, present opening status, weekly opening descriptions,
business status and reported wheelchair-accessibility fields. The first valid
search match is disclosed; name/address and other candidates let users detect a
wrong location. Search ranking is Google's relevance ranking, not BLR Air's
outdoor-suitability score.

The adapter is `blr_air/venues.py`:

```python
venue = await GooglePlaces(client, api_key).search("Cubbon Park, Bengaluru")
```

It returns a JSON-safe dictionary with `status="ok"`, `"not_found"`, or
`"unavailable"`. All responses identify Google Maps and their retrieval time.
Missing API access does not fabricate venue ratings or disable weather data.
Unknown values stay `None`/empty; `open_now=False` is preserved rather than
mistaken for missing data. `open_now` is not proof that a venue will be open at a
recommended forecast time. Checking full opening intervals against selected
windows is not implemented in this adapter.

The server needs **`GOOGLE_PLACES_API_KEY`**, with **Places API (New)** enabled
and Google Cloud billing configured. Restrict the key to that API and the
server's network where practical. Keep it out of browser code. The explicit
field mask avoids a wildcard, but reviews still invoke the **Text Search
Enterprise + Atmosphere** SKU; this is a paid-capable request, not a keyless API.
No Google account key or live access was available to this implementation task.

## Evidence and constraints

| Claim | Primary source and section | Implementation consequence |
|---|---|---|
| Text Search accepts `POST /v1/places:searchText` with `textQuery`, `pageSize`, and required field mask | [Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search), required parameters and `pageSize` | Use `X-Goog-Api-Key`, `X-Goog-FieldMask`, `pageSize: 3`, `languageCode: en`; no pagination or background fetching |
| `places.reviews` invokes Enterprise + Atmosphere; ratings/opening fields invoke Enterprise | Same reference, response field-mask SKU lists | Request the needed fields explicitly; disclose paid access requirement |
| A place returns at most five reviews, sorted by relevance | [Place REST resource](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places), `reviews` | Mark it as a relevance-selected sample, never all reviews or a representative sentiment survey |
| Reviews include text, original text, rating, author attribution, publication time and Maps link | Same reference, `Review` and `AuthorAttribution` | Preserve the returned review text as untrusted text; expose language, author name/profile/avatar, date and review link. The requested English locale may yield translated text |
| Current hours cover the next seven days and account for special hours; `openNow` concerns the present | Same reference, `currentOpeningHours` and `OpeningHours` | Show hours with an explicit present-time qualifier; do not equate them with eligibility of a future forecast window |
| Wheelchair parking, entrance, restroom and seating are optional booleans | Same reference, `AccessibilityOptions` | Preserve true/false; absence means unknown, never inaccessible or accessible by inference |
| A key, enabled API and billing account are required | [Set up Places API (New)](https://developers.google.com/maps/documentation/places/web-service/get-api-key), setup and key restrictions | Server-side optional integration with an actionable missing-access state |
| Google Maps and third-party attribution must accompany displayed results | [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies), Google Maps logo/text attribution, third-party attribution | Identify Google Maps near venue results; use official logo assets when possible, permitted text attribution where space is limited; display provider attributions |
| Review authors must be credited, including available avatar/name/profile resources | Same policies, Photos and reviews | Expose `author_photo_uri`, `author`, `author_url`; render them adjacent to their review |
| Places content cannot be cached or stored beyond permitted exceptions; public terms/privacy are required | Same policies, pre-fetching/caching and terms/privacy sections | No persistent adapter cache; avoid storing review content in usage logs or local storage. Public application terms/privacy must reference Google's terms/privacy |
| Google venue results shown on a map must use a Google map | Same policies, displaying results on a map | Keep venue content in a separate attributed text panel; do not plot these results onto the site's illustrative non-Google city map |

Customer stars are evidence of customer opinion, **not** air quality, personal
safety, accessibility certification or suitability for a child. BLR Air must
present these alongside its independently sourced weather assessment without
mixing them into a fabricated medical score. Missing venue data must remain an
explicit limitation.

## Reliability and verification

The adapter uses only the fixed HTTPS Google endpoint, disables redirects,
bounds the response to 2 MiB, limits connection/read timeouts and the overall
request to 12 seconds, and performs no automatic retry of paid requests.
Provider errors never include the provider response body or the API key.
Returned links allow only HTTP(S), reject embedded credentials/control
characters, and are never fetched by this adapter. Consumers must use
`textContent`/equivalent safe text rendering for provider names/reviews and
`rel="noopener noreferrer"` for external links.

24 focused tests passed after first being run against the missing adapter.
They exercise the actual HTTP request boundary and field mask, raw review
preservation and attribution, missing credentials, no match, malformed data,
HTTP 401/403/429/500, timeouts, redirect refusal, unknown values, unsafe links,
query and response bounds, candidate/review caps and missing review authors.
These are controlled transport tests, not a claim of live Google availability.

## Retrieval log

Public `urllib.request` fetched these exact URLs on 2026-10-31. The first pass
retrieved Text Search, Place resource and policies with HTTP 200. A second pass
began at **09:38:09 UTC** and fetched all four URLs with HTTP 200:

- `https://developers.google.com/maps/documentation/places/web-service/text-search`
- `https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places`
- `https://developers.google.com/maps/documentation/places/web-service/policies`
- `https://developers.google.com/maps/documentation/places/web-service/get-api-key`

Exact in-document search terms: `X-Goog-FieldMask`, `reviews`,
`accessibilityOptions`, `currentOpeningHours`, `authorAttribution`,
`A maximum of 5`, `sorted by relevance`, `weekdayDescriptions`, `openNow`,
`pageSize`, `Enterprise + Atmosphere`, `places.reviews`, `billing`,
`Google Maps logo`, `text attribution`, `must not pre-fetch`, and `avatar`.
No credentials were used for these documentation requests.
