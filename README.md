# BLR Air Window

**AQI, PM2.5, rain and heat → a better time to go outside.** Finds the best available 1–2 hour window in the next 48 hours to run, cycle, walk, commute or take children outside in Bengaluru or another city.

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:domain/utility](https://img.shields.io/badge/utility-4CAF50)

Uses live, keyless Open-Meteo forecasts. All replies identify the location, timezone, data retrieval time and source. This is **modelled air quality, not CPCB station readings**. A best available window can still have unhealthy air; the agent says so. It does not provide medical advice.

Public repository: [PDGamerSG/blr-air](https://github.com/PDGamerSG/blr-air). See the [verification record](docs/verification.md) for completed checks and external steps still to verify.

## Run it now

Python **3.12 or 3.13** is required. With [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run blr-air 'best 1-hour window to run in HSR Layout'
uv run blr-air 'best 2-hour cycling window in Koramangala tomorrow morning'
uv run blr-air --place 'Melbourne, Australia' --activity walk --json
```

Or use pip:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m blr_air 'best window in Whitefield'
```

No keys are needed for these commands. `--demo` exercises the same recommendation service with **clearly labelled synthetic Bengaluru data**, without making network calls:

```sh
python -m blr_air --demo --hours 2 --json
python -m blr_air --latitude 12.9116 --longitude 77.6389 --hours 2
python -m blr_air --place 'New York, US' --day tomorrow --period morning
```

## Compare places, keep backups, and set your limits

Every recommendation now includes up to **two non-overlapping backup windows**. Compare two or three places to rank each at its own best eligible time; this does not compare them at one simultaneous hour. Tied scores are disclosed and preserve input order. If a place cannot be evaluated, the reply identifies the missing result.

```sh
uv run blr-air 'compare HSR Layout and Whitefield for a run tomorrow morning'
uv run blr-air --compare 'Paris, France' --compare 'London, UK' --hours 2 --json
uv run blr-air --place 'HSR Layout' --day tomorrow --period morning \
  --max-aqi 100 --max-rain 30 --max-temperature 30 --max-uv 5 --max-wind 20 --daylight-only
```

Limits apply to **every hour**, not averages. `--max-temperature` means apparent/feels-like temperature in °C; wind is km/h, rain is percent, and AQI is US AQI. Missing values cannot pass a requested limit. If no slot qualifies, the agent explains this and never relaxes your limits automatically. These are user preferences, not medically validated safety thresholds.

Replies include apparent temperature, UV, wind and whether the whole block is between modelled sunrise and sunset. `--daylight-only` additionally requires that full interval. The usual 05:00–21:00 activity-hours restriction still applies. Optional weather context can be unavailable without making up values.

English chat can use `AQI at most 100`, `rain at most 30%`, `feels like at most 30C`, `UV at most 5`, `wind at most 20 km/h`, and `daylight only`. Explicit Fahrenheit, mph and m/s limits are converted to °C and km/h; CLI/API fields always use those canonical units. Repeated limits use the stricter bound. The local parser rejects numeric limit wording it cannot interpret. ASI:One supports more flexible language. CLI flags and the typed API provide exact control.

## Calendar and voice

Save the selected window, or the winning place's window, to a new calendar file:

```sh
uv run blr-air --place 'HSR Layout' --activity run --calendar run.ics
```

Import the `.ics` into your calendar. It is one event with UTC timestamps, source/freshness notes and a reminder to recheck conditions. It does not book a venue, sync a calendar account or promise recurring future forecasts. Existing output files are never overwritten.

Optional voice uses **Sarvam** for speech and the same ASI:One/Open-Meteo planning service for the answer. Put `SARVAM_API_KEY` in your private `.env` once:

```sh
uv run blr-air --audio-input request.wav --audio-output answer.wav --json
uv run blr-air 'compare HSR Layout and Koramangala for a run' --audio-output answer.wav
```

Input is a local 16-bit PCM WAV, mono/stereo, 8–48 kHz, up to 30 seconds and 10 MiB. Use `--audio-language hi-IN` or `kn-IN` if needed; default is automatic detection. Audio goes to Sarvam for transcription; the transcript goes to ASI:One when configured. Replies are spoken **in English** and saved as private WAV files. No microphone recording or remote audio URL downloading is performed. Voice is a CLI feature; the ASI:One agent interface continues to accept text. The text-only application uses ASI:One as its sole LLM; confirm the separate challenge's rules before submitting voice-enabled evidence.

Inputs support `run`, `cycle`, `walk`, `commute`, `kids`; duration `1` or `2`; day `next48`, `today`, `tomorrow`; period `any`, `morning`, `afternoon`, `evening`. Exact clock-time requests are rejected with guidance. CLI errors return nonzero exit codes. Use `--json` for structured results.

## Run the Agentverse mailbox agent

```sh
python -m blr_air init
python -m blr_air doctor
python agent.py
```

`init` creates a private, ignored `.env` with unique agent and caller seeds. It never overwrites an existing file. **Back up the seed; it determines your address.** Keep it unchanged when moving to an always-on host. `doctor` prints the public address without printing secrets.

1. Optionally set `ASI1_API_KEY` in `.env` for freeform/multilingual parsing using **asi1-mini**. ASI:One is the only model integration. No key, invalid output, unavailable API or HTTP 402 uses the deterministic English parser.
2. Open the Inspector URL printed by `python agent.py`. Choose **Connect → Mailbox → Finish**. Allow local-network access if your browser asks. Confirm registration and **Active** status on Agentverse; local process health alone does not prove this.
3. Set profile name **BLR Air Window**, claim `@blr-air` if available, upload an avatar, and publish [AGENT_README.md](AGENT_README.md). The handle is a profile setting; running the code does not claim it.
4. In ASI:One, enable **Agents** and use the profile's **Chat with Agent** link. Paste one of the prompts below. Save the actual share link from your account.

```text
@blr-air best 1-hour window to run in HSR Layout
@blr-air best 2-hour cycling window in Koramangala
@blr-air when is the air cleanest in Whitefield
@blr-air can I take children outside in Melbourne tomorrow morning
```

The profile link, ASI:One share link and Active status must be verified after registration. They are not inferred from a local run.

## Agents and typed API

| Agent | Purpose | Address |
| --- | --- | --- |
| `blr-air` | Chat Protocol and typed forecast requests | `agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3` |
| `day-planner-demo` | Hires BLR Air using the shared wire models | `agent1qtehmnqextcf6czcujeq3yfh5umr2qtz4cxyxknve5tlcxgdkmpdgp4x53p` |

These are the identities generated for this build; Agentverse account connection and ASI:One routing still need verification. A fresh clone's `init` creates its own identities. The original seeds stay private. A ready-to-upload avatar is in [assets/avatar.png](assets/avatar.png).

Protocol: **`blr-air-window` v0.1.0**. Import `WindowRequest` and `WindowResponse` from `blr_air.models` (or the root `models.py` compatibility module).

```python
request = WindowRequest(latitude=12.9116, longitude=77.6389, hours=2,
                        activity="run", day="tomorrow", period="morning")
await ctx.send(BLR_AIR_ADDRESS, request)
```

Success returns `status="ok"`, offset-aware `start`/`end`, `timezone`, mean `us_aqi`/`pm2_5`, peak `rain_probability`/`temperature`, `max_aqi`, `fetched_at`, `source`, and a readable `summary`. Always check status first. A valid request that cannot be fulfilled returns `status="error"`, `error_code`, and `summary`; measurements remain null. Invalid coordinates or durations are rejected by the wire schema.

The existing wire schemas are unchanged. The new **`blr-air-plan` v0.1.0** protocol accepts `PlanRequest` for one to three place names, supports all user limits and daylight, and returns numeric best/backup windows:

```python
from blr_air.models import PlanRequest, PlanResponse

await ctx.send(BLR_AIR_ADDRESS, PlanRequest(
    places=["HSR Layout", "Whitefield"], hours=2, activity="run",
    day="tomorrow", period="morning", max_aqi=100, max_rain=30,
    daylight_only=True,
))
```

`PlanResponse` includes `winner`, `tied_places`, `partial`, and `results`. Each successful result has `resolved_name`, `timezone`, `window`, `backups`, `source`, and `fetched_at`. Every window includes all numeric metrics and category; failed places contain an explanation. Check `status` and `partial` before using the winner. A targeted transport compatibility fix rejects malformed Pydantic-v1 wire messages without killing uAgents 0.26.1's processing loop.

Set `BLR_AIR_ADDRESS` in `.env`, then `python caller.py`. Connect its own Inspector/mailbox too. The caller sends once after 30 seconds; after first-time registration restart it if needed to demonstrate the response.

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

Twenty Bengaluru locality centroids are built in, including HSR Layout, Koramangala, Whitefield, Indiranagar, Electronic City, Jayanagar, Bellandur, Hebbal and Cubbon Park. Other names use Open-Meteo geocoding. Use `city, country` or coordinates to disambiguate; the resolved administrative area and country are shown. Model grid resolution does not provide street-level precision.

## Reliability, privacy and deployment

HTTP requests have six-second timeouts, at most three attempts for transient failures, a 23-second forecast budget, and a five-minute bounded forecast cache. There is no stale-data fallback. The timestamp on current model values is distinct from forecast retrieval time. Chat sends an acknowledgement, a text answer and `EndSessionContent`; acknowledgements are never answered.

Usage counters persist in `data/usage.sqlite`. Sender identifiers are keyed SHA-256 hashes; prompts and raw addresses are not saved by application telemetry. Unique senders are **not verified unique people**. The Inspector keeps recent envelopes in process memory for debugging; application message history is not persisted. Agentverse and ASI:One have their own data policies. `python -m blr_air stats` reports aggregate queries and outcomes.

See [deployment instructions](docs/deployment.md) for Docker, persistent identity and an always-on service. `/healthz` reports process liveness, not external service availability or Agentverse registration. The initial mailbox agent runs from this directory; production keeps all state in a dedicated volume.

## Verify

```sh
uv run pytest -q
uv run ruff check blr_air tests scripts agent.py caller.py models.py
uv run ruff format --check blr_air tests scripts agent.py caller.py models.py
uv run blr-air --demo --json
uv run python scripts/check_live.py --run-live
```

Tests cover window boundaries, comparisons/backups, hard limits, sunlight, missing values, retries, timezone/DST behaviour, parsing, schema validation, malformed-wire recovery, chat/error semantics, calendar, voice validation, telemetry persistence and CLI execution. The explicit live harness uses your configured ASI key, Open-Meteo, the running Docker service, and disposable local agents for signed chat callbacks; it makes real API calls and counts as developer traffic. See [verification record](docs/verification.md) and [machine-readable live evidence](docs/live-checks.json).

Feature choices and limits are supported by [official-source research](docs/research/feature-opportunities.md) and [voice API research](docs/research/voice-options.md). Neo4j is deferred: route planning could use a road graph later, but coarse CAMS data cannot justify street-level pollution claims and a graph adds no value to this hourly-window calculation.

## Hackathon evidence

The [submission kit](docs/submission.md) includes ten evaluation prompts, a routing experiment, outside-test notes, deployment checks and demo scripts. [Feedback log](docs/feedback.md) starts empty: there are no invented tester notes, users, videos, endorsements or challenge-completion claims. Record actual usage counts after deployment; local development messages are not outside-user tries.

## Landing page

**Website:** [blrairwindow.vercel.app](https://blrairwindow.vercel.app)

`site/` contains a static, scroll-driven landing page (Three.js, GSAP, Blender-made models). It includes an in-browser scanner that applies the same scoring rules to live Open-Meteo data, and links to ASI:One and Agentverse. See [site/README.md](site/README.md).

```sh
cd site && npm install && npm run dev
```

The website and the agent deploy independently. Vercel builds only `site/` and serves `site/dist`, as configured in [vercel.json](vercel.json) and [.vercelignore](.vercelignore). It skips rebuilds when a commit doesn't touch `site/`. The agent's Docker image, wheel and CI never include `site/`.

To deploy on Vercel, import this repository and name the project **blrairwindow** so the URL is `blrairwindow.vercel.app`. Leave Root Directory as the repository root, because the `/api` proxy lives in root `api/`.

The on-page planner calls same-origin `/api/*`. Vercel rewrites those requests to [api/proxy.mjs](api/proxy.mjs), which forwards them to the Python web service (`blr-air-web`, `Dockerfile.web`) running on an always-on HTTPS host:

1. On Vercel, set `BLR_AIR_API_ORIGIN` to the backend origin, e.g. `https://api.example.com`, then redeploy.
2. On the backend, set `PUBLIC_ORIGIN=https://blrairwindow.vercel.app` exactly. The proxy forwards the browser's `Origin` header, and any other value gets a 403.

Until `BLR_AIR_API_ORIGIN` is set, `/api` returns a JSON 503. The planner then shows itself as unavailable, the hero and prompt cards fall back to ASI:One, and the keyless quick scanner and live map keep working. Behind the proxy, the backend's per-client rate limit applies to Vercel's egress addresses. Uploads through Vercel are capped at 4.5 MB.

## Credits and licence

Code: MIT; see [LICENSE](LICENSE). Weather/geocoding: [Open-Meteo](https://open-meteo.com/). Air-quality forecasts: [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), based on [CAMS](https://atmosphere.copernicus.eu/). Follow the [Open-Meteo attribution and API terms](https://open-meteo.com/en/terms); the free endpoint is intended for noncommercial use. Language parsing: [ASI:One](https://asi1.ai/), optional. Agent transport: [Fetch.ai uAgents](https://github.com/fetchai/uAgents).
