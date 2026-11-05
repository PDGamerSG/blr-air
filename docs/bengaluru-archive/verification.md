# Verification record

## Request-specific answers

The routing fix passes **275 Python tests**, Ruff lint/format, **8 website tests** and the production website build. Both Docker services were rebuilt and restarted. Six consecutive requests from one caller through the installed Docker agent handler, using real ASI and Open-Meteo, returned relevant answers: a two-sentence photosynthesis explanation, a one-sentence notification explanation, a sample sentence containing “send me alerts”, multiplication, exactly three walking-benefit bullets, and current HSR Layout AQI with source and retrieval time.

Previously, a broad reminder keyword rule intercepted unrelated questions and returned the same forecast-update guide. Guidance now matches scheduling requests rather than words quoted in a question. The model prompt distinguishes activity explanations from outing plans, follows the requested format, and uses JSON response mode; the outage fallback also keeps activity explanations out of geocoding. The integration preserves the newer main-branch website and media features. See [request/reply verification](request-reply-verification.json).

## Natural questions and general conversation

The conversational revision passes **272 Python tests**, Ruff lint/format and both Docker builds. It adds ASI:One intent/answer handling before planning-only validation: everyday questions get a direct answer, current/daily condition requests fetch real provider data, planning requests preserve the original constraint parser, and ambiguous requests ask a short question. The typed APIs remain compatible. General model answers do not provide live news, market data or browsing; messages remain independent.

Six real-service checks passed: AQI interpretation, a two-sentence photosynthesis explanation, current HSR Layout AQI, tomorrow's rain outlook, a casual jog request retaining AQI/rain limits, and an unclear-location question. The initial live check caught an AQI-150 category error and a model-added location qualifier; regression tests now require the existing verified AQI categories for numeric explanations and preserve supplied location qualifiers.

After deployment, Agentverse Manual Test answered **“Explain photosynthesis in two sentences”** directly, then **“What's the AQI in HSR Layout right now?”** with current model US AQI 141 and PM2.5 29.0 µg/m³, source and retrieval time. A signed typed request to the deployed agent still returned a successful live recommendation with its calendar link. Both containers are healthy. The public guide, description and starter prompts were updated in Agentverse. [Conversational verification](conversation-verification.json) records the checks; raw replies are saved in ignored `artifacts/conversation-*` files. No new ASI:One product-browser test or automated Agentverse evaluation is claimed.

## Reply formatting, rechecks and matching favicon

The reply/update revision passes **251 Python tests**, **six website tests**, Ruff lint/format and both Docker builds. The rebuilt agent and website are healthy. A signed request to the deployed agent returned the new formatted summary. Live Agentverse Manual Test then returned the structured HSR Layout forecast with a Google Calendar link, and `@blr-air updates` returned the on-demand refresh and reminder instructions. Authenticated access to the existing mailbox returned HTTP 200; the agent identity is unchanged.

The live website API returned a 1 November 2026, 08:00–09:00 Asia/Kolkata running window for HSR Layout, average/worst US AQI 87, PM2.5 25.7 µg/m³ and 2% peak hourly rain chance. Its Google Calendar link preserved the exact UTC instants. The downloaded `.ics` contains a one-hour alarm and an event-day `today` recheck prompt. An immediate repeat request retained the cached retrieval timestamp as disclosed. Calendar events remain snapshots; Google Calendar notifications are configured and saved by the user.

The updated usage guide was saved to the Agentverse profile. Its logo now uses the website's UFO favicon from `site/public/favicon.svg`, rendered as a transparent 512 × 512 PNG and saved in Agentverse. Local SVG/PNG avatar assets match that artwork. [Reply and logo evidence](reply-update-verification.json) records the checks; actual replies, the importable calendar example and browser screenshots are under ignored `artifacts/reply-updates/`. The worker still runs on this computer and requires Docker and an awake computer. These follow-up checks do not establish remote hosting or a successful automated Agentverse evaluation.

## Agentverse publication and live chat

On **31 October 2026**, the existing agent identity was connected to the account's Agentverse mailbox. After a container restart, the dashboard showed **Active**, **ASI Available** and **Mailbox**. The published profile has the name **BLR Air Window**, handle **@blr-air**, the project README and description, the custom avatar from `assets/avatar.png`, and three starter prompts.

Two browser-observed production replies are recorded in [publication evidence](agentverse-publication.json): Agentverse Manual Test returned an HSR Layout running window, and ASI:One returned a Koramangala cycling window from **BLR Air Window** after an explicit **@blr-air** mention. Both replies included live measurements, backup windows, timezone and retrieval/source information. An earlier unmentioned ASI:One request went to the account's personal AI and is excluded from agent verification.

Ten test questions were imported into Agentverse, but its automated evaluator failed with `unable to find agent` (`POST /v2/automations` returned 404). No automated score or ten completed interactions is claimed. A subsequent manual request was sent but its reply was not captured before browser control returned to the user. These are developer checks, not outside-user tries. The running worker is local Docker Compose with `restart: unless-stopped`; continuous remote hosting and survival of laptop sleep remain unverified.

Local checks performed on **31 October 2026**, using Python 3.12.14, uAgents 0.26.1 and uagents-core 0.4.12.

## Expanded end-to-end check

The subsequent agent/API expansion passes **243 automated Python tests** and adds grounded AQI/location assessments, a genuine Google Places adapter and a same-origin HTTP service for website integration. Tests cover nullable venue fields, attribution, provider authentication failure, hard constraints after review requests, chunked JSON, request bounds, stale-plan rejection, paid venue-search budgeting and exact backup selection for speech/calendar. Five DOM/PCM checks exercise the website integration before frontend work is handed back to the separate website thread. The frontend build and Docker builds passed.

