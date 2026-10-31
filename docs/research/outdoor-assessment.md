# Outdoor and location assessment

Research date: **2026-10-31**. This is a bounded review of official public
guidance, used to improve the explanation of an existing forecast. It is not a
clinical evaluation, a new exposure model, or a comprehensive literature review.

## Implemented behavior

`blr_air.assessment.assess(recommendation)` returns a verdict, AQI meaning and
advice, a resolved location, warnings, selection reasons, and a practical
checklist. Its output is JSON-safe and does not make network requests. It can be
used by the shared Python service, chat and website without a second scoring
implementation.

The AQI `index` is the window average; `worst_hourly` determines `category`,
`meaning` and `advice`. A low average cannot conceal a worse hour. Good or moderate
AQI never produces a promise of safety, especially when weather context is
missing. Hazardous air never receives a suggestion that merely shortening the
outing resolves the risk. Children receive sensitive-group context when relevant.

The location assessment identifies the resolved name, coordinates, timezone and
a coordinate map link. It explains regional model resolution and requires a
local check of access/opening hours. It does not manufacture ratings or infer
park quality from air quality. Real venue reviews belong to the separately
attributed venue-data response.

Weather warnings distinguish ambient from apparent temperature, surface
freezing checks, rain chance, sun protection and missing data. Cycling advice
reports forecast wind and asks for a local gust/exposure check without inventing
a universal safe wind speed. No new numerical wind cutoff was added. The existing
application's 35°C heat and 70% rain cautions remain product heuristics, not
medical thresholds or warnings issued by a meteorological agency. The UV 3 and
8 action bands are grounded in WHO public guidance. A zero-degree freezing
check does not assert that ice has been observed.

## Evidence and limits

| Claim | Primary source and inspected passage | Implementation | Limit |
| --- | --- | --- | --- |
| Six AQI bands communicate rising concern | [AirNow AQI Basics](https://www.airnow.gov/aqi/aqi-basics/), category table and “How does the AQI work?” | Use the existing `aqi_category` bands and worst hourly AQI for health wording | This uses US AQI from a model, not Indian AQI or CPCB observations |
| Advice should vary by category and sensitivity | [EPA Air Quality Guide for Particle Pollution](https://document.airnow.gov/air-quality-guide-for-particle-pollution.pdf), EPA-452/F-23-002, February 2023, page 1 activity table | Shorter/less intense activity at lower adverse bands; avoid outdoor physical activity at hazardous levels; mention children as a sensitive group | Public guidance is not personal medical advice; model overall AQI may be driven by pollutants other than particles |
| Indoor air can also have particles | Same EPA guide, page 2 “How can I protect myself?” | Say “indoor alternative with cleaner air,” not that any indoor space is safe | No indoor air measurement is available |
| UV 3–7 calls for protection; 8+ requires stronger midday precautions | [WHO UV Index Q&A](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index), “What does the UV index mean?” | Shade, clothing, hat and sunscreen; avoid midday exposure at 8+ | No personalized burn-time or dose estimate |
| Apparent temperature incorporates wind chill, humidity and radiation | [Open-Meteo Forecast docs](https://open-meteo.com/en/docs), Hourly Parameter Definition, `apparent_temperature` | Distinguish feels-like heat from air temperature; disclose absent apparent temperature | No heat-index diagnosis or official heat warning |
| Air-quality model grids are much coarser than streets | [Open-Meteo Air Quality docs](https://open-meteo.com/en/docs/air-quality-api), Data Sources | Warn that nearby places may share forecasts and coordinates are not monitoring stations | CAMS Europe ~11 km and global composition ~45 km; no street/route exposure ranking |
| Current and forecast AQI have different meanings | [AirNow Using the AQI](https://www.airnow.gov/aqi/aqi-basics/using-air-quality-index/), forecast/NowCast descriptions | Keep the selected forecast assessment distinct from current conditions | Open-Meteo output is not an AirNow NowCast |

## Retrieval log

All requests used public `urllib.request` with user agent
`BLR-Air-doc-review/1.0`, a 20–30 second timeout, and no credentials. HTML was
inspected after tag removal and whitespace normalization. Exact search terms
were `sensitive`, `unhealthy`, `Moderate`, `outdoor`, `3 and above`, `8 and above`,
`45 km`, `11 km`, `apparent temperature`, `wind chill`, `shorter`,
`less strenuous`, `reduce`, `prolonged`, `indoor`, `avoid`, and `children`.

| UTC time | Exact URL | Result |
| --- | --- | --- |
| 09:36:14–09:36:15 | `https://www.airnow.gov/aqi/aqi-basics/` | HTTP 200; AQI category table |
| 09:36:15 | `https://www.airnow.gov/air-quality-and-health/` | HTTP 200; health context and links to activity guides |
| 09:36:14 | `https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index` | HTTP 200; action-band table |
| 09:36:14 | `https://open-meteo.com/en/docs/air-quality-api` | HTTP 200; model resolution and US AQI definition |
| 09:36:15 | `https://open-meteo.com/en/docs` | HTTP 200; apparent-temperature definition |
| Time not individually recorded | `https://www.airnow.gov/aqi/aqi-basics/using-air-quality-index/` | HTTP 200; forecast/current distinctions |
| 09:40:51 | `https://www.airnow.gov/all-activity-guides/` | HTTP 200; followed publication links |
| 09:41:20 | `https://www.airnow.gov/publications/activity-guides/air-quality-activity-guide-for-particle-pollution/` | HTTP 200; linked English PDF |
| 09:41:34 | `https://document.airnow.gov/air-quality-guide-for-particle-pollution.pdf` | HTTP 200; read both pages with `pypdf` in a temporary `uv run --with pypdf` environment; no project dependency added |

Guessed AirNow paths `/education/air-quality-and-outdoor-activity-guidance-for-schools/`,
`/aqi/aqi-basics/activity-guides/`, and
`/air-quality-and-health/how-smoke-from-fires-can-affect-your-health/` returned
HTTP 404. The published activity-guide links above resolved the relevant source;
the failed URLs were not evidence that guidance was unavailable.

## Further features worth considering

- **Explicit user preferences:** expose the existing every-hour limits directly
  in the website and explain each applied limit. Do not derive personal medical
  thresholds from age or a diagnosis.
- **Recheck action:** repeat the original request before departure and keep a
  timestamp on calendar snapshots. This is useful because conditions change;
  a static calendar event is not a live forecast.
- **Location confirmation:** put the resolved name/address and map link beside
  the result. Candidate ambiguity must be visible before a venue rating is
  treated as relevant to the user's intended place.
- **Wind gusts as a later weather field:** cyclists benefit from gust context;
  the current hourly wind-speed field alone cannot establish peak gusts. Until
  such data is fetched and validated, disclose its absence.

No additional API key is required for these deterministic forecast assessments.
