# BLR Air Window: best time to go outside, by air quality and rain

Finds the best available 1–2 hour window in the next 48 hours to run, cycle, walk, commute or take kids outdoors in Bengaluru or another city, using live AQI, PM2.5, rain-probability and temperature forecasts.

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:domain/utility](https://img.shields.io/badge/utility-4CAF50)

## Summary

Ask when the air is cleaner and rain/heat are lower for going outside. Get current modelled US AQI and PM2.5, a recommended time slot in the location's timezone, forecast conditions and the data retrieval time. If every eligible slot has unhealthy air, the reply explains that and suggests considering an indoor alternative.

## Key features

- Live current and hourly US AQI and PM2.5, plus rain probability and temperature.
- Contiguous 1–2 hour windows entirely within the next 48 hours, between 05:00 and 21:00 local.
- Today/tomorrow and morning/afternoon/evening preferences.
- Bengaluru localities including HSR Layout, Koramangala, Whitefield, Indiranagar, Electronic City, Jayanagar, Bellandur, Hebbal, Cubbon Park and Lalbagh.
- Global city geocoding; use city and country to disambiguate.
- Typed agent-to-agent interface for planners.
- Up to two non-overlapping backup windows for each recommendation.
- Compare two or three places, ranked at each place's own best eligible time. Ties and unavailable places are disclosed.
- User-set per-hour limits for AQI, rain, feels-like temperature, UV and wind; optional daylight-only windows.
- AQI category explanations, outdoor-condition warnings, resolved-location map links and a before-you-go checklist.
- Optional real Google Maps customer ratings, review excerpts, opening hours and venue matching when Places API access is configured. Customer ratings are separate from air-quality guidance.

## Usage instructions

**Ask in your own words.** The examples below are suggestions, not a required format. You can ask general everyday questions, request a short explanation or translation, ask what an AQI number means, check current conditions, or plan an outing. General questions receive direct conversational answers; live-condition questions use Open-Meteo data, and outing requests use the forecast planner.

```text
@blr-air Explain photosynthesis in two sentences
@blr-air What does US AQI 150 mean?
@blr-air What's the AQI in HSR Layout right now?
@blr-air Will I need an umbrella in HSR Layout tomorrow?
@blr-air I'd love a jog around HSR tomorrow morning. Any good time?
```

New here? Send **`@blr-air help`**. For forecast refreshes and reminder options, send **`@blr-air updates`**. In ASI:One, include the **@blr-air** mention so your message reaches this agent instead of your personal AI.

For live conditions, name the city or locality. For an outdoor plan, optionally add an activity and 1- or 2-hour duration. Planning defaults: Bengaluru, walking, one hour, next 48 hours. If a question needs more information, the agent asks a short clarifying question.

```text
best 1-hour window to run in HSR Layout
best 2-hour cycling window in Koramangala
when is the air cleanest in Whitefield
take kids outside in Melbourne tomorrow morning
best window to walk in Paris, France today
compare HSR Layout and Whitefield for a run tomorrow morning
run in HSR Layout with AQI at most 100, rain at most 30%, daylight only
walk in Cubbon Park tomorrow morning with reviews
show opening hours for Royal Botanic Gardens, Melbourne tomorrow morning
```

The answer identifies the resolved location and timezone. AQI/PM2.5 are averages over the recommended window; rain chance and temperature are hourly maxima. Ranking balances air pollution, rain and heat. It is not a guarantee of safety.

Optional limits must hold for every hour; missing data cannot satisfy a limit and limits are never relaxed automatically. Feels-like temperature is °C and wind is km/h. Daylight-only requires the whole block to fit between forecast sunrise and sunset as well as the 05:00–21:00 activity window. UV, wind and feels-like context is shown when available.

## Read your answer and get an update

Outdoor-planning replies put your **recommended date and time first**, followed by **conditions**, **why that time was selected**, **precautions**, and up to two **backup options**. Current-condition replies show current model estimates, while daily weather replies summarize the available hours for today or tomorrow. General answers use the format that fits your question. All forecast times use the resolved location's timezone. The source and **Forecast retrieved** timestamp show which data the answer used.

Each planning reply includes a complete, copyable **Get an update** prompt that keeps your activity, places, duration, day, period and limits. Send it again before leaving. Each request is independent: use the complete request instead of a follow-up such as “same place” or “update that.” Include the relevant details if asking about a previous answer. Today and tomorrow are resolved again when you resend the request, so change **tomorrow** to **today** when rechecking on the outing date.

Forecast data may be cached for up to **five minutes**. A recheck during that time may return the same retrieval timestamp. This agent does **not** monitor a selected window in the background or schedule automatic chat alerts.

For a reminder, open **Add this window to Google Calendar** in the forecast reply, set a notification **1 hour before**, then save. The link pre-fills the selected time, location and a recheck prompt; nothing is added until you save it. Alternatively, download a calendar file through the website or CLI and import it into your calendar; the `.ics` includes a one-hour recheck reminder. The event description uses **today** in its prompt so it targets the event date when you recheck. Calendar events are snapshots and do not update themselves.

For example:

```text
@blr-air best 1-hour window to run in HSR Layout tomorrow morning
@blr-air compare HSR Layout and Whitefield for a 2-hour cycle tomorrow morning
@blr-air walk in Cubbon Park tomorrow morning with AQI at most 100, rain at most 30%, daylight only
```

## Use cases and agent API

Runners and cyclists selecting a time, parents considering outdoor play, and commuters considering rain and pollution. Agents send `WindowRequest{latitude, longitude, hours, activity, day, period}` to protocol **blr-air-window v0.1.0**. Required fields are latitude and longitude; defaults are 1 hour, walk, next48, any period. `WindowResponse` contains status, summary, start/end, timezone, AQI/PM2.5, peak rain/temperature, worst AQI, source and retrieval time. Errors return status `error` with an error code and no fabricated measurements.

The separate **blr-air-plan v0.1.0** protocol accepts `PlanRequest{places, hours, activity, day, period, max_aqi, max_rain, max_temperature, max_uv, max_wind, daylight_only}`. `places` is one to three city/locality names; optional limits default to unset. `PlanResponse` supplies winner, ties, partial-result flag and a result per place containing numeric best/backup windows, timezone, source and retrieval time. Original coordinate request/response schemas remain compatible.

## Limitations and known issues

General conversation uses the configured ASI:One model. Without it, documented English planning and basic AQI/PM2.5 explanations still work, while general questions report that conversational answers are unavailable. General answers use model knowledge; they do not provide live news, market prices or web browsing. Current weather/air figures come from the forecast provider. Questions are independent, so the agent does not remember an earlier location or recommendation.

The additional **blr-air-plan v0.2.0** protocol uses `DetailedPlanRequest` (the same planning fields plus `include_venue`) and `DetailedPlanResponse`. It adds structured `assessment` and `venue` data per place. The original v0.1 planning protocol and coordinate protocol remain available with unchanged schemas. Genuine venue access depends on the configured Google Places project and key.

Open-Meteo/CAMS air quality is a model forecast, not CPCB station readings or street-level measurements. Not medical advice. Supported periods use fixed local hours; daylight-only is an extra sunrise/sunset filter. Exact clock-time filters, dates beyond the next 48 hours, push alerts and historical data are not supported. Comparisons evaluate each place at its own best time, not one shared instant. Geocoding can be ambiguous; add country or use coordinates through the original typed API. Complete forecast data must be available. A service outage gives a retry message. With no ASI:One API key configured, documented English requests work through local parsing; freeform multilingual understanding requires ASI:One. Chat replies provide a Google Calendar link; calendar-file downloads and optional Sarvam audio-file input/output are available through the website or CLI, not as attachments or voice messages in this chat agent.

## Metadata and credits

Calendar and Sarvam audio are also exposed by the separate HTTP API for website clients. Agentverse chat remains text-only. Google Places access failures are disclosed; venue stars are never invented. Review excerpts retain provider/author attribution and represent a small relevance-ranked sample, not all customers. Opening status is for now and does not guarantee access during a future forecast window.

Data: [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), [CAMS](https://atmosphere.copernicus.eu/), and [Open-Meteo Forecast](https://open-meteo.com/en/docs). Optional language understanding: ASI:One (`asi1-mini`). Transport: Fetch.ai uAgents Agent Chat Protocol. Built for Stranger Builds Bangalore 2026.

Keywords: air quality, AQI, PM2.5, pollution, best time to run, cycling, rain, heat, Bengaluru, Bangalore, HSR Layout, Whitefield, Koramangala, children, outdoor window.
