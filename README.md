# Delhi Air Window

**AQI, PM2.5, rain and heat → a better time to go outside.** Finds the best available 1–2 hour window in the next 48 hours to run, cycle, walk, commute or take children outside in Delhi or another city.

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:domain/utility](https://img.shields.io/badge/utility-4CAF50)

Uses live, keyless Open-Meteo forecasts. All replies identify the location, timezone, data retrieval time and source. This is **modelled air quality, not CPCB station readings**. A best available window can still have unhealthy air; the agent says so. It does not provide medical advice.

Ported from [PDGamerSG/blr-air](https://github.com/PDGamerSG/blr-air), built for Stranger Builds Bangalore 2026. See the [Delhi verification record](docs/verification.md) for what has and has not been checked, and [docs/bengaluru-archive](docs/bengaluru-archive/) for the original project's evidence, which does not apply to this port.

## What is different in Delhi

Delhi's air and geography change how the results should be read:

- **Air is usually far worse than Bengaluru's.** Winter readings of US AQI 200–500 are normal, so "best available" often still means *unhealthy*. Replies say so, and a limit like `AQI at most 100` is refused rather than relaxed when no hour qualifies.
- **The model is coarse.** CAMS cells are about 45 km wide. On 4 November 2026 the 22 built-in localities produced only **3 distinct readings**. Comparisons say when places share a cell, and they carry a warning that local hotspots are invisible: Anand Vihar can rank as "best" even though it is a well-known pollution hotspot.
- **US AQI here is smoothed.** Open-Meteo's `us_aqi` barely moves through the day, while PM2.5 swung from 97 to 167 µg/m³ on the same day. The hourly ranking in Delhi is therefore driven mostly by the PM2.5 term, and it tends to favour early afternoon in smog season.
- **US AQI is not India's AQI.** Delhi residents usually see CPCB figures, which use a different scale and real monitors. Neither number here should be compared directly with those.
- **Names.** `New Delhi`, `NCR`, `Gurgaon`, `CP`, `Old Delhi` and `Sector 62, Noida` all resolve locally. Noida, Gurugram, Ghaziabad and Faridabad are labelled `Delhi NCR`, because they are not in Delhi. `Delhi, Ontario` still goes to the geocoder.

## Run it now

Python **3.12 or 3.13** is required. With [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run delhi-air 'best 1-hour window to run in Hauz Khas'
uv run delhi-air 'best 2-hour cycling window in Dwarka tomorrow morning'
uv run delhi-air --place 'Melbourne, Australia' --activity walk --json
```

Or use pip:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m delhi_air 'best window in Noida'
```

No keys are needed for these commands. `--demo` exercises the same recommendation service with **clearly labelled synthetic Delhi data**, without making network calls:

```sh
python -m delhi_air --demo --hours 2 --json
python -m delhi_air --latitude 28.5494 --longitude 77.2001 --hours 2
python -m delhi_air --place 'New York, US' --day tomorrow --period morning
```

## The agent decides for you

The agent doesn't have to be asked. Say "what should I do near Rohini", or let the watch check in by itself, and it picks the activity, the time and the place, and explains why. It downgrades hard exercise when the air is too bad and says to stay in when that's the honest answer. `POST /api/recommend` accepts a position plus preferred activities and usual hours, and stores none of them.

## Ask where and when

Say what you want to do and roughly where. The agent searches real places, checks each one's forecast and nearest monitor, and picks a place and a time:

```text
i want to go for a walk near rohini area
go for a bike ride near Dwarka tomorrow evening
where can i take my kids near Saket tomorrow morning
looking for a place to jog around Gurugram
```

It suits the place to the activity, for example a cycle track for a ride and a larger park for a run, and offers two alternatives. Places come from OpenStreetMap (`delhi_air/spots.json`, rebuilt by `scripts/build_spots.py`), and only Delhi NCR is covered. Live monitor readings need `WAQI_TOKEN` on the server. The ranking is a preference heuristic, and OpenStreetMap doesn't confirm opening hours, entry rules or whether cycling is allowed.

## Compare places, keep backups, and set your limits

Every recommendation now includes up to **two non-overlapping backup windows**. Compare two or three places to rank each at its own best eligible time; this does not compare them at one simultaneous hour. Tied scores are disclosed and preserve input order. If a place cannot be evaluated, the reply identifies the missing result.

```sh
uv run delhi-air 'compare Hauz Khas and Noida for a run tomorrow morning'
uv run delhi-air --compare 'Paris, France' --compare 'London, UK' --hours 2 --json
uv run delhi-air --place 'Hauz Khas' --day tomorrow --period morning \
  --max-aqi 100 --max-rain 30 --max-temperature 30 --max-uv 5 --max-wind 20 --daylight-only
```

Limits apply to **every hour**, not averages. `--max-temperature` means apparent/feels-like temperature in °C; wind is km/h, rain is percent, and AQI is US AQI. Missing values cannot pass a requested limit. If no slot qualifies, the agent explains this and never relaxes your limits automatically. These are user preferences, not medically validated safety thresholds.

Replies include apparent temperature, UV, wind and whether the whole block is between modelled sunrise and sunset. `--daylight-only` additionally requires that full interval. The usual 05:00–21:00 activity-hours restriction still applies. Optional weather context can be unavailable without making up values.

English chat can use `AQI at most 100`, `rain at most 30%`, `feels like at most 30C`, `UV at most 5`, `wind at most 20 km/h`, and `daylight only`. Explicit Fahrenheit, mph and m/s limits are converted to °C and km/h; CLI/API fields always use those canonical units. Repeated limits use the stricter bound. The local parser rejects numeric limit wording it cannot interpret. ASI:One supports more flexible language. CLI flags and the typed API provide exact control.

## Calendar and voice

The same planning service is also available through a server-side HTTP API for website clients. Run `uv run delhi-air-web` (port 8080), or use Docker Compose (web port 8082). It supports natural-language/structured planning, exact backup calendar downloads and Sarvam transcription/speech. See the [integration contract](docs/agent-http-api.md). API keys remain on the server; static frontend hosting alone does not run this API.

Replies now explain the worst-hour AQI category, weather concerns and the resolved location, with map links and a checklist. Named-park requests and requests for reviews can use Google Places for genuine customer ratings, review excerpts, opening hours and accessibility. Configure `GOOGLE_PLACES_API_KEY` with Places API (New) and billing. Missing or rejected access is explicitly reported; no ratings are generated or inferred from air quality. [Official-source venue research](docs/research/venue-data.md) and [outdoor guidance](docs/research/outdoor-assessment.md) explain the limits.

Save the selected window, or the winning place's window, to a new calendar file:

```sh
uv run delhi-air --place 'Hauz Khas' --activity run --calendar run.ics
```

Import the `.ics` into your calendar. It is one event with UTC timestamps, source/freshness notes and a reminder to recheck conditions. It does not book a venue, sync a calendar account or promise recurring future forecasts. Existing output files are never overwritten.

Optional voice uses **Sarvam** for speech and the same ASI:One/Open-Meteo planning service for the answer. Put `SARVAM_API_KEY` in your private `.env` once:

```sh
uv run delhi-air --audio-input request.wav --audio-output answer.wav --json
uv run delhi-air 'compare Hauz Khas and Dwarka for a run' --audio-output answer.wav
```

Input is a local 16-bit PCM WAV, mono/stereo, 8–48 kHz, up to 30 seconds and 10 MiB. Use `--audio-language hi-IN` or `pa-IN` if needed; default is automatic detection. Audio goes to Sarvam for transcription; the transcript goes to ASI:One when configured. Replies are spoken **in English** and saved as private WAV files. No microphone recording or remote audio URL downloading is performed. Voice is a CLI feature; the ASI:One agent interface continues to accept text. The text-only application uses ASI:One as its sole LLM; confirm the separate challenge's rules before submitting voice-enabled evidence.

Inputs support `run`, `cycle`, `walk`, `commute`, `kids`; duration `1` or `2`; day `next48`, `today`, `tomorrow`; period `any`, `morning`, `afternoon`, `evening`. Exact clock-time requests are rejected with guidance. CLI errors return nonzero exit codes. Use `--json` for structured results.

## Run the Agentverse mailbox agent

```sh
python -m delhi_air init
python -m delhi_air doctor
python agent.py
```

`init` creates a private, ignored `.env` with unique agent and caller seeds. It never overwrites an existing file. **Back up the seed; it determines your address.** Keep it unchanged when moving to an always-on host. `doctor` prints the public address without printing secrets.

1. Optionally set `ASI1_API_KEY` in `.env` for general conversation and freeform/multilingual parsing using **asi1-mini**. ASI:One is the only model integration. No key, invalid output, unavailable API or HTTP 402 preserves deterministic English planning and basic AQI explanations; general answers report the conversation service is unavailable.
2. Open the Inspector URL printed by `python agent.py`. Choose **Connect → Mailbox → Finish**. Allow local-network access if your browser asks. Confirm registration and **Active** status on Agentverse; local process health alone does not prove this.
3. Set profile name **Delhi Air Window**, claim `@blr-air` if available, upload an avatar, and publish [AGENT_README.md](AGENT_README.md). The handle is a profile setting; running the code does not claim it.
4. In ASI:One, enable **Agents** and use the profile's **Chat with Agent** link. Paste one of the prompts below. Save the actual share link from your account.

```text
@blr-air best 1-hour window to run in Hauz Khas
@blr-air best 2-hour cycling window in Dwarka
@blr-air when is the air cleanest in Noida
@blr-air can I take children outside in Melbourne tomorrow morning
```

**Published agent.** This code extends the agent already live as `@blr-air` (`agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3`). The website links to that agent. It answers with the code deployed on its host, so the Delhi changes reach ASI:One only after this code is deployed there with the original `AGENT_SEED_PHRASE`. Keep that seed and handle: a new identity would start from zero users, and the event rules don't count forks as new projects.

Ask naturally: the examples are optional. General questions receive direct answers through ASI:One. Current AQI/weather questions fetch model forecasts without selecting an activity window; outdoor plans retain the structured recommendation and calendar links. Send `@blr-air help` for examples and `@blr-air updates` for refresh/reminder guidance. Planning replies include a complete request to resend for an update. Use the reply's Google Calendar link, set a notification one hour before, then save; website/CLI `.ics` downloads include that reminder. Requests are independent and forecasts can be cached for five minutes; automatic chat alerts are not scheduled. See the [user guide](AGENT_README.md#read-your-answer-and-get-an-update).


## Agents and typed API

| Agent | Purpose | Address |
| --- | --- | --- |
| `delhi-air` | Chat Protocol and typed forecast requests | `agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3` |
| `day-planner-demo` | Hires Delhi Air using the shared wire models | `agent1qtehmnqextcf6czcujeq3yfh5umr2qtz4cxyxknve5tlcxgdkmpdgp4x53p` |

These are the published identities. Their seeds stay with the team that deployed them; `python -m delhi_air init` creates a separate identity for local testing only. A ready-to-upload avatar is in [assets/avatar.png](assets/avatar.png).

Protocol: **`delhi-air-window` v0.1.0**. Import `WindowRequest` and `WindowResponse` from `delhi_air.models` (or the root `models.py` compatibility module).

```python
request = WindowRequest(latitude=28.5494, longitude=77.2001, hours=2,
                        activity="run", day="tomorrow", period="morning")
await ctx.send(DELHI_AIR_ADDRESS, request)
```

Success returns `status="ok"`, offset-aware `start`/`end`, `timezone`, mean `us_aqi`/`pm2_5`, peak `rain_probability`/`temperature`, `max_aqi`, `fetched_at`, `source`, and a readable `summary`. Always check status first. A valid request that cannot be fulfilled returns `status="error"`, `error_code`, and `summary`; measurements remain null. Invalid coordinates or durations are rejected by the wire schema.

The existing wire schemas are unchanged. The new **`delhi-air-plan` v0.1.0** protocol accepts `PlanRequest` for one to three place names, supports all user limits and daylight, and returns numeric best/backup windows:

```python
from delhi_air.models import PlanRequest, PlanResponse

await ctx.send(DELHI_AIR_ADDRESS, PlanRequest(
    places=["Hauz Khas", "Noida"], hours=2, activity="run",
    day="tomorrow", period="morning", max_aqi=100, max_rain=30,
    daylight_only=True,
))
```

`PlanResponse` includes `winner`, `tied_places`, `partial`, and `results`. Each successful result has `resolved_name`, `timezone`, `window`, `backups`, `source`, and `fetched_at`. Every window includes all numeric metrics and category; failed places contain an explanation. Check `status` and `partial` before using the winner. A targeted transport compatibility fix rejects malformed Pydantic-v1 wire messages without killing uAgents 0.26.1's processing loop.

Set `DELHI_AIR_ADDRESS` in `.env`, then `python caller.py`. Connect its own Inspector/mailbox too. The caller sends once after 30 seconds; after first-time registration restart it if needed to demonstrate the response.

For a fully local signed agent-message exchange, start `python agent.py --local`, copy the address from `doctor`, and run:

```sh
python caller.py --address YOUR_AGENT_ADDRESS --endpoint http://127.0.0.1:8001/submit
curl -fsS http://127.0.0.1:8001/healthz
```

Local mode does not publish or register the agent. The caller uses its own cryptographic identity. This exercises real uAgents message envelopes, schema validation and the same live forecast service used by the mailbox.

## How the recommendation is chosen

Fetch four calendar days to cover the next **48 elapsed hours**, even late in the day. Join hourly air and weather data by UTC timestamp, then select complete consecutive blocks. Missing rain, temperature, AQI or PM2.5 excludes that hour; it is never assumed to be zero. Past hours and windows ending outside the horizon are excluded.

Only **05:00–21:00 local** windows are eligible. This is an activity-hours preference, **not a sunrise/sunset calculation**. Morning is 05:00–12:00, afternoon 12:00–17:00, evening 17:00–21:00. A request with no eligible window returns an explanation, never a nighttime fallback. Dates and DST use the provider's IANA timezone.

Lower mean hourly score wins, then earlier time breaks ties:

```text
US AQI + 0.5 × PM2.5 + 1.5 × rain probability + 5 × max(0, temperature °C − 30)
```

This is a documented **preference heuristic**, not a validated medical/exposure formula. AQI already includes particulate pollution; the PM2.5 term deliberately adds weight to particulates. Activity changes the wording, not an invented medical risk score. The reported rain chance is the **maximum hourly chance**, not the probability of rain over the entire block. Risk language uses the worst hourly AQI rather than averaging away a bad hour.

Twenty-two Delhi NCR locality centroids are built in, including Hauz Khas, Dwarka, Noida, Lajpat Nagar, Okhla, Saket, Mayur Vihar, Rohini and Lodhi Garden. Other names use Open-Meteo geocoding. Use `city, country` or coordinates to disambiguate; the resolved administrative area and country are shown. Model grid resolution does not provide street-level precision.

## Reliability, privacy and deployment

HTTP requests have six-second timeouts, at most three attempts for transient failures, a 23-second forecast budget, and a five-minute bounded forecast cache. There is no stale-data fallback. The timestamp on current model values is distinct from forecast retrieval time. Chat sends an acknowledgement, a text answer and `EndSessionContent`; acknowledgements are never answered.

Usage counters persist in `data/usage.sqlite`. Sender identifiers are keyed SHA-256 hashes; prompts and raw addresses are not saved by application telemetry. Unique senders are **not verified unique people**. The Inspector keeps recent envelopes in process memory for debugging; application message history is not persisted. Agentverse and ASI:One have their own data policies. `python -m delhi_air stats` reports aggregate queries and outcomes.

See [deployment instructions](docs/deployment.md) for Docker, persistent identity and an always-on service. `/healthz` reports process liveness, not external service availability or Agentverse registration. The initial mailbox agent runs from this directory; production keeps all state in a dedicated volume.

## Verify

```sh
uv run pytest -q
uv run ruff check delhi_air tests scripts agent.py caller.py models.py
uv run ruff format --check delhi_air tests scripts agent.py caller.py models.py
uv run delhi-air --demo --json
uv run python scripts/check_live.py --run-live
```

Tests cover window boundaries, comparisons/backups, hard limits, sunlight, missing values, retries, timezone/DST behaviour, parsing, schema validation, malformed-wire recovery, chat/error semantics, calendar, voice validation, telemetry persistence and CLI execution. The explicit live harness uses your configured ASI key, Open-Meteo, the running Docker service, and disposable local agents for signed chat callbacks; it makes real API calls and counts as developer traffic. See the [verification record](docs/verification.md).

Feature choices and limits are supported by [official-source research](docs/research/feature-opportunities.md) and [voice API research](docs/research/voice-options.md). Neo4j is deferred: route planning could use a road graph later, but coarse CAMS data cannot justify street-level pollution claims and a graph adds no value to this hourly-window calculation.

## Hackathon evidence

The [submission kit](docs/submission.md) lists evaluation prompts for Delhi. The [feedback log](docs/feedback.md) starts empty: there are no invented tester notes, users, videos, endorsements or challenge-completion claims.

## Landing page

**Website:** not deployed yet. `delhiairwindow.vercel.app` below is the intended project name, not a live URL.

`site/` contains a static, scroll-driven landing page (Three.js, GSAP, Blender-made models). It includes an in-browser scanner that applies the same scoring rules to live Open-Meteo data, and links to ASI:One and Agentverse. See [site/README.md](site/README.md).

```sh
cd site && npm install && npm run dev
```

The website and the agent deploy independently. Vercel builds only `site/` and serves `site/dist`, as configured in [vercel.json](vercel.json) and [.vercelignore](.vercelignore). It skips rebuilds when a commit doesn't touch `site/`. The agent's Docker image, wheel and CI never include `site/`.

To deploy on Vercel, import this repository and name the project **delhiairwindow** so the URL is `delhiairwindow.vercel.app`. Leave Root Directory as the repository root, because the `/api` proxy lives in root `api/`.

The on-page planner calls same-origin `/api/*`. Vercel rewrites those requests to [api/proxy.mjs](api/proxy.mjs), which forwards them to the Python web service (`delhi-air-web`, `Dockerfile.web`) running on an always-on HTTPS host:

1. On Vercel, set `DELHI_AIR_API_ORIGIN` to the backend origin, e.g. `https://api.example.com`, then redeploy.
2. On the backend, set `PUBLIC_ORIGIN=https://delhiairwindow.vercel.app` exactly. The proxy forwards the browser's `Origin` header, and any other value gets a 403.

Until `DELHI_AIR_API_ORIGIN` is set, `/api` returns a JSON 503. The planner then shows itself as unavailable, the hero and prompt cards fall back to ASI:One, and the keyless quick scanner and live map keep working. Behind the proxy, the backend's per-client rate limit applies to Vercel's egress addresses. Uploads through Vercel are capped at 4.5 MB.

## Smartwatch app

[watch/](watch/) is a standalone Wear OS app with the same planning logic, real station readings, a tile and a watch-face complication. It needs no phone app or hosted backend. See [watch/README.md](watch/README.md).

## Credits and licence

Code: MIT; see [LICENSE](LICENSE). Weather/geocoding: [Open-Meteo](https://open-meteo.com/). Air-quality forecasts: [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), based on [CAMS](https://atmosphere.copernicus.eu/). Follow the [Open-Meteo attribution and API terms](https://open-meteo.com/en/terms); the free endpoint is intended for noncommercial use. Language parsing: [ASI:One](https://asi1.ai/), optional. Agent transport: [Fetch.ai uAgents](https://github.com/fetchai/uAgents).
