# BLR Air feature opportunities

Research date: **2026-10-31**. This is a bounded public-source screen, not a
systematic review. Comparison and backup windows were being added alongside
this research; the recommendations below guided the remaining feature work.

## Prioritized recommendations

### 1. Add user-configurable ceilings (P0)

Let a request express hard limits, then rank only complete windows that satisfy
all limits. If none qualify, return `status="error"` with the closest observed
conditions and the unmet limits. This makes the recommendation useful for a
runner, a child-care plan, or a commute without pretending that one universal
score fits everyone.

Suggested fields (optional, bounded and in the user's units):

```text
max_us_aqi: 0..500
max_rain_probability: 0..100 (%)
max_apparent_temperature: -80..70 (°C)
max_wind_speed: 0..200 (km/h), optional for cycling
max_uv_index: 0..30, optional for sun-sensitive plans
```

The typed `WindowRequest` and local `RequestSpec` should carry the same fields.
The provider must request `apparent_temperature`, `wind_speed_10m` and (when
used) `uv_index` in addition to the current AQI/PM2.5 and rain fields. Missing
values fail closed for that hour; they must not be treated as zero.

This is a preference/eligibility feature, not a medical rule. The UI should say
that a ceiling is user-selected and that modelled AQI is not a guarantee of
safety. EPA's AQI categories are useful explanatory labels, but they do not
turn a forecast into personalised advice.

### 2. Add daylight, UV and apparent-temperature context (P1)

Expose the selected block's mean/peak `apparent_temperature`, `uv_index`, and
whether it is in daylight. Include daily `sunrise`, `sunset`, and
`daylight_duration` in the forecast response so a user can ask for “daylight
only” or understand why a cooler slot is still high-UV. Open-Meteo defines
apparent temperature as a perceived value combining wind chill, humidity and
solar radiation; its UV values are an index, with a clear-sky variant.

Suggested response fields:

```text
apparent_temperature: float
max_apparent_temperature: float
uv_index: float
max_uv_index: float
sunrise: ISO-8601 timestamp | null
sunset: ISO-8601 timestamp | null
daylight: bool
```

Use plain educational wording: WHO's public guidance describes UVI 0–2 as low,
3–7 as a range where midday shade/clothing/sunscreen are advised, and 8+ as a
range where avoiding midday exposure and seeking shade are advised. Do not
derive a dose, burn time, or disease risk from UVI, skin type, AQI, or activity
duration. The existing 05:00–21:00 rule is an activity-hours preference, so a
`daylight_only` option should be explicit rather than silently changing it.

Open-Meteo warns that timestamps use the requested offset fixed at request time;
DST changes inside a range are ignored unless the client requests Unix time and
converts with the returned IANA zone. Bengaluru currently has no DST, but this
matters for global locations. Keep the existing offset-aware conversion and add
tests for a DST location before exposing daylight windows globally.

### 3. Export a selected window to a calendar (P1)

Offer a `.ics`/iCalendar export after a recommendation. Emit one
`VEVENT` with UTC `DTSTART`/`DTEND` (retaining the location's IANA zone in its description), a short summary, the
location, retrieval time, source, and a note that conditions can change. This
turns an answer into an action without storing a user's calendar credentials.

For recurring plans, create a local reminder/watch that re-runs the forecast and
creates a fresh event rather than publishing a stale `RRULE` forecast far into
the future. RFC 5545 defines `VEVENT`, `DTSTART`, `DTEND`, `TZID`, and `RRULE`,
but recurrence semantics do not make future weather predictable. A safe first
version is a single event plus an optional reminder to re-check 3–6 hours before
start; add true recurring events only when each occurrence is re-evaluated.

## Neo4j decision

**Do not add Neo4j for the current window-selection task.** The service joins two
hourly arrays at one coordinate, filters contiguous blocks, and applies a small
deterministic score. SQLite (already used for aggregate usage) or in-memory
structures are simpler, cheaper, and easier to operate. A graph would not make
that calculation more accurate.

Neo4j becomes justified only for a later route-aware feature with a maintained
network and segment-level exposure data. A possible model is:

```text
(:Place {id, point})-[:ROAD {distance_m, time_s, aqi_cost}]->(:Place)
(:RoadSegment {id, distance_m})-[:FROM]->(:Place)
(:RoadSegment)-[:TO]->(:Place)
(:RoadSegment)-[:HAS_FORECAST]->(:SegmentForecast {valid_from, valid_to, us_aqi, pm2_5})
```

Then a route request could minimise a positive weighted cost (travel time plus a
documented pollution/rain penalty) and return alternatives. Neo4j's GDS
Dijkstra implementation requires a named graph and positive relationship
weights; Cypher `point.distance()` supplies geodesic distance for WGS84 points,
not a drivable route. Therefore this option also needs a routing/network source,
map matching, segment forecast interpolation, refresh/expiry policy, and a clear
fallback when route data is unavailable. Open-Meteo's documented grid-cell
forecasts (11 km CAMS Europe / 45 km CAMS global) cannot support street-level
exposure claims by themselves.

## Evidence table

| Claim | Primary source and supporting location | What it supports | Limitation | Classification |
|---|---|---|---|---|
| Open-Meteo exposes apparent temperature, UV, sunrise/sunset and daylight duration | [Open-Meteo Forecast API](https://open-meteo.com/en/docs), “Hourly Parameter Definition” (`apparent_temperature`, `uv_index`) and “Daily Parameter Definition” (`sunrise`, `sunset`, `daylight_duration`, `uv_index_max`) | Exact weather fields for ceilings and daylight/UV context | Apparent temperature is a perceived model value; UV is an index, not dose | Fact → feature proposal |
| Forecast time-zone behavior needs care | [Open-Meteo Forecast API](https://open-meteo.com/en/docs), `timezone`/`utc_offset_seconds` parameter notes | Keep IANA timezone and convert Unix timestamps for DST-aware display | Offset is fixed at request time; DST changes in the range are ignored in default ISO timestamps | Fact → implementation constraint |
| AQI and pollutant variables are available | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), “United States Air Quality Index” and “Hourly Parameter Definition” | Existing `us_aqi`/`pm2_5` plus optional PM10, ozone, NO2, SO2, CO fields | Forecast is modelled; overall US AQI uses pollutant-specific averaging windows and can exceed 500 | Fact |
| CAMS spatial resolution is coarse for street-level claims | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), “Data Sources” and response `latitude`/`longitude` notes | Preserve the product's model/grid limitation in route or threshold wording | 11 km CAMS European and 45 km CAMS global forecasts; returned coordinate is a grid-cell center | Fact → limitation |
| UVI thresholds can drive neutral safety copy | [WHO UV Index Q&A](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index), “What does the UV index mean?” | UVI 3+ prompts shade/protection wording; UVI 8+ prompts stronger midday advice | WHO guidance is public education, not personalised medical advice or a dose calculator | Fact → copy proposal |
| AQI categories provide explanatory labels | [US EPA AirNow AQI Basics](https://www.airnow.gov/aqi/aqi-basics/), “How does the AQI work?” and category table | Explain 0–50, 51–100, 101–150, etc. when a user ceiling is crossed | US AQI is an ambient communication index, not an individual's exposure estimate | Fact → copy proposal |
| Calendar export has a standard event model | [RFC 5545 iCalendar](https://www.rfc-editor.org/rfc/rfc5545), sections 3.6.1 and 3.8.2–3.8.5 (`VEVENT`, `DTSTART`, `DTEND`, `TZID`, `RRULE`) | Generate a standards-compliant `.ics` event and optional recurrence | A recurrence rule cannot predict future weather; re-evaluate each occurrence | Fact → feature proposal |
| Neo4j can compute weighted shortest paths | [Neo4j GDS Dijkstra source-target](https://neo4j.com/docs/graph-data-science/current/algorithms/dijkstra-source-target/), Introduction and configuration tables | Possible route-aware extension with positive edge costs | Requires a projected named graph, maintained edges and weights; no routing data is provided | Fact → deferred proposal |
| Neo4j point distance is geodesic/Euclidean, not road routing | [Neo4j Cypher spatial functions](https://neo4j.com/docs/cypher-manual/current/functions/spatial/), `point.distance()` | Useful straight-line sanity check for places | Cannot replace a road network or model segment-level exposure | Fact → limitation |

## Exact search and retrieval log

All retrievals were made from the public internet on **2026-10-31**, using
`urllib.request`/`curl` with a descriptive user agent; no credentials or private
project data were sent. HTTP status and local capture files are recorded below.

| UTC time | Source/database | Exact query or URL | Result |
|---|---|---|---|
| 08:29:50 | Open-Meteo Forecast API docs | `https://open-meteo.com/en/docs` | HTTP 200; opened hourly/daily variable definitions and timezone notes |
| 08:29:50 | Open-Meteo Air Quality API docs | `https://open-meteo.com/en/docs/air-quality-api` | HTTP 200; opened AQI definitions, CAMS resolution, limits, attribution |
| 08:29:50 | Open-Meteo terms | `https://open-meteo.com/en/terms` | HTTP 200; opened attribution/usage page |
| Time not individually recorded | Open-Meteo forecast endpoint | `https://api.open-meteo.com/v1/forecast?latitude=12.9716&longitude=77.5946&hourly=apparent_temperature,uv_index,visibility,wind_speed_10m,weather_code,precipitation_probability&daily=sunrise,sunset,daylight_duration,uv_index_max&timezone=auto&forecast_days=2` | HTTP 200; response contained requested hourly units/arrays and timezone metadata |
| Time not individually recorded | Open-Meteo air-quality endpoint | `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=12.9716&longitude=77.5946&hourly=us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide&timezone=auto&forecast_days=2` | HTTP 200; response contained requested pollutant arrays and `USAQI`/`μg/m³` units |
| Time not individually recorded | Open-Meteo geocoding endpoint | `https://geocoding-api.open-meteo.com/v1/search?name=HSR%20Layout&count=3&language=en&format=json` | HTTP 200 but no `results` array; this confirms a lookup may return no match, so the built-in Bengaluru locality map remains useful |
| 08:29:50 | Neo4j Graph Data Science docs | `https://neo4j.com/docs/graph-data-science/current/algorithms/dijkstra-source-target/` | HTTP 200; opened Dijkstra requirements, named-graph syntax and positive weighted relationships |
| 08:29:50 | Neo4j Cypher Manual | `https://neo4j.com/docs/cypher-manual/current/functions/spatial/` | HTTP 200; opened WGS84 geodesic behavior of `point.distance()` |
| 08:29:50 | IETF RFC Editor | `https://www.rfc-editor.org/rfc/rfc5545.txt` | HTTP 200; opened iCalendar component/property definitions and recurrence notes |
| 08:29:50 | US EPA AirNow | `https://www.airnow.gov/aqi/aqi-basics/` | HTTP 200; opened AQI categories and health-communication scope |
| 08:29:50 | WHO | `https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index` | HTTP 200; opened UVI meaning and public action bands |

Local text inspection used these exact searches after retrieval (to identify
supporting sections; they are not independent sources):

```sh
rg -in 'apparent_temperature|uv_index|sunrise|sunset|daylight' weather_docs.clean.txt
rg -in 'us_aqi|pm2_5|CAMS|resolution|grid-cell' air_docs.clean.txt
rg -in 'Dijkstra|shortest|positive relationship|point.distance|WGS 84' neo4j_*.clean.txt
rg -in 'VEVENT|DTSTART|DTEND|RRULE|TZID' icalendar.txt
rg -in 'AQI|health|category' airnow_aqi.clean.txt
rg -in 'UV index|shade|protection|3 and above|8 and above' who_uv.clean.txt
```
