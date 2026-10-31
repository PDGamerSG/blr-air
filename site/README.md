# BLR Air Window — landing page

A single scroll-driven page for the BLR Air Window agent, styled after Stranger Builds. It is a static site with no backend. The only network calls are keyless Open-Meteo requests made directly from the browser, to the same endpoints the agent uses.

## The scroll story

| # | Section | What happens |
| --- | --- | --- |
| 01 | Orbit | A UFO hovers over a toon-shaded Bengaluru at night. A live sticker shows the current modelled AQI. |
| 02 | Haze | The camera dives into PM2.5 smog: "AQI is a number. You need a time." |
| 03 | Four signals | AQI, PM2.5, rain and heat orbit the UFO while the cost formula assembles term by term. |
| 04 | Scanner | Live 48-hour forecast for any of the 20 localities, or any city. It uses the agent's own scoring rules, ported 1:1 from `blr_air/scoring.py`. |
| 05 | City | A top-down map of Bengaluru: the Outer Ring Road, lakes, Cubbon Park, Lalbagh, Vidhana Soudha, and live AQI beacons. Click a locality to scan it. |
| 06 | Hire | A hand-drawn rough.js diagram of the chat and typed-protocol paths, plus the `WindowRequest` snippet. |
| 07 | Prompts | A 3D drum of example prompts. Drag, scroll or press arrow keys; tap to copy and open ASI:One. |
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

`dist/` uses relative URLs, so it can be served from any static host or sub-path: Vercel, Netlify, GitHub Pages or Cloudflare Pages.

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
- `src/ui/` — scanner, prompt wheel, diagram, live ticker and map board.
- `src/main.ts` — preloader, Lenis smooth scroll, GSAP ScrollTrigger reveals, section controllers, cursor and motion toggle.

The motion toggle in the footer, and `prefers-reduced-motion`, pause the WebGL animation, marquee and grain.
