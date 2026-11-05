# Delhi Air for Wear OS

A smartwatch client for the Delhi Air agent. **Ask the agent** posts to `/api/ask`, which runs the same `AirService.chat` conversation people reach through ASI:One. If the agent can't be reached, the watch plans by itself with a local copy of the scoring and says so. It needs internet through Wi-Fi, LTE or a paired phone's connection, and no phone app.

Requires Wear OS 3 or newer (Android 11, API 30): Galaxy Watch 4 onwards, Pixel Watch, OnePlus Watch 2 and similar.

## What it does

| Feature | On the watch |
| --- | --- |
| Current air | Big AQI number, category and PM2.5 |
| Measured air | CPCB/DPCC station reading through WAQI. It sets the headline only within 6 km |
| Best window | Best time in the next 48 hours, with up to 2 backups |
| Planning | Activity, 1 or 2 hours, day, time of day, daylight only |
| Limits | AQI, rain, feels-like, UV and wind. Never relaxed automatically |
| For You | The agent suggests what to do, when, where and why without being asked, and explains its reasoning |
| Learns your routine | Which activities you choose or decline, hours you're active, and your usual area. Kept on the watch |
| Speaks up by itself | An hourly check that notifies you of a good window soon or a stay-in warning, at most twice a day and never at night |
| Where and when | Ask "a walk near Rohini" or "a bike ride near Dwarka" and the agent picks a real place and time, with alternatives |
| Places | 22 Delhi NCR localities, your location, or any city by asking |
| Compare | 2 or 3 places, with measured readings, disclosing shared model cells and contradictions |
| Speak or type to the agent | The same agent as ASI:One answers, and the watch shows its plan, comparison or reply. Samsung watches may ask which voice app to use |
| Read aloud | Spoken summary, if the watch has a speech engine |
| Remind me | Notification about 1 hour before, with a fresh forecast for that place and those hours |
| Tile | Swipe from the watch face for AQI and the next window |
| Complication | AQI on your watch face, as text or a gauge |
| Offline | Saved forecasts appear instantly and stay usable for 6 hours. After that the tile and complication show no data |

Free-form language, general questions and venue lookups happen on the agent, so they need the agent's server keys. In the watch's offline fallback, requests use a port of the keyless English parser.

## Station readings

Forecast windows always come from the model. Only the current reading can use a station.

Get a free token at [aqicn.org/data-platform/token](https://aqicn.org/data-platform/token/), then add it to `watch/local.properties`, which git ignores:

```properties
WAQI_TOKEN=your-token-here
```

Without a token the app works on model data and says so under **About this data**.

The token is compiled into the APK, which is fine for a personal sideload. Before publishing on Google Play, move the station lookup behind your own server, because anyone can extract a token from an APK.

## Connecting to the agent

Set the agent's address in `watch/local.properties`:

```properties
AGENT_URL=https://your-agent-host
```

Use HTTPS for anything beyond local testing. For a watch on your desk, run the web service on this PC and forward its port over adb:

```bash
uv run delhi-air-web --port 8080
```

```bash
adb reverse tcp:8080 tcp:8080
```

Then set `AGENT_URL=http://127.0.0.1:8080`. Plain HTTP is allowed only for that address. The forward stops when adb disconnects, and Ask then falls back to the watch's own planner.

## The agent acts by itself

Every hour the background job asks the agent what you should do next, using your position, usual hours and favourite activities. If the agent has something worth saying, the watch notifies you with what, when, where and why. It also fills the For You card and the tile.

The watch learns from what you plan, when you ask, your step count and the suggestions you turn down. That history stays on the watch. It notifies you at most twice a day, with at least 3 hours between alerts, and never from 22:00 to 07:00. Turn it off with Plan > Agent suggestions.

## Build

Needs Android Studio's JDK and an Android SDK with platform 37.

```bash
./gradlew :app:testDebugUnitTest :app:assembleDebug
```

The APK is at `app/build/outputs/apk/debug/app-debug.apk`.

## Install on a real watch

1. On the watch, open **Settings > About watch > Software** and tap **Software version** 7 times.
2. In **Settings > Developer options**, turn on **ADB debugging** and **Wireless debugging**.
3. Put the watch and PC on the same Wi-Fi network.
4. In **Wireless debugging**, tap **Pair new device** and note the address and 6-digit code.

```bash
adb pair WATCH_IP:PAIRING_PORT
```

```bash
adb connect WATCH_IP:DEBUG_PORT
```

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

To add the tile, swipe to the end of your tiles and tap **Add tile**. To add the complication, long-press the watch face, tap **Edit**, and choose **Delhi AQI** for a slot.

## How it stays correct

The scoring, assessment wording, sentence parser, locality table and forecast parsing are Kotlin ports of the Python agent. `tools/gen_parity.py` runs the real Python code over hundreds of randomised cases, and `ParityTest` must reproduce every result.

After changing the Python logic:

```bash
.venv/Scripts/python watch/tools/gen_parity.py
```

Then rerun the Gradle tests from `watch/`. `tests/test_delhi.py` also fails if the Python and Kotlin locality tables drift apart.

## Limits

- Forecast air quality has the same 45 km model limit as the agent. Nearby localities often share a forecast.
- Station coverage depends on what is reporting. On 4 November 2026 the feed had 25 stations in the region, all in Delhi, so Noida, Gurugram, Ghaziabad and Faridabad show the model as the headline, with the nearest station listed as context.
- Forecasts rank places, but a nearby monitor can disagree. Comparisons show measured readings and say so when monitors contradict the ranking.
- The app is not medical advice. The best window can still be unhealthy.

Data: [Open-Meteo](https://open-meteo.com/), [CAMS](https://atmosphere.copernicus.eu/) and the [World Air Quality Index project](https://waqi.info/).
