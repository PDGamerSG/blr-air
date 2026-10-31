# Verification record

Local checks performed on **31 October 2026**, using Python 3.12.14, uAgents 0.26.1 and uagents-core 0.4.12.

## Expanded end-to-end check

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

These tests establish local implementation, live-data functionality and authenticated ASI:One API parsing. They do not establish routing through the ASI:One chat product, Agentverse account registration, real-user tries, a feedback-driven change, contest submission or video evidence. Automated ASI parser tests use controlled HTTP responses; the authenticated integration was also tested separately with the configured key.

Developer test traffic is not evidence of outside adoption. Forecast values change, so this record records successful behaviour rather than a permanent recommended time.
