# BLR Air Window — landing page

A scroll-driven page and working planning interface for the BLR Air Window agent, styled after Stranger Builds. The main planner calls the Python service through same-origin `/api` routes, so natural-language requests use the shared agent logic. The quick scanner and city beacons also make keyless Open-Meteo calls directly from the browser.

The planner shows the interpreted request, current modelled air quality, outdoor assessment, warning conditions, best/backup windows, place comparisons and source freshness. Users can download the exact selected window as an iCalendar event or ask Sarvam to speak it. A local WAV recording can be transcribed into an editable request. Optional real venue results show Google Maps ratings, opening hours, accessibility fields and attributed customer-review excerpts separately from the air-quality assessment.

## The scroll story

| # | Section | What happens |
| --- | --- | --- |
| 01 | Orbit | A UFO hovers over a toon-shaded Bengaluru at night. A live sticker shows the current modelled AQI. |
| 02 | Haze | The camera dives into PM2.5 smog: "AQI is a number. You need a time." |
| 03 | Four signals | AQI, PM2.5, rain and heat orbit the UFO while the cost formula assembles term by term. |
| 04 | Planner and scanner | Natural-language planning through the shared Python service, with comparisons, reviews and downloads. A separate keyless quick scanner shows a single-place 48-hour forecast. |
| 05 | City | A top-down map of Bengaluru: the Outer Ring Road, lakes, Cubbon Park, Lalbagh, Vidhana Soudha, and live AQI beacons. Click a locality to scan it. |
| 06 | Hire | A hand-drawn rough.js diagram of the chat and typed-protocol paths, plus the `WindowRequest` snippet. |
| 07 | Prompts | A 3D drum of example prompts. Drag, scroll or press arrow keys; tap to send a request to the on-page agent. |
| 08 | Fine print | Redactions wipe away to reveal the honest limitations. |
| 09 | Origin | Stranger Builds context, a submissions countdown, and the five-step journey. |
| 10 | Landing | Dawn breaks. Gaali (ಗಾಳಿ, "air") takes off the gas mask under a green beam, and the final CTAs appear. |

## Run

```sh
cd site
npm install
npm run dev       # http://localhost:5173
npm run build     # static output in site/dist
npm run preview
```

Run the Python web service on `127.0.0.1:8080` alongside Vite for development; Vite proxies `/api` there. On Vercel, `/api/*` goes through the same-origin proxy in `../api/proxy.mjs` to `BLR_AIR_API_ORIGIN`; see the root README. Production should serve `site/dist/` and `/api` from the same origin using the Python service or a reverse proxy. A standalone static host can show the landing page and keyless quick scanner, but cannot run the full planner without routing `/api` to the server. No API keys belong in browser code or `VITE_*` variables.

The server reports configured language, voice and venue capabilities at `/api/status`. Missing optional credentials produce visible unavailability messages. The interface never substitutes synthetic forecasts for a failed full-agent request. An interrupted or new request clears previous full-agent results; transient plan IDs expire, so downloads require a fresh plan afterward.

Browser requests use `POST /api/plan`, `POST /api/transcribe` (raw WAV), `POST /api/speech` and `GET /api/calendar/{plan_id}`. Calendar and voice requests preserve the selected place and backup-window indexes. Voice uploads require a complete 16-bit PCM WAV, up to 30 seconds and 10 MiB. An explicit microphone button requests permission, records at most 30 seconds, encodes genuine mono PCM16 WAV, and stops all microphone tracks on completion or cancellation. Microphone access requires HTTPS or localhost and browser permission. Cancelling discards the recording without sending it. Speech output is English.

## Edit links

All outbound links live in `src/config.ts`: ASI:One, the Agentverse profile URL (derived from the agent address), GitHub, the feedback issue template and Stranger Builds. The agent handle (`@blr-air`) and the submissions deadline are also there. Update the handle after you claim it on Agentverse.

For social previews, set `og:image` in `index.html` to an absolute URL once the site has a domain.

## 3D models

The UFO, Gaali, Vidhana Soudha and the pink trumpet tree are generated procedurally by a Blender script:

```sh
npm run models    # blender --background --python blender/build_models.py -- public/models
```

The script exports flat colours only. The page re-shades everything with a 3-step toon ramp and inverted-hull ink outlines (`src/scene/toon.ts`). Material names starting with `glow` become unlit, and names starting with `glass` become translucent.

## Code map

- `src/scene/` — Three.js world: `World.ts` (renderer, scroll keyframes), `state.ts` (per-section camera, sky, beam and haze states), `city.ts`, `ufo.ts`, `signals.ts`, `sky.ts`, `haze.ts`, `toon.ts`.
- `src/air/` — browser port of the agent's provider and scoring rules (`openMeteo.ts`, `scoring.ts`).
- `src/ui/planner.ts` — shared-service planner, request state, selection/download actions, review attribution and safe DOM rendering.
- `src/styles/planner.css` — responsive planner styles using the existing project tokens.
- `src/ui/` — quick scanner, prompt wheel, diagram, live ticker and map board.
- `src/main.ts` — preloader, Lenis smooth scroll, GSAP ScrollTrigger reveals, section controllers, cursor and motion toggle.

The motion toggle in the footer, and `prefers-reduced-motion`, pause the WebGL animation, marquee and grain.

The planner's requests and provider text are rendered as text, never injected as HTML. Outbound provider links must be HTTPS without embedded credentials. The footer includes public privacy and terms describing data sent to ASI, Open-Meteo, Google Places and Sarvam, plus Google's required terms/privacy links. Review content is a relevance-ranked provider sample, not a complete sentiment analysis.
