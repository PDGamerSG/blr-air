# BLR Air Window implementation

The accepted deliverable is a Python agent, tests, docs, and CLI. The user's instruction to build immediately supersedes additional design approval checkpoints.

The same service powers the CLI, Chat Protocol and typed agent requests. Open-Meteo provides current modelled AQI/PM2.5 and hourly AQI, PM2.5, rain probability and temperature. Built-in Bengaluru locality centroids precede global geocoding. HTTP calls are asynchronous and bounded; missing or invalid values are excluded, never converted to good conditions.

Select a contiguous one- or two-hour block entirely in the next 48 hours and between 05:00 and 21:00 in the location's timezone. Compare blocks by mean hourly heuristic cost: US AQI + 0.5 × PM2.5 + 1.5 × rain probability + 5 × degrees above 30°C. Break ties by earliest time. Report average AQI/PM2.5, peak rain/temperature, category, timezone, source and retrieval time. This is a transparent preference heuristic, not a health or exposure model. Current conditions must come from the provider's current section and have their own timestamp.

ASI:One is the only optional language model. Without a key, deterministic extraction supports the documented examples and free city names. No unrecognised city silently becomes Bengaluru. Today/tomorrow and morning/afternoon/evening constraints are honoured. Invalid duration, missing contiguous data and provider failures produce actionable responses.

The mailbox agent keeps its seed in a local ignored .env. The typed protocol returns a structured success or error response. Chat acknowledges messages, replies with text, closes the session, and never replies to acknowledgements. Usage stores counts and keyed sender hashes, never prompts or raw sender addresses.

Deployment includes a container, persistent data volume, health endpoint and restart instructions. No public registration, external feedback, demo video, contest submission or real-user evidence is claimed without being performed. The submission kit records these as pending external actions.

## Expanded scope approved 31 October

Compare up to three places at each place's own best eligible time. Supply the best window and up to two non-overlapping backups, disclose tied scores, and report failed places separately. Optional user ceilings apply to every hourly value: US AQI, rain percent, apparent temperature °C, UV and wind km/h. Explicit Fahrenheit/mph/m/s input is converted. Daylight-only requires the entire interval to lie between modelled sunrise/sunset; absent data cannot satisfy a limit. Limits are never silently relaxed.

Keep the published coordinate WindowRequest/WindowResponse schemas unchanged. A separate blr-air-plan v0.1.0 protocol exposes place names, comparisons, numeric backup windows and all limits. Chat and CLI use the same service. Fix the installed uAgents 0.26.1 Pydantic-v1/v2 validation exception mismatch at the message-processing boundary so malformed signed requests return an error and leave the queue working.

CLI adds a single-event UTC iCalendar export with a re-check reminder and an optional Sarvam voice-file path. Local PCM16 WAV input goes to Saaras v4, then ASI parsing and the shared forecast service; Bulbul v4 produces a bounded English spoken answer. Output files do not overwrite existing paths. Voice does not download remote user URLs, record a microphone, or imply ASI chat supports audio attachments. Keys remain in ignored .env.

Neo4j is deferred until a maintained route network and suitable segment-level data justify a route-planning feature. No new database dependency is needed for comparing hourly arrays.
