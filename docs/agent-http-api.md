# Agent API for website integration

The Python service exposes the same recommendation logic as CLI and uAgents chat. Start `uv run blr-air-web --port 8080` locally, or `docker compose up -d --build`. Compose exposes the web API at `http://127.0.0.1:8082` and the signed agent at port 8001; `WEB_PORT` changes the former. The agent's seed/address remains unchanged.

## Contract

- `GET /api/status`: configuration flags for language, voice, venues, calendar and comparisons. These flags show configured credentials, not successful provider authentication.
- `POST /api/plan` with JSON `{"query":"compare HSR Layout and Whitefield tomorrow morning with AQI at most 100"}`. Alternatively supply `{"request":{"place":"HSR Layout","hours":1,"max_aqi":100}}`. Supply exactly one of `query` or `request`. All `RequestSpec` constraints work in the structured form.
- `include_venue: true` asks for genuine venue lookup. Named parks, customer reviews, ratings, opening hours and accessibility requests also trigger lookup automatically. Optional `venue_query` supplies a precise venue name/city for a single-place plan; this replaces the forecast location with the matched venue's coordinates. Compare venues by naming each in the query.
- Successful JSON contains `plan_id`, `expires_at`, numeric `window`/`backups`, `assessment`, `venue` and `summary`. Comparisons return `places`, `tied_places` and `partial`. Each numeric window has its own assessment, including backups. Unavailable venues do not suppress a forecast when the location can otherwise be resolved.
- `GET /api/calendar/{plan_id}?place_index=0&window_index=1` downloads the first backup of the first result. Index zero selects the best window. Comparison indexes follow returned order, including unavailable entries; selecting an unavailable place returns an error.
- `POST /api/speech` with JSON `{"plan_id":"...","place_index":0,"window_index":1}` returns `audio/wav` for the exact selected forecast. It cannot synthesize arbitrary caller-provided text.
- `POST /api/transcribe` with raw PCM16 WAV and `Content-Type: audio/wav` returns `{"transcript":"..."}`. Audio must be complete, 8–48 kHz mono/stereo, at most 30 seconds and 10 MiB. Speech output is English. Website microphone capture is the client's responsibility; browser permission is required.

Errors are JSON `{"status":"error","error":"..."}`: 400 invalid JSON/schema, 403 foreign origin, 410 expired/started selection, 413 oversized body, 415 unsupported media, 422 unsupported request/no qualifying window, 429 rate limit or paid venue-search budget, 502 forecast-provider failure, 503 busy/missing voice configuration, 504 timeout. All-place comparison failures may return structured error results and `summary`. No requested hard limit is automatically relaxed. Venue lookups have a separate server-side budget because Google Places SearchText is billable; a 429 does not mean the forecast request itself failed.

## Credentials and deployment

`ASI1_API_KEY` enables freeform/multilingual extraction. `SARVAM_API_KEY` enables audio. `GOOGLE_PLACES_API_KEY` must be a valid Google Cloud key with Places API (New) and billing enabled for genuine customer reviews, ratings, opening hours and accessibility. Requesting reviews uses a higher-priced Google SKU. Restrict this key to the server API; never bundle it in Vite or return it to users. Open-Meteo needs no key for the current noncommercial endpoint.

The stored Google credential has not produced a usable venue response in the live check (an earlier value returned HTTP 400 `API_KEY_INVALID`; the latest supplied value timed out); the integration reports this and leaves reviews unavailable. ASI and Sarvam passed real calls. Claude is not required and its stored credential previously failed authentication. No Neo4j dependency is needed for hourly planning.

For a separate static Vercel frontend, route `/api/*` through a same-origin rewrite to an always-on HTTPS Python backend. Set `PUBLIC_ORIGIN` on that backend to the exact website origin. Do not point a production frontend at a user's localhost. The API currently uses one process and ephemeral in-memory selections: deploy one replica or use sticky routing; restarts expire selections. Static-only deployment cannot run Python requests or keep server secrets. Frontend hosting is managed in the separate website thread.

The service uses a bounded 128-plan store, fifteen-minute expiry, four concurrent operations, 30 POST requests per client per minute and a global 120/minute ceiling. Behind a proxy it conservatively counts the proxy as the client; it does not trust arbitrary forwarded-IP headers. API responses are `no-store`. Forecast snapshots retain no review content. Audio uses temporary private directories and is removed after each request; prompts/reviews are not persisted by this service. Request access logging is disabled. Hosting/provider logging policies remain separate.

Display Google Maps attribution beside venue results and each supplied reviewer's name/profile/photo/date. Treat review text as untrusted text. Show the exact matched venue/address and the possibility of multiple search matches. Stars do not score outdoor safety. Current opening status does not prove that a venue is open during the forecast window.

## Checks

`uv run pytest -q` exercises shared service, validation, venue failures, voice boundaries and HTTP requests. `uv run python scripts/check_live.py --run-live` checks signed chat/typed requests, real ASI and Open-Meteo. `uv run python scripts/check_web_live.py --run-live --url http://127.0.0.1:8082` checks actual HTTP forecasts, precise backup calendar export, voice roundtrip and reports Google access separately. See `docs/web-live-checks.json` for the latest result. Developer traffic is not outside-user evidence.