[HTTP live evidence](web-live-checks.json) records real planning, comparison, backup export, failure handling and a Sarvam speech-to-plan-to-speech roundtrip. Google Places was tested with the stored credential and returned a provider-unavailable result (the earlier stored value returned HTTP 400 `API_KEY_INVALID`; the latest supplied value timed out). Thus genuine venue ratings/reviews remain unavailable pending a valid, reachable Places API project. The adapter's mocked contract tests do not establish live Google availability. The local web service runs on port 8082; public frontend hosting and backend routing are not established by these local checks.

The expanded build passes **165 automated tests**, scoped Ruff lint/format and package build. Added comparison, non-overlapping backups, per-hour hard limits, sunlight/UV/wind/apparent-temperature context, calendar export and Sarvam voice-file input/output. Independent review findings were fixed with regression tests, including unit conversions and preservation of explicit limits and compared places.

[Machine-readable live evidence](live-checks.json) records five passing check groups: actual ASI Hindi parsing with fallback forbidden, all three Open-Meteo endpoints and five cities/timezones, invalid inputs, Docker typed messages and counters, and signed chat/planning callbacks. Callbacks include acknowledgement, text, EndSession, deduplication/no-loop checks, numeric backup windows, impossible-limit rejection, and original wire-schema compatibility.

The live tests found a dependency bug: malformed Pydantic-v1 wire input escaped uAgents' Pydantic-v2 exception handler and killed its message queue, while health remained OK. The compatibility fix was tested by an invalid signed request followed by a successful valid request on the same agent process.

Sarvam `saaras:v4` and `bulbul:v4-flash` passed authenticated synthesis/transcription. A full local CLI run transcribed a spoken Bengaluru request, parsed it through ASI:One, fetched a live recommendation, and saved a 24-kHz spoken WAV. Calendar export of a live daylight-only two-hour HSR window also succeeded. Local artifacts are ignored by Git under `artifacts/`; they contain developer-generated demonstrations, not outside-user proof.

The final combined run also passed: local WAV input, ASI parsing, HSR Layout/Whitefield comparison with AQI ≤100, rain ≤30% and daylight-only, calendar export, and a **33.78-second, 24-kHz spoken answer**. Both places tied at score 117 for 1 November 08:00–09:00 Asia/Kolkata, with two qualifying backup windows each; the answer disclosed the tie. The comparison JSON, single-event calendar and WAV were checked locally under `artifacts/final-*`.

The separately supplied Anthropic credential was tested with a minimal Messages API call and returned **HTTP 401 authentication_error / invalid x-api-key**. Claude was not enabled in the application. ASI:One and Sarvam credentials were verified and remain private; Neo4j is neither required nor connected.

## Initial build checks

- **74 automated tests passed.** Ranking, contiguous windows, bounds, missing/invalid forecast values, provider retries, timezone/DST cases, parser and ASI failure behaviour, wire validation, chat acknowledgement/error/end-session semantics, private counters and CLI execution.
- **Independent code review completed.** Fixed and regression-tested local period end boundaries, alternate city phrasing, unsupported time constraints and incomplete ASI extractions that could otherwise default to Bengaluru.
- **Ruff lint and format checks passed.**
- **Wheel and source distribution built successfully.** Discovery README is included in the installed package.
- **Live Koramangala CLI request passed.** A two-hour cycling recommendation returned current model AQI, PM2.5, future window, rain/temperature, timezone and attribution.
- **Live Melbourne CLI request passed.** Global geocoding resolved Melbourne, Victoria, Australia and returned a recommendation in Australia/Melbourne, including its +11:00 offset.
- **Real signed uAgents request/reply passed locally.** A separate caller identity sent `WindowRequest` to the running agent's `/submit` endpoint and received `WindowResponse` with status `ok` and a live two-hour forecast.
- **Local HTTP health check passed.** `/healthz` returned the expected address, mode and version.
- **Docker image built successfully**, using Python 3.12.16 on Linux; the installed CLI ran the complete offline demo as the non-root application user.
- **Container health and signed live request passed.** The Docker healthcheck reported `healthy`; the caller received a live successful typed response through the container's loopback-published port.
- **Public repository created and pushed:** https://github.com/PDGamerSG/blr-air. Private `.env`, generated state, virtualenv and the pre-existing research notes are excluded from Git.
- **GitHub CI passed on Python 3.12 and 3.13:** [initial CI run](https://github.com/PDGamerSG/blr-air/actions/runs/41183700358).
- **Mailbox deployment started in Docker Compose.** Health responds in mailbox mode; both protocol manifests were published and Almanac API registration succeeded. The provider logs report `Agent mailbox not found: create one using the agent inspector`. Account connection remains pending.
- **Real ASI:One integration verified.** `asi1-mini` returned HTTP 200 and correctly extracted a two-hour run in HSR tomorrow morning from a Hindi/English request. The complete CLI path then returned a live forecast for HSR Layout with those constraints. The private key is stored only in the ignored, mode-0600 `.env`; the running container was recreated with the configured parser and its original agent identity.

Those initial tests establish local implementation, live-data functionality and authenticated ASI:One API parsing. The later publication checks above separately establish Agentverse account registration and explicit-mention routing through the ASI:One chat product. Real-user tries, a feedback-driven change, contest submission and video evidence remain outstanding. Automated ASI parser tests use controlled HTTP responses; the authenticated integration was also tested separately with the configured key.

Developer test traffic is not evidence of outside adoption. Forecast values change, so this record records successful behaviour rather than a permanent recommended time.
