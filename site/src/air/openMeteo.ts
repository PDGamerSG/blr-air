// Keyless Open-Meteo calls straight from the browser (CORS is open), mirroring
// blr_air/providers.py: same endpoints, same fields, same validation rules.
import type { Hour } from "./scoring";

const AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality";
const WEATHER_URL = "https://api.open-meteo.com/v1/forecast";
const GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";

export const SOURCE = "Open-Meteo Air Quality (CAMS) and Weather Forecast";

export interface Place {
  name: string;
  lat: number;
  lon: number;
  timezone?: string;
}

export interface Forecast {
  place: Place;
  hours: Hour[];
  current: { t: number; aqi: number; pm: number } | null;
  timezone: string;
  fetchedAt: Date;
  demo: boolean;
}

type Json = Record<string, unknown>;

function isNum(v: unknown, min = 0, max = 10000): v is number {
  return typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
}

async function getJson(url: string, params: Record<string, string | number>): Promise<unknown> {
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  for (let attempt = 0; attempt < 3; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);
    try {
      const res = await fetch(`${url}?${query}`, { signal: ctrl.signal });
      if (res.ok) {
        const data = await res.json();
        if (data && typeof data === "object" && !(data as Json).error) return data;
        break;
      }
      if (![429, 500, 502, 503, 504].includes(res.status)) break;
    } catch {
      // Network failure or timeout: fall through to retry.
    } finally {
      clearTimeout(timer);
    }
    await new Promise((r) => setTimeout(r, 250 * (attempt + 1)));
  }
  throw new Error("Open-Meteo is unavailable or rate-limited. Please try again in a minute.");
}

function hourlyMap(payload: Json, fields: string[]): Map<number, number[]> {
  const hourly = payload.hourly as Record<string, unknown[]>;
  const times = hourly.time;
  if (!Array.isArray(times) || fields.some((f) => !Array.isArray(hourly[f]) || hourly[f].length !== times.length)) {
    throw new Error("Invalid hourly arrays");
  }
  const out = new Map<number, number[]>();
  times.forEach((t, i) => {
    if (isNum(t, 0, 4102444800)) out.set(t, fields.map((f) => hourly[f][i] as number));
  });
  return out;
}

export async function fetchForecast(place: Place): Promise<Forecast> {
  const common = {
    latitude: place.lat,
    longitude: place.lon,
    forecast_days: 4,
    timezone: "auto",
    timeformat: "unixtime",
  };
  const [aq, wx] = (await Promise.all([
    getJson(AIR_URL, { ...common, current: "us_aqi,pm2_5", hourly: "us_aqi,pm2_5" }),
    getJson(WEATHER_URL, { ...common, hourly: "precipitation_probability,temperature_2m" }),
  ])) as [Json, Json];
  const timezone = String(wx.timezone ?? "");
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone });
  } catch {
    throw new Error("Open-Meteo returned an unknown timezone.");
  }
  const air = hourlyMap(aq, ["us_aqi", "pm2_5"]);
  const weather = hourlyMap(wx, ["precipitation_probability", "temperature_2m"]);
  const hours: Hour[] = [];
  // Missing values exclude the hour; they are never treated as clean air.
  for (const [t, [aqi, pm]] of [...air.entries()].sort((a, b) => a[0] - b[0])) {
    const w = weather.get(t);
    if (!w) continue;
    const [rain, temp] = w;
    if (isNum(aqi) && isNum(pm) && isNum(rain, 0, 100) && isNum(temp, -100, 70)) {
      hours.push({ t, aqi, pm, rain, temp });
    }
  }
  if (!hours.length) throw new Error("Open-Meteo returned incomplete forecast data. Please try again shortly.");
  const raw = (aq.current ?? {}) as Json;
  const current =
    isNum(raw.time, 0, 4102444800) && isNum(raw.us_aqi) && isNum(raw.pm2_5)
      ? { t: raw.time, aqi: raw.us_aqi, pm: raw.pm2_5 }
      : null;
  return { place, hours, current, timezone, fetchedAt: new Date(), demo: false };
}

// Current modelled AQI for many points in one request (used by the city map and ticker).
export async function fetchCurrentMany(places: { lat: number; lon: number }[]): Promise<({ aqi: number; pm: number } | null)[]> {
  const data = await getJson(AIR_URL, {
    latitude: places.map((p) => p.lat).join(","),
    longitude: places.map((p) => p.lon).join(","),
    current: "us_aqi,pm2_5",
    timezone: "auto",
    timeformat: "unixtime",
  });
  const list = (Array.isArray(data) ? data : [data]) as Json[];
  return places.map((_, i) => {
    const cur = (list[i]?.current ?? {}) as Json;
    return isNum(cur.us_aqi) && isNum(cur.pm2_5) ? { aqi: cur.us_aqi, pm: cur.pm2_5 } : null;
  });
}

export async function geocode(query: string): Promise<Place> {
  const parts = query.split(",").map((p) => p.trim()).filter(Boolean);
  if (!parts.length) throw new Error("Type a city, e.g. 'Paris, France'.");
  const data = (await getJson(GEOCODING_URL, { name: parts[0], count: 10, language: "en", format: "json" })) as Json;
  for (const hit of (data.results as Json[] | undefined) ?? []) {
    const qualifiers = new Set(["admin1", "admin2", "country", "country_code"].map((f) => String(hit[f] ?? "").toLowerCase()));
    if (parts.slice(1).some((p) => !qualifiers.has(p.toLowerCase()))) continue;
    if (!isNum(hit.latitude, -90, 90) || !isNum(hit.longitude, -180, 180)) continue;
    const name = [...new Set(["name", "admin1", "country"].map((k) => hit[k]).filter(Boolean).map(String))].join(", ");
    return { name, lat: hit.latitude, lon: hit.longitude, timezone: hit.timezone as string | undefined };
  }
  throw new Error(`Couldn't find '${query}'. Try 'city, country' or a Bengaluru locality.`);
}

// Clearly-labelled synthetic Bengaluru data, the same shape as blr_air/demo.py,
// used only when the live fetch fails so the scanner still demonstrates the rules.
export function demoForecast(place: Place): Forecast {
  const now = Date.now() / 1000;
  const ist = 19800;
  const start = Math.floor((now + ist) / 3600) * 3600 - ist;
  const hours: Hour[] = [];
  for (let i = 0; i < 72; i++) {
    const t = start + i * 3600;
    const h = new Date((t + ist) * 1000).getUTCHours();
    hours.push({
      t,
      aqi: 45 + Math.abs(h - 9) * 5,
      pm: 12 + Math.abs(h - 9),
      rain: h < 14 ? 10 : 65,
      temp: 24 + Math.max(0, 5 - Math.abs(h - 14)),
    });
  }
  return {
    place,
    hours,
    current: { t: start, aqi: hours[0].aqi, pm: hours[0].pm },
    timezone: "Asia/Kolkata",
    fetchedAt: new Date(),
    demo: true,
  };
}
