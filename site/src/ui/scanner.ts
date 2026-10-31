import gsap from "gsap";
import { AGENT_HANDLE, LOCALITIES } from "../config";
import { demoForecast, fetchForecast, geocode, SOURCE, type Forecast, type Place } from "../air/openMeteo";
import {
  aqiCategory,
  aqiColor,
  HORIZON,
  hourEligible,
  hourlyCost,
  selectWindow,
  type Activity,
  type Day,
  type Period,
  type Request,
  type Window,
} from "../air/scoring";

const VERBS: Record<Activity, string> = {
  run: "run",
  cycle: "cycle",
  walk: "walk",
  commute: "commute",
  kids: "take kids outside",
};

const $ = <T extends Element>(sel: string, root: ParentNode = document) => root.querySelector<T>(sel)!;

function fmt(t: number, tz: string, opts: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: tz, hourCycle: "h23", ...opts }).format(new Date(t * 1000));
}

function offset(t: number, tz: string) {
  const name = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "longOffset" })
    .formatToParts(new Date(t * 1000))
    .find((p) => p.type === "timeZoneName")?.value;
  const m = name?.match(/GMT([+-])(\d{2}):(\d{2})/);
  return m ? `${m[1]}${m[2]}${m[3]}` : "+0000";
}

const hm = (t: number, tz: string) => fmt(t, tz, { hour: "2-digit", minute: "2-digit" });

