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

## Usage instructions

In ASI:One enable Agents and select this agent or use its configured handle. Input a city or locality, optionally an activity and 1- or 2-hour duration. Default: Bengaluru, walking, one hour, next 48 hours.

```text
best 1-hour window to run in HSR Layout
best 2-hour cycling window in Koramangala
when is the air cleanest in Whitefield
take kids outside in Melbourne tomorrow morning
best window to walk in Paris, France today
```

The answer identifies the resolved location and timezone. AQI/PM2.5 are averages over the recommended window; rain chance and temperature are hourly maxima. Ranking balances air pollution, rain and heat. It is not a guarantee of safety.

## Use cases and agent API

Runners and cyclists selecting a time, parents considering outdoor play, and commuters considering rain and pollution. Agents send `WindowRequest{latitude, longitude, hours, activity, day, period}` to protocol **blr-air-window v0.1.0**. Required fields are latitude and longitude; defaults are 1 hour, walk, next48, any period. `WindowResponse` contains status, summary, start/end, timezone, AQI/PM2.5, peak rain/temperature, worst AQI, source and retrieval time. Errors return status `error` with an error code and no fabricated measurements.

## Limitations and known issues

Open-Meteo/CAMS air quality is a model forecast, not CPCB station readings or street-level measurements. Not medical advice. Supported periods use fixed local hours, not sunrise/sunset. Exact clock-time filters, dates beyond the next 48 hours, alerts and historical data are not supported. Geocoding can be ambiguous; add country or use coordinates through the typed API. Complete forecast data must be available. A service outage gives a retry message. With no ASI:One API key configured, documented English requests work through local parsing; freeform multilingual understanding requires ASI:One.

## Metadata and credits

Data: [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), [CAMS](https://atmosphere.copernicus.eu/), and [Open-Meteo Forecast](https://open-meteo.com/en/docs). Optional language understanding: ASI:One (`asi1-mini`). Transport: Fetch.ai uAgents Agent Chat Protocol. Built for Stranger Builds Bangalore 2026.

Keywords: air quality, AQI, PM2.5, pollution, best time to run, cycling, rain, heat, Bengaluru, Bangalore, HSR Layout, Whitefield, Koramangala, children, outdoor window.
