# BLR Air voice input and output

Research date: 2026-10-31. Bounded public documentation review, followed by implementation verification. This is not an exhaustive provider comparison. No secret values were read into tool output or copied into this report.

## Recommendation

Use Sarvam REST speech APIs around the existing BLR Air planning service:

`local WAV → Saaras transcription → existing parse_request / AirService → English summary → Bulbul WAV`

ASI:One remains the optional text parser. Its documented API does not offer a callable speech-to-text or text-to-speech endpoint: the published OpenAPI paths contain chat, responses and models, and chat accepts only `text` and `image_url` content parts. Do not infer audio endpoint compatibility from the phrase “OpenAI-compatible” or from a voice feature in the ASI:One consumer UI. [A1–A3]

One additional credential is required for this hosted speech path: **`SARVAM_API_KEY`**, sent in `api-subscription-key`. The project already uses `httpx`, so no additional SDK is needed. A Claude key adds no capability needed for this slice. No paid API credentials were used during documentation retrieval. [S1]

The implemented adapter is `blr_air/voice.py`. It receives an injected `httpx.AsyncClient`, making the actual REST boundary testable with `httpx.MockTransport`. CLI orchestration can reuse all existing location, scoring, demo and output logic after transcription. Microphone capture, streaming, audio URL downloads and speech hosting are separate follow-on features.

## Exact REST contracts

### Speech input

**Request:** `POST https://api.sarvam.ai/speech-to-text`, multipart form-data. [S2–S4]

```python
headers = {"api-subscription-key": api_key}
data = {
    "model": "saaras:v4",
    "mode": "transcribe",
    "language_code": "unknown",
}
files = {"file": ("request.wav", wav_bytes, "audio/wav")}
```

Let `httpx` generate the multipart boundary; do not set a bare `Content-Type` header manually. `language_code="unknown"` enables language detection. `mode="transcribe"` returns the source language; `mode="translate"` returns English from supported Indic speech. The adapter uses transcription so the transcript remains faithful to what the user said. The existing ASI:One parser can consume it; BLR Air's English-only local fallback should not be advertised as a full multilingual parser.

**Response:** JSON object with `transcript: str`, nullable `request_id`, nullable `language_code`, and optional `language_probability`. Only a nonempty transcript advances to planning. Language-detection confidence is not a word-level transcription confidence score.

**Models:** `saaras:v4` is the current default/recommended model, adding global English and optional keyterm prompting; `saaras:v3` remains available. Explicitly send the model to avoid silent changes in defaults. The older `/speech-to-text-translate` endpoint uses `saaras:v2.5` and is not recommended for a new integration. [S3–S4]

**Provider limits:** synchronous REST accepts up to 30 seconds; longer files require batch or another architecture. Batch supports up to two hours per file, but is unnecessary for a short planning request. The inspected REST reference does not specify an exact maximum byte size; do not claim a provider-wide 10 MiB limit. It accepts WAV, MP3, AAC, AIFF, OGG/Opus, FLAC, MP4/M4A, AMR, WMA, WebM and raw PCM. Raw PCM requires `input_audio_codec` and 16 kHz; WAV is simplest to validate without adding a decoder. The guide recommends 16-bit PCM WAV, mono, 16 kHz; 8 kHz telephony is supported, and the reference says multiple channels are merged. [S2–S4]

**Application limits:** local regular `.wav` files only; complete, nonempty PCM with 16-bit samples, one or two channels, sample rate 8–48 kHz, duration at most 30 seconds, byte size at most 10 MiB. These conservative application limits provide preflight validation with Python's standard `wave` module. Other provider-supported formats need a separate local decoding strategy.

**Input language codes:** `unknown`, `hi-IN`, `bn-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN`, `en-IN`, `gu-IN`, `as-IN`, `ur-IN`, `ne-IN`, `kok-IN`, `ks-IN`, `sd-IN`, `sa-IN`, `sat-IN`, `mni-IN`, `brx-IN`, `mai-IN`, `doi-IN`. These cover English and 22 Indian languages. [S2, S4]