// Mirrors blr_air/service.py describe() so the in-page verdict reads like the agent.
function describe(f: Forecast, w: Window, req: Request) {
  const tz = f.timezone;
  const lines = [`${f.place.name} · ${tz}`];
  if (f.demo) lines.unshift("OFFLINE DEMO — synthetic data; do not use for outdoor decisions.");
  if (f.current) {
    const when = fmt(f.current.t, tz, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    const stale = f.fetchedAt.getTime() / 1000 - f.current.t > 3 * 3600 ? " (older model estimate)" : "";
    lines.push(
      `Current model at ${when}${stale}: US AQI ${f.current.aqi.toFixed(0)} (${aqiCategory(f.current.aqi)}), PM2.5 ${f.current.pm.toFixed(1)} µg/m³.`,
    );
  } else {
    lines.push("Current air-quality estimate unavailable; hourly forecast shown below.");
  }
  const day = fmt(w.start, tz, { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).replace(",", "");
  lines.push(
    `Best available ${req.hours}-hour window to ${VERBS[req.activity]}: ${day}, ${hm(w.start, tz)}–${hm(w.end, tz)} (${offset(w.start, tz)}).`,
    `Average US AQI ${w.aqi.toFixed(0)}; PM2.5 ${w.pm.toFixed(1)} µg/m³. Peak hourly rain chance ${w.rain.toFixed(0)}%; temperature up to ${w.temp.toFixed(1)}°C.`,
    `Worst hourly AQI: ${w.maxAqi.toFixed(0)} (${aqiCategory(w.maxAqi)}).`,
    "Ranked by air pollution, rain and heat among complete windows between 05:00–21:00 local.",
  );
  if (w.maxAqi > 100)
    lines.push("This is the least-bad available slot; consider an indoor alternative, especially for children or people sensitive to air pollution.");
  if (w.temp >= 35) lines.push("Significant heat is forecast even in this slot; consider an indoor activity.");
  if (w.rain >= 70) lines.push("Rain is still likely in this slot; keep an indoor alternative.");
  const fetched = f.fetchedAt.toLocaleString("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).replace(",", "");
  lines.push(
    `Data: ${f.demo ? "Synthetic offline demo" : SOURCE}. Retrieved ${fetched} UTC.`,
    "Model forecasts, not CPCB station readings or medical advice.",
  );
  return lines.join("\n");
}

export function promptFor(place: string, req: Request) {
  const when = req.day === "next48" ? (req.period === "any" ? "" : ` this ${req.period}`) : ` ${req.day}${req.period === "any" ? "" : ` ${req.period}`}`;
  return `${AGENT_HANDLE} best ${req.hours}-hour window to ${VERBS[req.activity]} in ${place}${when}`;
}

export interface ScannerHooks {
  onResult: (color: string | null) => void;
  onAsk: (prompt: string) => void;
  onCopy: (prompt: string) => void;
}

export function initScanner(hooks: ScannerHooks) {
  const form = $<HTMLFormElement>(".scanner__controls");
  const select = $<HTMLSelectElement>("select", form);
  const cityInput = $<HTMLInputElement>("input[name=city]", form);
  const go = $<HTMLButtonElement>(".scanner__go", form);
  const chart = $<HTMLElement>(".chart");
  const bars = $<HTMLElement>(".chart__bars");
  const beam = $<HTMLElement>(".chart__beam");
  const scroll = $<HTMLElement>(".chart__scroll");
  const tip = $<HTMLElement>(".chart__tip");
  const status = $<HTMLElement>(".chart__status");
  const statusText = $<HTMLElement>(".chart__status-text");
  const placeLabel = $<HTMLElement>(".chart__place");
  const result = $<HTMLElement>(".result");
  const windowText = $<HTMLElement>(".result__window", result);
  const stats = $<HTMLElement>(".result__stats", result);
  const text = $<HTMLElement>(".result__text", result);
  const ask = $<HTMLButtonElement>("[data-ask]", result);
  const copy = $<HTMLButtonElement>("[data-copy-prompt]", result);

  const req: Request = { hours: 1, activity: "walk", day: "next48", period: "any" };
  let place: Place = { ...LOCALITIES[0] };
  let custom: Place | null = null;
  let prompt = "";
  let busy = false;

  for (const l of LOCALITIES) {
    const o = document.createElement("option");
    o.value = l.name;
    o.textContent = l.name === "Bengaluru" ? "Bengaluru (city centre)" : `${l.name}, Bengaluru`;
    select.append(o);
  }
  select.addEventListener("change", () => {
    custom = null;
    cityInput.value = "";
    const l = LOCALITIES.find((x) => x.name === select.value)!;
    place = { ...l };
  });

  form.querySelectorAll<HTMLElement>(".chips[data-group]").forEach((group) => {
    group.addEventListener("click", (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLButtonElement>(".chip");
      if (!btn) return;
      group.querySelectorAll(".chip").forEach((c) => c.classList.toggle("is-on", c === btn));
      const v = btn.dataset.value!;
      switch (group.dataset.group) {
        case "activity":
          req.activity = v as Activity;
          break;
        case "hours":
          req.hours = Number(v) as 1 | 2;
          break;
        case "day":
          req.day = v as Day;
          break;
        case "period":
          req.period = v as Period;
          break;
      }
    });
  });

  async function resolveCity() {
    const q = cityInput.value.trim();
    if (!q) {
      // Cleared the city box: fall back to the selected locality.
      if (custom) {
        custom = null;
        place = { ...LOCALITIES.find((x) => x.name === select.value)! };
      }
      return true;
    }
    if (custom && cityInput.dataset.resolved === q) return true;
    try {
      setStatus("Finding that place…", "");
      custom = await geocode(q);
      cityInput.dataset.resolved = q;
      place = custom;
      return true;
    } catch (err) {
      setStatus((err as Error).message, "is-demo");
      return false;
    }
  }

  $<HTMLButtonElement>("[data-geocode]", form).addEventListener("click", async () => {
    if (await resolveCity()) placeLabel.textContent = place.name;
  });
  cityInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  function setStatus(msg: string, cls: "is-live" | "is-demo" | "") {
    status.className = `chart__status ${cls}`;
    statusText.textContent = msg;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (busy) return;
    busy = true;
    go.classList.add("is-busy");
    go.querySelector("span")!.textContent = "Scanning…";
    try {
      if (!(await resolveCity())) return;
      placeLabel.textContent = custom ? place.name : `${place.name}${place.name === "Bengaluru" ? "" : ", Bengaluru"}`;
      setStatus("Contacting Open-Meteo…", "");
      let forecast: Forecast;
      try {
        forecast = await fetchForecast({ ...place, name: placeLabel.textContent! });
        setStatus(`Live · fetched ${forecast.fetchedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`, "is-live");
      } catch (err) {
        if (custom) throw err;
        forecast = demoForecast({ ...place, name: placeLabel.textContent! });
        setStatus("Offline demo · synthetic data, not a forecast", "is-demo");
      }
      render(forecast);
    } catch (err) {
      setStatus((err as Error).message, "is-demo");
      windowText.textContent = "Couldn't reach the sky.";
      text.textContent = (err as Error).message;
    } finally {
      busy = false;
      go.classList.remove("is-busy");
      go.querySelector("span")!.textContent = "Scan again";
    }
  });

  function render(f: Forecast) {
    const now = Date.now() / 1000;
    const tz = f.timezone;
    const shown = f.hours.filter((h) => h.t + 3600 > now && h.t < now + HORIZON);
    const w = selectWindow(f.hours, req, tz, now);
    const best = new Set(w?.hours.map((h) => h.t));
    const maxCost = Math.max(80, ...shown.map(hourlyCost));
    bars.replaceChildren();
    let lastDate = "";
    for (const h of shown) {
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.setAttribute("role", "listitem");
      const eligible = hourEligible(h, req, tz, now);
      if (!eligible) bar.classList.add("is-off");
      if (best.has(h.t)) bar.classList.add("is-best");
      bar.style.setProperty("--c", aqiColor(h.aqi));
      bar.style.setProperty("--h", `${Math.max(3, (hourlyCost(h) / maxCost) * 100)}%`);
      bar.style.setProperty("--rain", String(Math.min(1, h.rain / 60)));
      const date = fmt(h.t, tz, { weekday: "short", day: "2-digit" });
      const hour = fmt(h.t, tz, { hour: "2-digit" });
      bar.innerHTML = `<span class="bar__rain"></span><span class="bar__fill"></span>`;
      if (date !== lastDate) {
        bar.insertAdjacentHTML("beforeend", `<span class="bar__day">${date.toUpperCase()}</span>`);
        lastDate = date;
      } else if (Number(hour) % 6 === 0) {
        bar.insertAdjacentHTML("beforeend", `<span class="bar__label">${hour}</span>`);
      }
      bar.setAttribute(
        "aria-label",
        `${date} ${hour}:00, AQI ${h.aqi.toFixed(0)}, PM2.5 ${h.pm.toFixed(1)}, rain ${h.rain.toFixed(0)}%, ${h.temp.toFixed(1)}°C${eligible ? "" : ", outside your hours"}`,
      );
      bar.dataset.tip = `<b>${date} · ${hour}:00</b>US AQI ${h.aqi.toFixed(0)} · ${aqiCategory(h.aqi)}<br>PM2.5 ${h.pm.toFixed(1)} µg/m³<br>Rain ${h.rain.toFixed(0)}% · ${h.temp.toFixed(1)}°C<br>cost ${hourlyCost(h).toFixed(0)}${eligible ? "" : "<br><i>outside your hours</i>"}`;
      bars.append(bar);
    }

    const fills = bars.querySelectorAll(".bar__fill");
    gsap.fromTo(fills, { scaleY: 0 }, { scaleY: 1, duration: 0.7, ease: "back.out(1.6)", stagger: 0.012 });

    const bestBars = [...bars.querySelectorAll<HTMLElement>(".bar.is-best")];
    gsap.killTweensOf(beam);
    if (w && bestBars.length) {
      const first = bestBars[0];
      const last = bestBars[bestBars.length - 1];
      const left = first.offsetLeft - 4;
      const width = last.offsetLeft + last.offsetWidth - first.offsetLeft + 8;
      const tl = gsap.timeline();
      tl.set(beam, { opacity: 1, left: 0, width: 26 })
        .to(beam, { left: bars.scrollWidth - 26, duration: 0.9, ease: "power1.inOut" })
        .to(beam, { left, width, duration: 0.7, ease: "back.out(1.4)" });
      scroll.scrollTo({ left: Math.max(0, left - 60), behavior: "smooth" });
    } else {
      gsap.to(beam, { opacity: 0, duration: 0.3 });
    }

    if (!w) {
      windowText.textContent = "No window fits.";
      stats.replaceChildren();
      text.textContent =
        "No complete outdoor window matches this request in the next 48 hours. Try 1 hour, another part of the day, or try again when forecasts update.";
      hooks.onResult(null);
    } else {
      const day = fmt(w.start, tz, { weekday: "short", day: "2-digit", month: "short" });
      windowText.innerHTML = `${day} · ${hm(w.start, tz)}–${hm(w.end, tz)}`;
      stats.innerHTML = [
        ["Avg US AQI", w.aqi.toFixed(0), aqiColor(w.aqi), aqiCategory(w.aqi)],
        ["PM2.5", w.pm.toFixed(1), "", "µg/m³"],
        ["Rain peak", `${w.rain.toFixed(0)}%`, "#8be9ed", ""],
        ["Temp max", `${w.temp.toFixed(1)}°`, w.temp >= 30 ? "#ff6a2a" : "", "C"],
      ]
        .map(([k, v, c, sub]) => `<div><dt>${k}</dt><dd style="${c ? `--c:${c}` : ""}">${v} <small>${sub}</small></dd></div>`)
        .join("");
      text.textContent = describe(f, w, req);
      hooks.onResult(aqiColor(w.maxAqi));
    }
    prompt = promptFor(place.name, req);
    ask.disabled = copy.disabled = false;
  }

  ask.addEventListener("click", () => hooks.onAsk(prompt));
  copy.addEventListener("click", () => hooks.onCopy(prompt));

  // Tooltip follows the hovered bar.
  bars.addEventListener("pointermove", (e) => {
    const bar = (e.target as HTMLElement).closest<HTMLElement>(".bar");
    if (!bar?.dataset.tip) {
      tip.hidden = true;
      return;
    }
    tip.innerHTML = bar.dataset.tip;
    tip.hidden = false;
    const box = chart.getBoundingClientRect();
    const x = Math.min(box.width - tip.offsetWidth - 10, Math.max(10, e.clientX - box.left + 14));
    tip.style.left = `${x}px`;
    tip.style.top = `${e.clientY - box.top - tip.offsetHeight - 14}px`;
  });
  bars.addEventListener("pointerleave", () => (tip.hidden = true));

  return {
    setPlace(name: string) {
      const l = LOCALITIES.find((x) => x.name === name);
      if (!l) return;
      select.value = l.name;
      select.dispatchEvent(new Event("change"));
    },
    scan() {
      form.requestSubmit();
    },
  };
}
