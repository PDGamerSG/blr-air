// Browser port of blr_air/scoring.py. Keep the rules identical so the page never
// promises something the agent would answer differently.

export type Activity = "run" | "cycle" | "walk" | "commute" | "kids";
export type Day = "next48" | "today" | "tomorrow";
export type Period = "any" | "morning" | "afternoon" | "evening";

export interface Hour {
  t: number; // unix seconds, start of the hour
  aqi: number;
  pm: number;
  rain: number;
  temp: number;
}

export interface Request {
  hours: 1 | 2;
  activity: Activity;
  day: Day;
  period: Period;
}

export interface Window {
  start: number;
  end: number;
  aqi: number;
  pm: number;
  rain: number;
  temp: number;
  maxAqi: number;
  score: number;
  hours: Hour[];
}

const HOUR = 3600;
export const HORIZON = 48 * HOUR;

export const PERIODS: Record<Period, [number, number]> = {
  any: [5, 21],
  morning: [5, 12],
  afternoon: [12, 17],
  evening: [17, 21],
};

export function aqiCategory(aqi: number): string {
  for (const [ceiling, name] of [
    [50, "Good"],
    [100, "Moderate"],
    [150, "Unhealthy for sensitive groups"],
    [200, "Unhealthy"],
    [300, "Very unhealthy"],
  ] as const) {
    if (aqi <= ceiling) return name;
  }
  return "Hazardous";
}

export function aqiColor(aqi: number): string {
  if (aqi <= 50) return "#7cff5b";
  if (aqi <= 100) return "#ffe62b";
  if (aqi <= 150) return "#ff6a2a";
  if (aqi <= 200) return "#e20b1b";
  if (aqi <= 300) return "#a14bd8";
  return "#7a0510";
}

// A preference heuristic, not a health/exposure model. Lower is better.
export function hourlyCost(h: Hour): number {
  return h.aqi + 0.5 * h.pm + 1.5 * h.rain + 5 * Math.max(0, h.temp - 30);
}

export interface LocalTime {
  date: string; // YYYY-MM-DD in the location's timezone
  hour: number;
  minute: number;
}

const formatters = new Map<string, Intl.DateTimeFormat>();

export function localTime(t: number, timezone: string): LocalTime {
  let fmt = formatters.get(timezone);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
    formatters.set(timezone, fmt);
  }
  const parts = Object.fromEntries(fmt.formatToParts(new Date(t * 1000)).map((p) => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) % 24, minute: Number(parts.minute) };
}

function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function targetDay(day: Day, now: number, timezone: string): string | null {
  if (day === "next48") return null;
  const today = localTime(now, timezone).date;
  return day === "today" ? today : addDays(today, 1);
}

// Whether a single hour could belong to an eligible window; used to shade the chart.
export function hourEligible(h: Hour, req: Request, timezone: string, now: number): boolean {
  const [startHour, endHour] = PERIODS[req.period];
  if (h.t < now || h.t + HOUR > now + HORIZON) return false;
  const local = localTime(h.t, timezone);
  if (local.hour < startHour || local.hour >= endHour) return false;
  const day = targetDay(req.day, now, timezone);
  return !day || local.date === day;
}

export function selectWindow(rows: Hour[], req: Request, timezone: string, now: number): Window | null {
  const [startHour, endHour] = PERIODS[req.period];
  const day = targetDay(req.day, now, timezone);
  const ordered = [...new Map(rows.map((r) => [r.t, r])).values()].sort((a, b) => a.t - b.t);
  let best: { score: number; start: number; block: Hour[] } | null = null;
  for (let i = 0; i + req.hours <= ordered.length; i++) {
    const block = ordered.slice(i, i + req.hours);
    const end = block[block.length - 1].t + HOUR;
    if (block[0].t < now || end > now + HORIZON) continue;
    if (block.some((b, j) => j > 0 && b.t - block[j - 1].t !== HOUR)) continue;
    const local = block.map((b) => localTime(b.t, timezone));
    if (local.some((l) => l.hour < startHour || l.hour >= endHour)) continue;
    const localEnd = localTime(end, timezone);
    if (localEnd.date !== local[0].date || localEnd.hour * 60 + localEnd.minute > endHour * 60) continue;
    if (day && local.some((l) => l.date !== day)) continue;
    const score = block.reduce((sum, b) => sum + hourlyCost(b), 0) / block.length;
    if (!best || score < best.score || (score === best.score && block[0].t < best.start)) {
      best = { score, start: block[0].t, block };
    }
  }
  if (!best) return null;
  const b = best.block;
  const mean = (f: (h: Hour) => number) => b.reduce((s, h) => s + f(h), 0) / b.length;
  return {
    start: b[0].t,
    end: b[b.length - 1].t + HOUR,
    aqi: mean((h) => h.aqi),
    pm: mean((h) => h.pm),
    rain: Math.max(...b.map((h) => h.rain)),
    temp: Math.max(...b.map((h) => h.temp)),
    maxAqi: Math.max(...b.map((h) => h.aqi)),
    score: best.score,
    hours: b,
  };
}