### Speech output

**Request:** `POST https://api.sarvam.ai/text-to-speech`, JSON. [S5–S7]

```json
{
  "text": "The best running window is tomorrow from seven to eight AM.",
  "language_code": "en-IN",
  "model": "bulbul:v4-flash",
  "speaker": "simran_en_customer",
  "speech_sample_rate": 24000,
  "output_audio_codec": "wav"
}
```

Use the same `api-subscription-key` header. The current required field is **`language_code`**, not the `target_language_code` used by older examples. `bulbul:v4-flash` is recommended for new integrations; `bulbul:v3` remains the API default if `model` is omitted. V4 uses persona IDs such as `simran_en_customer`, and short v3 speaker IDs such as `shubh` are invalid on v4. [S5, S7]

**Response:** `{ "request_id": "…", "audios": ["<base64 WAV>"] }`. With one text input, require exactly one audio string, decode it using strict base64 validation, and validate the WAV container and frames before saving. Do not concatenate independently encoded WAV files or silently use only the first of several unexpected outputs. [S5]

**Limits:** `bulbul:v4-flash` and `bulbul:v3` accept at most 2,500 characters per REST request. REST sample rates are 8,000; 16,000; 22,050; 24,000; 32,000; 44,100; 48,000 Hz. Explicit 24,000 Hz avoids contradictory older tutorial defaults. V3/v4 pace can be 0.5–2.0; pitch and loudness parameters are unsupported and unnecessary here. REST output can be WAV, MP3, AAC, FLAC or Linear16. Although `opus` appears in the schema enum, the reference explicitly says it currently returns an error on this endpoint for v3/v4. [S5, S7]

**Languages:** v3 lists English plus Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil and Telugu. V4 Flash currently offers English, Hindi, Bengali, Gujarati, Kannada, Marathi, Punjabi, Tamil, Telugu and English–Hindi voice styles; Malayalam and Odia are not yet offered in the v4 voice catalog, despite their presence in the shared request enum. The adapter uses a matching documented persona for each of the nine supported BCP-47 language codes. Default output is English. `language_code` chooses speech rendering; it does not translate an English forecast into Kannada or another language. [S5, S7]

## CLI-facing adapter contract

```python
voice = SarvamVoice(client: httpx.AsyncClient, api_key: str)
transcript = await voice.transcribe(path: Path, language="unknown")  # -> str
saved_path = await voice.synthesize(text: str, output: Path, language="en-IN")  # -> Path
```

- Missing key, invalid input, malformed/empty provider response, timeout, HTTP failure, malformed output audio and write failures are exposed as `domain.AirError`, suitable for existing CLI handling.
- The adapter makes only fixed-host Sarvam POST requests, with redirects disabled even when the injected client enables redirects. It never downloads user-supplied URLs or includes provider response bodies in errors.
- Requests have a 10-second connection timeout and 60-second operation timeout. STT response bytes are capped at 1 MiB and TTS responses at 48 MiB. There is no silent retry of paid speech requests; the caller gets an actionable error.
- Input recordings are not copied to project storage. Output must be a new `.wav` path with an existing parent directory. A private temporary file is published atomically with mode `0600`, refusing existing files, symlinks, and files created by another process while the API call was in flight.
- Speech text must be 1–2,500 characters. Build a concise spoken summary from the same recommendation, retaining the location, time zone, date, forecast limits and relevant caution. Do not truncate a warning midway. Keep the complete normal CLI result available separately.
- A speech synthesis failure must not erase a successful planning result. CLI code should print/preserve the result and clearly report that audio output failed.
- A `--demo` forecast should remain explicitly synthetic. Speech APIs are network calls even when planning uses a demo provider; an offline demo must not silently upload recordings.

The file and summary interfaces are intentionally enough for the first working slice. Local recording can be captured by an existing recorder and supplied to the CLI. Audio playback can use the user's normal WAV player; automatic microphone recording and speaker playback are not required to demonstrate both API directions.

## Fetch.ai ChatProtocol audio resources

The official `uagents_core.contrib.protocols.chat` source defines `ResourceContent(type="resource", resource_id=<UUID4>, resource=Resource | list[Resource])`. A `Resource` carries `uri: str` and `metadata: dict[str, str]`; `mime_type` and `role` are described metadata fields. A resource list's first item is primary. `ChatMessage` supports resource content alongside text and session controls, but these models do not fetch, transcribe, validate or play audio. The same shape is present in this project's installed package. [F1]

For example, a future voice attachment may use `Resource(uri="https://approved-host/audio.wav", metadata={"mime_type": "audio/wav"})`. That is a transport representation, not evidence that all ASI:One clients accept/play it or that microphone input reaches this agent as a resource. The text-only tutorial even treats unrecognized content as unexpected; client interoperability requires an end-to-end test. [F2]

BLR Air currently extracts only `TextContent` and should not claim native ChatProtocol voice-resource handling. For a later attachment path, first define a trusted upload/download service and a resource contract. Fetching arbitrary `Resource.uri` values creates concrete SSRF and resource-exhaustion risks: loopback/private/link-local/metadata hosts, redirects into private networks, DNS changes between validation and connection, non-HTTP schemes, huge/chunked bodies, misleading MIME types, decompression bombs, and slow downloads. Never forward the Sarvam key to an attachment host. Prefer an exact HTTPS host allowlist with controlled storage and egress rules, no redirects, bounded streamed downloads and actual decoding validation. Merely checking an URL's suffix, MIME string or initially resolved IP is insufficient. These are engineering inferences from the unrestricted URI field, not security guarantees provided by ChatProtocol. [F1]

The local-file CLI slice avoids adding this downloader, public audio hosting or permanent voice storage.

## Optional local speech alternatives

| Option | Evidence and fit | Additional work |
| --- | --- | --- |
| `whisper.cpp` transcription | Maintainer README supports fully offline inference, Apple Silicon/Metal/Core ML, and a `whisper-cli` WAV path; the example CLI requires 16-bit WAV. Good local STT alternative after model download. [L1] | Native binary/build and model artifact management; select a multilingual model for Indic speech and test real Bengaluru locality recognition. `base.en` is English-only. |
| Piper speech synthesis | Maintainer describes a local neural TTS engine and CLI, with explicit voice/model download and WAV output. [L2–L3] | New dependency and model files; inspect each voice's model card and distribution/license terms. Current documented voice list includes English/Hindi/Malayalam/Telugu/Nepali but not Kannada. Do not promise uniform Indic-language parity. [L4] |

A fully local speech pair needs no paid speech credential after model downloads. The complete live forecasting workflow still needs weather/air API network access; only the synthetic demo can be wholly offline. Sarvam is the smaller integration for this repository because it needs no native inference runtime or model downloads, and its documented language set includes Kannada. Latency and recognition quality on actual user recordings remain empirical questions.

## Evidence map

All sources below were retrieved on **2026-10-31**. Provider documentation pages did not supply a reliable page publication date; they are treated as current retrieved documentation, not dated announcements.

| ID | Primary source and supporting location | Observed claim | Classification / limit |
| --- | --- | --- | --- |
| A1 | [ASI:One API index](https://docs.asi1.ai/api-reference/llms.txt), API Docs; [OpenAPI JSON](https://docs.asi1.ai/openapi.json), `paths` | Chat, responses and model endpoints; no audio paths | Fact about published API surface, not proof that a private API cannot exist |
| A2 | [Create a chat completion](https://docs.asi1.ai/api-reference/chat-completions/create-a-chat-completion), Types → ChatMessage / ChatMessageContent | Only text/image_url content; other types rejected with `unsupported_content_part` | Explicit API documentation |
| A3 | [OpenAI compatibility](https://docs.asi1.ai/documentation/build-with-asi-one/openai-compatibility), Overview | Compatibility covers chat and responses request formats | No inference that OpenAI's audio endpoints exist |
| S1 | [Authentication](https://docs.sarvam.ai/api-reference/authentication), API subscription keys | `api-subscription-key` header; Bearer also documented | Use the header used by official SDK examples |
| S2 | [STT REST reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe), Request / Response | Exact multipart fields, models, language codes and transcript schema | Mode description retains one stale v3-only phrase; newer model/guide sections explicitly cover v4 |
| S3 | [STT REST guide](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api), Preparing Your Audio | ≤30s; 16-bit WAV/16 kHz/mono recommended; invalid audio rejected | No numeric byte cap found |
| S4 | [Saaras model](https://docs.sarvam.ai/api/api-guides-tutorials/models/saaras), At a Glance / Output Modes / Language Support | V4 current; V3 available; 23 languages; translate mode | Model documentation, not independently measured accuracy |
| S5 | [TTS REST reference](https://docs.sarvam.ai/api-reference/text-to-speech/convert), Request / Response | Required `text`, `language_code`; v4 personas; base64 `audios`; 2,500 chars | Shared enum contains unsupported v4 language entries; use model-specific guide too |
| S6 | [TTS REST guide](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/rest-api), response and examples | JSON base64 audio flow | Contains stale sample-rate and speaker examples; see discrepancy notes |
| S7 | [Bulbul model](https://docs.sarvam.ai/api/api-guides-tutorials/models/bulbul), model comparison / languages / limits | V4 personas; V3 default; language exclusions; codec caveat | No claim of live quality or latency |
| F1 | [Fetch.ai ChatProtocol source](https://github.com/fetchai/uAgents/blob/1f19f7e06c4d388ffda2a26d42d1b928c40886a2/python/uagents-core/uagents_core/contrib/protocols/chat/__init__.py), Resource / ResourceContent / ChatMessage | Resource URI + metadata representation | Last source-file change returned by GitHub: 2025-10-03; checked against installed package |
| F2 | [ASI:One Agent Chat Protocol tutorial](https://docs.asi1.ai/documentation/tutorials/agent-chat-protocol), steps 2–5 | Acknowledgements, text processing, session controls | Does not establish end-client audio interoperability |
| L1 | [whisper.cpp maintainer README](https://github.com/ggml-org/whisper.cpp), supported platforms / quickstart | Local inference, Apple optimization, WAV CLI | No local installation/performance trial performed |
| L2 | [Piper maintainer README](https://github.com/OHF-Voice/piper1-gpl) | Local neural TTS | Additional package/model/runtime requirement |
| L3 | [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md), downloading voices / running | Download model, synthesize to WAV | Model load adds per-command latency |
| L4 | [Piper voices](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md), languages / models | Listed language set and model-card licensing | No Kannada entry in retrieved list; not proof no third-party Kannada voice exists |

Documentation discrepancies were retained rather than hidden: the Saaras reference's mode description says v3-only while the v4 model and REST guides explicitly support the same modes; Bulbul REST tutorial has older short speaker names in some v4 examples and says default 24 kHz while reference/model pages say 22,050 Hz; TTS response prose labels all audio WAV although the request accepts several codecs. The implementation pins v4, known v4 personas, explicit WAV and 24,000 Hz, avoiding these ambiguous defaults.

## Retrieval and verification log

- Discovery: fetched `https://docs.asi1.ai/llms.txt`, `https://docs.sarvam.ai/llms.txt`, `https://docs.agentverse.ai/llms.txt`; followed official Markdown/index links. No general web search engine was available or required for these vendor contracts.
- ASI queries: fetched `/documentation/llms.txt`, `/api-reference/llms.txt`, `/openapi.json`, `/documentation/models.md`, `/documentation/build-with-asi-one/openai-compatibility.md`, `/api-reference/chat-completions/create-a-chat-completion.md`, `/documentation/tutorials/agent-chat-protocol.md`; inspected `paths`, `content`, `audio`, `supported`, and model sections.
- Sarvam queries: fetched `/api-reference/authentication.md`, `/api-reference/speech-to-text/transcribe.md`, `/api-reference/text-to-speech/convert.md`, `/api/api-guides-tutorials/speech-to-text/overview.md`, `/speech-to-text/rest-api.md`, `/text-to-speech/overview.md`, `/text-to-speech/rest-api.md`, `/models/saaras.md`, `/models/bulbul.md` under the same guide prefix. Searched exact fields `model`, `mode`, `language_code`, `speaker`, `output_audio_codec`, `audios`, `30`, `2500`, `input_audio_codec`, `file`, `base64`. Also fetched `/changelog/2026/10/30.md`; it concerns a chat-model release and provides no further voice evidence.
- Fetch.ai queries: fetched GitHub recursive tree `https://api.github.com/repos/fetchai/uAgents/git/trees/main?recursive=1`, filtered paths containing `chat`/`resource`, retrieved the raw protocol package `__init__.py`, and queried its latest file commit. Read installed `.venv/lib/python3.12/site-packages/uagents_core/contrib/protocols/chat/__init__.py` and the project's text handler for applicability.
- Local alternatives: fetched the raw maintainer README for `ggml-org/whisper.cpp` and README/CLI/VOICES docs for `OHF-Voice/piper1-gpl`. No binaries or speech models were installed.
- Failed/stale leads: `https://uagents.network/docs/llms.txt` failed DNS; the guessed raw Fetch.ai `chat.py` URL returned 404 (actual path is `chat/__init__.py`); guessed ASI `/documentation/api-reference/{overview,chat-completions,models}.md` and Sarvam `speech-to-text/{api-reference,models}.md` / `text-to-speech/api-reference.md` returned page-not-found documents. `https://docs.fetch.ai/llms.txt` redirected to the general Fetch site, and Innovation Lab's guessed `/resources/docs/llms.txt` returned a 404 page. These failures were not treated as evidence of absent capabilities.
- Reproducible retrieval method: public `curl -L --max-time 30 -sS URL` / Python `urllib.request`, with local text filtering. No authenticated provider API calls were needed to verify the contract documentation.
- Implementation proof: focused `tests/test_voice.py` exercises actual WAV parsing, multipart/JSON requests through `httpx.MockTransport`, malformed input/output, error redaction, redirect refusal, private atomic file output, write races and Kannada persona selection. Mock tests establish integration behavior, not provider availability or recognition quality. Live smoke results are recorded below when available.

## Next falsifying checks

Live API smoke completed on 2026-10-31 using the privately configured key: `bulbul:v4-flash` generated a valid **3.28-second, 24,000 Hz WAV (157,484 bytes)** from “Find a one hour running window in Bengaluru tomorrow morning.” `saaras:v4`, `mode=transcribe` returned the same sentence, preserving Bengaluru and tomorrow. This confirms both authenticated endpoint contracts and the local WAV handling. It is synthetic-speech round-trip evidence, not a microphone/accent benchmark. The temporary audio was saved outside the repository at `/var/folders/4s/14dbpv1d6k58tqyh5gtbgf9w0000gn/T/blr-air-voice-smoke-ct2o4l22/request.wav`.

Next, use human recordings of “HSR Layout”, “Whitefield” and “Bengaluru”, including Kannada and code-mixed requests. Check that the interpreted location and date match the transcript, and that spoken forecast times and caveats survive synthesis. This is needed before claiming multilingual voice accuracy. A client-level ChatProtocol attachment test is separately required before claiming Agentverse/ASI:One voice attachment support.
