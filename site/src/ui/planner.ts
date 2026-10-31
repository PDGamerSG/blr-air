import { aqiColor } from "../air/scoring";
import { openAgent } from "./agentLink";

interface Assessment {
  verdict?: string;
  aqi?: { meaning?: string; advice?: string };
  location?: { maps_url?: string; precision_note?: string };
  warnings?: string[];
  reasons?: string[];
  checklist?: string[];
}

interface WindowOption {
  start: string;
  end: string;
  us_aqi: number;
  pm2_5: number;
  rain_probability: number;
  temperature: number;
  max_aqi: number;
  score: number;
  apparent_temperature?: number | null;
  uv_index?: number | null;
  wind_speed?: number | null;
  daylight?: boolean | null;
  aqi_category: string;
  assessment?: Assessment;
}

interface Review {
  text?: string;
  rating?: number | null;
  author?: string;
  author_url?: string | null;
  author_photo_uri?: string | null;
  published_at?: string | null;
  relative_time?: string | null;
  google_maps_uri?: string | null;
}

interface Venue {
  status: string;
  message?: string;
  name?: string;
  address?: string;
  matched_name?: string;
  rating?: number | null;
  rating_count?: number | null;
  google_maps_uri?: string | null;
  website_uri?: string | null;
  business_status?: string | null;
  opening_hours?: string[];
  open_now?: boolean | null;
  accessibility?: Record<string, boolean | null>;
  reviews?: Review[];
  attributions?: { displayName?: string; uri?: string; name?: string; url?: string; provider?: string; provider_uri?: string }[];
  fetched_at?: string;
  candidates?: { name?: string; address?: string }[];
}

interface PlaceResult {
  status: string;
  place?: string;
  error?: string;
  summary?: string;
  mode?: string;
  location?: { name: string; latitude: number; longitude: number };
  timezone?: string;
  window?: WindowOption;
  backups?: WindowOption[];
  source?: string;
  fetched_at?: string;
  current?: { time: string; us_aqi: number; pm2_5: number; aqi_category: string } | null;
  request?: { activity?: string; hours?: number; day?: string; period?: string; daylight_only?: boolean; max_aqi?: number | null; max_rain?: number | null; max_temperature?: number | null; max_uv?: number | null; max_wind?: number | null };
  assessment?: Assessment;
  venue?: Venue | null;
}

interface Plan extends PlaceResult {
  plan_id: string;
  expires_at: string;
  places?: PlaceResult[];
  tied_places?: string[];
  partial?: boolean;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className = "", text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function safeExternalUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

/** A bounded mono recording becomes a real PCM16 WAV, not a renamed browser codec. */
export function encodePcmWav(chunks: Float32Array[], sampleRate: number): Blob {
  const frames = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (!Number.isInteger(sampleRate) || sampleRate < 8000 || sampleRate > 48000 || frames <= 0 || frames > sampleRate * 30) {
    throw new Error("Record between a moment and 30 seconds of audio at 8–48 kHz.");
  }
  const buffer = new ArrayBuffer(44 + frames * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => { [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0))); };
  write(0, "RIFF"); view.setUint32(4, 36 + frames * 2, true); write(8, "WAVE");
  write(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, "data"); view.setUint32(40, frames * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const value of chunk) {
    const sample = Number.isFinite(value) ? Math.min(1, Math.max(-1, value)) : 0;
    view.setInt16(offset, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function link(text: string, value: unknown): HTMLAnchorElement | HTMLSpanElement {
  const url = safeExternalUrl(value);
  if (!url) return el("span", "", text);
  const a = el("a", "", text);
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
}

function list(title: string, values?: string[], className = "") {
  const box = el("div", className);
  if (!values?.length) return box;
  box.append(el("h5", "", title));
  const ul = el("ul");
  values.forEach((text) => ul.append(el("li", "", text)));
  box.append(ul);
  return box;
}

function timeLabel(value: string, timezone?: string, includeDate = true): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone ?? "UTC", hourCycle: "h23", hour: "2-digit", minute: "2-digit",
      ...(includeDate ? { weekday: "short", day: "numeric", month: "short" } as const : {}),
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function number(value: number | null | undefined, suffix = "", decimals = 1): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(decimals)}${suffix}` : "Unavailable";
}

function renderVenue(venue: Venue): HTMLElement {
  const section = el("section", "planner__venue");
  section.append(el("h5", "", "Venue ratings and customer reviews"));
  if (venue.status !== "ok") {
    section.append(el("p", "planner__notice", venue.message || "Venue information is unavailable. Outdoor forecasts remain independent of customer ratings."));
    return section;
  }
  section.append(el("p", "planner__attribution", "Google Maps"));
  section.append(el("p", "", `Matched venue: ${venue.matched_name || venue.name || "Unknown"}`));
  if (venue.address) section.append(el("p", "planner__hint", venue.address));
  section.append(el("p", "planner__rating", venue.rating == null
    ? "No customer rating supplied."
    : `${number(venue.rating, "", 1)} / 5 · ${venue.rating_count == null ? "Review count unavailable" : `${venue.rating_count.toLocaleString()} ratings`}`));
  if (venue.business_status) section.append(el("p", "", `Venue status: ${venue.business_status.toLowerCase().replaceAll("_", " ")}.`));
  if (typeof venue.open_now === "boolean") section.append(el("p", "", `Reported ${venue.open_now ? "open" : "closed"} now. This does not establish availability during your forecast window.`));
  if (venue.opening_hours?.length) section.append(list("Provider opening hours", venue.opening_hours));
  const accessibility = Object.entries(venue.accessibility ?? {})
    .filter(([, value]) => typeof value === "boolean")
    .map(([key, value]) => `${key.replace(/([A-Z])/g, " $1").replaceAll("_", " ")}: ${value ? "reported available" : "reported unavailable"}`);
  if (accessibility.length) section.append(list("Accessibility reported by provider", accessibility));
  const venueLinks = el("p", "planner__links");
  if (venue.google_maps_uri) venueLinks.append(link("View venue on Google Maps", venue.google_maps_uri));
  if (venue.website_uri) venueLinks.append(link("Venue website", venue.website_uri));
  section.append(venueLinks);
  for (const attribution of venue.attributions ?? []) {
    const line = el("p", "planner__hint");
    line.append(link(attribution.provider || attribution.displayName || attribution.name || "Data attribution", attribution.provider_uri || attribution.uri || attribution.url));
    section.append(line);
  }
  if (venue.candidates && venue.candidates.length > 1) {
    section.append(el("p", "planner__notice", "More than one venue matched. Check the name and address; add a city or exact venue name if this is not the place you intended."));
  }
  section.append(el("p", "planner__hint", "Up to five customer reviews, ranked by relevance by Google Maps. This sample does not represent every visitor and does not determine the air-quality recommendation."));
  const reviews = el("div", "planner__reviews");
  for (const review of venue.reviews ?? []) {
    const article = el("article", "planner__review");
    const byline = el("div", "planner__review-author");
    const photo = safeExternalUrl(review.author_photo_uri);
    if (photo) {
      const img = el("img");
      img.src = photo;
      img.alt = "";
      img.width = img.height = 32;
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      byline.append(img);
    }
    byline.append(link(review.author || "Google Maps reviewer", review.author_url));
    article.append(byline);
    const meta = [review.rating == null ? null : `${review.rating}/5`, review.relative_time || review.published_at].filter(Boolean);
    if (meta.length) article.append(el("p", "planner__hint", meta.join(" · ")));
    if (review.text) article.append(el("blockquote", "", review.text));
    else article.append(el("p", "planner__hint", "Rating only; no review text supplied."));
    if (review.google_maps_uri) article.append(link("Read review on Google Maps", review.google_maps_uri));
    reviews.append(article);
  }
  if (!reviews.childElementCount) reviews.append(el("p", "planner__hint", "No customer-review text was supplied for this match."));
  section.append(reviews);
  if (venue.fetched_at) section.append(el("p", "planner__hint", `Venue data retrieved ${timeLabel(venue.fetched_at, "UTC")} UTC.`));
  return section;
}

function renderScoreChart(places: PlaceResult[]): HTMLElement {
  const figure = el("figure", "planner__scores");
  figure.append(el("figcaption", "", "Forecast preference score · lower is better"));
  const available = places.filter((p) => p.window && p.status === "ok");
  const max = Math.max(1, ...available.map((p) => p.window!.score));
  const rows = el("div", "planner__score-bars");
  for (const p of available) {
    const w = p.window!;
    const row = el("div", "planner__score-row");
    row.append(el("span", "planner__score-name", p.location?.name || p.place || "Place"));
    const track = el("div", "planner__score-track");
    const fill = el("span", "planner__score-fill");
    fill.style.width = `${Math.max(0, Math.min(100, w.score / max * 100))}%`;
    fill.style.background = aqiColor(w.max_aqi);
    track.append(fill);
    track.setAttribute("aria-hidden", "true");
    row.append(track, el("span", "", number(w.score)));
    rows.append(row);
  }
  figure.append(rows, el("p", "planner__hint", "Each place is compared at its own best eligible time. This combines air pollution, rain and heat; it is not a customer rating or medical risk score."));
  return figure;
}

// Resolves once /api/status answers, so callers can fall back to ASI:One when the
// planning server isn't reachable (e.g. a static deploy without a backend).
export function initPlanner(): { ready: Promise<boolean> } {
  const root = document.querySelector<HTMLElement>("#planner");
  if (!root) return { ready: Promise.resolve(false) };
  const find = <T extends Element>(selector: string) => root.querySelector<T>(selector)!;
  const form = find<HTMLFormElement>("[data-planner-form]");
  const query = find<HTMLTextAreaElement>("#planner-query");
  const includeVenue = find<HTMLInputElement>("input[name=include_venue]");
  const venueQuery = find<HTMLInputElement>("#planner-venue");
  const upload = find<HTMLInputElement>("#planner-audio");
  const record = find<HTMLButtonElement>("[data-plan-record]");
  const submit = find<HTMLButtonElement>("[data-plan-submit]");
  const cancel = find<HTMLButtonElement>("[data-plan-cancel]");
  const capabilities = find<HTMLElement>("[data-planner-capabilities]");
  const status = find<HTMLElement>("[data-plan-status]");
  const output = find<HTMLElement>("[data-plan-results]");
  const audio = find<HTMLAudioElement>("[data-plan-audio]");
  let voiceEnabled = false;
  let plannerOnline = false;
  let controller: AbortController | null = null;
  let audioUrl: string | null = null;
  let requestNumber = 0;
  let expiryTimer = 0;
  let captureNumber = 0;
  let capturePending = false;
  let stopRecording: ((send: boolean) => void) | null = null;
  let captureCleanup: (() => void) | null = null;

  function setStatus(message: string, error = false) {
    status.textContent = message;
    status.classList.toggle("is-error", error);
    status.setAttribute("role", error ? "alert" : "status");
  }

  function clearAudio() {
    audio.pause();
    audio.removeAttribute("src");
    audio.hidden = true;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioUrl = null;
  }

  function setBusy(busy: boolean) {
    root!.setAttribute("aria-busy", String(busy));
    root!.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLTextAreaElement>("button, input, textarea").forEach((control) => {
      if (control === cancel) return;
      control.disabled = busy || control.dataset.disabled === "true" || (control === upload && !voiceEnabled) || (control === record && (!voiceEnabled || !navigator.mediaDevices?.getUserMedia));
    });
    cancel.hidden = !busy;
    submit.textContent = busy ? "Working on your request…" : plannerOnline ? "Find my plan" : "Ask on ASI:One ↗";
  }

  async function responseError(response: Response): Promise<Error> {
    try {
      const body = await response.json();
      if (typeof body.error === "string") return new Error(body.error);
      if (typeof body.message === "string") return new Error(body.message);
      if (typeof body.summary === "string") return new Error(body.summary);
    } catch { /* A reverse proxy can return a non-JSON error. */ }
    return new Error(response.status === 429 ? "The agent is busy. Please wait a moment and retry." : `The planning service could not complete that request (HTTP ${response.status}). Please retry.`);
  }

  async function run<T>(work: (signal: AbortSignal) => Promise<T>, consume: (value: T) => void, message: string, timeout = 70000) {
    controller?.abort();
    controller = new AbortController();
    const active = controller;
    const ticket = ++requestNumber;
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; active.abort(); }, timeout);
    setBusy(true);
    setStatus(message);
    try {
      const value = await work(active.signal);
      if (ticket === requestNumber && !active.signal.aborted) consume(value);
    } catch (error) {
      if (ticket !== requestNumber) return;
      if (active.signal.aborted) setStatus(timedOut ? "That request timed out. Please retry." : "Request cancelled. You can edit your request and try again.", timedOut);
      else setStatus(error instanceof Error ? error.message : "The service could not be reached. Please retry.", true);
    } finally {
      window.clearTimeout(timer);
      if (ticket === requestNumber) {
        controller = null;
        setBusy(false);
      }
    }
  }

  function download(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = el("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  function renderPlace(plan: Plan, place: PlaceResult, placeIndex: number): HTMLElement {
    const article = el("article", "planner__place");
    article.append(el("h4", "", place.location?.name || place.place || "Your outdoor plan"));
    if (place.status !== "ok" || !place.window) {
      article.append(el("p", "planner__notice", place.error || place.summary || "This place could not be evaluated."));
      if (place.venue) article.append(renderVenue(place.venue));
      return article;
    }
    if (place.mode === "synthetic-demo") article.append(el("p", "planner__notice", "Synthetic demo data — do not use this plan for outdoor decisions."));
    if (place.current) {
      article.append(el("p", "planner__current", `Current model: US AQI ${number(place.current.us_aqi, "", 0)} (${place.current.aqi_category}), PM2.5 ${number(place.current.pm2_5, " µg/m³")}. Model time ${timeLabel(place.current.time, place.timezone)}.`));
    } else {
      article.append(el("p", "planner__hint", "Current air-quality reading unavailable. Forecast conditions are shown below."));
    }
    if (place.request) {
      const q = place.request;
      const interpreted = [`${q.hours ?? 1}-hour ${q.activity || "walk"}`, q.day === "next48" ? "next 48 hours" : q.day, q.period === "any" ? null : q.period];
      for (const [label, value, unit] of [["AQI", q.max_aqi, ""], ["rain", q.max_rain, "%"], ["feels like", q.max_temperature, "°C"], ["UV", q.max_uv, ""], ["wind", q.max_wind, " km/h"]] as const) {
        if (value != null) interpreted.push(`${label} ≤ ${value}${unit}`);
      }
      if (q.daylight_only) interpreted.push("daylight only");
      article.append(el("p", "planner__hint", `Interpreted request: ${interpreted.filter(Boolean).join(" · ")}.`));
    }
    const assessment = place.assessment;
    article.append(el("p", "planner__hint", `Times in ${place.timezone || "the resolved location's timezone"}. Select a window to see its conditions and save that exact time.`));
    const choices = [place.window, ...(place.backups ?? [])];
    const tabs = el("div", "planner__windows");
    tabs.setAttribute("role", "group");
    tabs.setAttribute("aria-label", `Choose a window for ${place.location?.name || place.place}`);
    const selectedPanel = el("div", "planner__selected");
    selectedPanel.setAttribute("aria-live", "polite");
    let selected = 0;
    const buttons: HTMLButtonElement[] = [];
    function choose(index: number) {
      selected = index;
      clearAudio();
      const w = choices[index];
      buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(i === index)));
      selectedPanel.replaceChildren();
      selectedPanel.append(el("p", "planner__time", `${timeLabel(w.start, place.timezone)}–${timeLabel(w.end, place.timezone, false)}`));
      const selectedAssessment = w.assessment ?? (index === 0 ? assessment : undefined);
      if (selectedAssessment) {
        selectedPanel.append(el("p", "planner__verdict", selectedAssessment.verdict || "Outdoor assessment"));
        if (selectedAssessment.aqi?.meaning) selectedPanel.append(el("p", "", selectedAssessment.aqi.meaning));
        if (selectedAssessment.aqi?.advice) selectedPanel.append(el("p", "", selectedAssessment.aqi.advice));
        selectedPanel.append(list("Conditions to consider for this window", selectedAssessment.warnings, "planner__warnings"));
      }
      const stats = el("dl", "planner__stats");
      for (const [label, value] of [
        ["Average US AQI", number(w.us_aqi, "", 0)],
        ["Worst hourly AQI", `${number(w.max_aqi, "", 0)} · ${w.aqi_category}`],
        ["PM2.5 average", number(w.pm2_5, " µg/m³")],
        ["Peak rain chance", number(w.rain_probability, "%", 0)],
        ["Peak temperature", number(w.temperature, "°C")],
        ["Feels like up to", number(w.apparent_temperature, "°C")],
        ["Peak UV index", number(w.uv_index)],
        ["Wind up to", number(w.wind_speed, " km/h")],
        ["Whole window in daylight", w.daylight === true ? "Yes" : w.daylight === false ? "No" : "Unavailable"],
      ]) {
        const item = el("div");
        item.append(el("dt", "", label), el("dd", "", value));
        stats.append(item);
      }
      selectedPanel.append(stats);
      if (!selectedAssessment && w.max_aqi > 100) selectedPanel.append(el("p", "planner__notice", "Air pollution remains adverse in this window. Consider an indoor alternative, especially for sensitive people."));
      if (selectedAssessment?.reasons?.length || selectedAssessment?.checklist?.length) {
        const explanation = el("details", "planner__explanation");
        explanation.append(el("summary", "", "Why this window, and what to check before leaving"), list("Selection reasons", selectedAssessment.reasons), list("Before you go", selectedAssessment.checklist));
        selectedPanel.append(explanation);
      }
    }
    choices.forEach((w, i) => {
      const button = el("button", "chip", `${i === 0 ? "Best" : `Backup ${i}`} · ${timeLabel(w.start, place.timezone, false)}`);
      button.type = "button";
      button.setAttribute("aria-pressed", String(i === 0));
      button.addEventListener("click", () => choose(i));
      buttons.push(button);
      tabs.append(button);
    });
    article.append(tabs, selectedPanel);
    choose(0);
    const actions = el("div", "planner__actions");
    const calendar = el("button", "btn btn--small", "Save selected time");
    calendar.type = "button";
    calendar.dataset.planDownload = "true";
    calendar.addEventListener("click", () => {
      const windowIndex = selected;
      void run(async (signal) => {
        const response = await fetch(`/api/calendar/${encodeURIComponent(plan.plan_id)}?place_index=${placeIndex}&window_index=${windowIndex}`, { signal });
        if (!response.ok) throw await responseError(response);
        if (!response.headers.get("content-type")?.includes("text/calendar")) throw new Error("The server did not return a calendar file. Please refresh your plan.");
        return response.blob();
      }, (blob) => { download(blob, "blr-air-window.ics"); setStatus("Calendar downloaded for the selected window. Import it into your calendar and recheck conditions before leaving."); }, "Preparing your calendar…");
    });
    const speak = el("button", "btn btn--small btn--ghost", "Listen to selected plan");
    speak.type = "button";
    speak.dataset.planDownload = "true";
    speak.dataset.disabled = String(!voiceEnabled);
    speak.disabled = !voiceEnabled;
    if (!voiceEnabled) speak.title = "Voice is not configured on this server.";
    speak.addEventListener("click", () => {
      const windowIndex = selected;
      clearAudio();
      void run(async (signal) => {
        const response = await fetch("/api/speech", { method: "POST", signal, headers: { "content-type": "application/json" }, body: JSON.stringify({ plan_id: plan.plan_id, place_index: placeIndex, window_index: windowIndex }) });
        if (!response.ok) throw await responseError(response);
        if (!response.headers.get("content-type")?.includes("audio/")) throw new Error("The server did not return audio. Please retry.");
        return response.blob();
      }, (blob) => {
        audioUrl = URL.createObjectURL(blob);
        audio.src = audioUrl;
        audio.hidden = false;
        setStatus("Spoken answer ready for the selected window. Use the player below to listen.");
        void audio.play().catch(() => { /* Some browsers require a second explicit play gesture. */ });
      }, "Generating the spoken answer…");
    });
    actions.append(calendar, speak);
    const maps = assessment?.location?.maps_url || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${place.location!.latitude},${place.location!.longitude}`)}`;
    actions.append(link("Check location on Google Maps", maps));
    if (place.location) actions.append(link("Directions", `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${place.location.latitude},${place.location.longitude}`)}`));
    article.append(actions);
    if (assessment?.location?.precision_note) article.append(el("p", "planner__hint", assessment.location.precision_note));
    if (place.venue) article.append(renderVenue(place.venue));
    article.append(el("p", "planner__hint", `${place.source || "Forecast source unavailable"}. Retrieved ${place.fetched_at ? timeLabel(place.fetched_at, "UTC") + " UTC" : "at an unknown time"}.`));
    return article;
  }

  function render(plan: Plan) {
    if (!plan.plan_id || !plan.window && !Array.isArray(plan.places)) throw new Error("The service returned an incomplete plan. Please retry.");
    output.replaceChildren();
    const places = plan.places ?? [plan];
    if (plan.partial) output.append(el("p", "planner__notice", "Some places could not be evaluated. The recommendation covers available results only."));
    if (plan.tied_places?.length) output.append(el("p", "planner__notice", `Forecast score tie: ${plan.tied_places.join(", ")}. Input order breaks the tie; the model does not establish that the first place is cleaner.`));
    if (places.filter((p) => p.window).length > 1) output.append(renderScoreChart(places));
    places.forEach((place, index) => output.append(renderPlace(plan, place, index)));
    if (plan.summary) {
      const full = el("details", "planner__explanation");
      full.append(el("summary", "", "Full agent response"), el("pre", "planner__full", plan.summary));
      const copy = el("button", "chip", "Copy full response");
      copy.type = "button";
      copy.addEventListener("click", () => {
        if (!navigator.clipboard) { setStatus("Clipboard unavailable. Select the full response above to copy it.", true); return; }
        void navigator.clipboard.writeText(plan.summary!).then(() => setStatus("Agent response copied.")).catch(() => setStatus("Clipboard unavailable. Select the full response above to copy it.", true));
      });
      full.append(copy);
      output.append(full);
    }
    const refresh = el("button", "chip", "Recheck my request");
    refresh.type = "button";
    refresh.addEventListener("click", () => form.requestSubmit());
    output.append(refresh);
    const expiry = Date.parse(plan.expires_at);
    if (Number.isFinite(expiry)) {
      expiryTimer = window.setTimeout(() => {
        output.querySelectorAll<HTMLButtonElement>("[data-plan-download]").forEach((button) => { button.disabled = true; button.dataset.disabled = "true"; });
        clearAudio();
        setStatus("This plan's download session has expired. Submit again for a fresh forecast and new downloads.");
      }, Math.max(0, expiry - Date.now()));
    }
    setStatus("Your plan is ready. Check the matched location, conditions and backup windows below.");
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (!plannerOnline) {
      let prompt = query.value.trim();
      if (includeVenue.checked) {
        prompt += `\nInclude venue ratings, customer reviews and opening hours${venueQuery.value.trim() ? ` for ${venueQuery.value.trim()}` : ""}.`;
      }
      setStatus("Opening BLR Air Window on ASI:One…");
      void openAgent(prompt).then((message) => setStatus(message));
      return;
    }
    captureNumber++;
    capturePending = false;
    stopRecording?.(false);
    captureCleanup?.();
    captureCleanup = null;
    record.textContent = "Record a request";
    clearAudio();
    window.clearTimeout(expiryTimer);
    output.replaceChildren();
    const body = { query: query.value.trim(), include_venue: includeVenue.checked, ...(venueQuery.value.trim() ? { venue_query: venueQuery.value.trim() } : {}) };
    void run(async (signal) => {
      const response = await fetch("/api/plan", { method: "POST", signal, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) throw await responseError(response);
      return await response.json() as Plan;
    }, render, "Reading your request, checking locations and comparing live forecast windows…", 60000);
  });
  cancel.addEventListener("click", () => {
    if (capturePending || stopRecording) {
      captureNumber++;
      capturePending = false;
      stopRecording?.(false);
      captureCleanup?.();
      captureCleanup = null;
      record.textContent = "Record a request";
      setBusy(false);
      setStatus("Recording cancelled. No audio was sent.");
    } else controller?.abort();
  });
  root.querySelectorAll<HTMLButtonElement>("[data-plan-example]").forEach((button) => {
    button.addEventListener("click", () => {
      query.value = button.dataset.planExample || "";
      venueQuery.value = button.dataset.exampleVenue || "";
      includeVenue.checked = Boolean(button.dataset.exampleVenue);
      query.focus();
      form.requestSubmit();
    });
  });
  function transcribe(file: Blob) {
    clearAudio();
    window.clearTimeout(expiryTimer);
    output.replaceChildren();
    void run(async (signal) => {
      const response = await fetch("/api/transcribe", { method: "POST", signal, headers: { "content-type": "audio/wav" }, body: file });
      if (!response.ok) throw await responseError(response);
      const body = await response.json();
      if (typeof body.transcript !== "string" || !body.transcript.trim()) throw new Error("No speech was recognized. Try a clearer recording or type your request.");
      return body.transcript as string;
    }, (transcript) => {
      query.value = transcript;
      upload.value = "";
      setStatus("Transcript ready. Check the place and date, edit if needed, then choose Find my plan.");
      query.focus();
    }, "Transcribing your recording with Sarvam…");
  }

  upload.addEventListener("change", () => {
    const file = upload.files?.[0];
    if (!file) return;
    upload.value = "";
    if (!file.name.toLowerCase().endsWith(".wav") || file.size > 10 * 1024 * 1024 || file.size < 44) {
      setStatus("Choose a complete WAV recording up to 10 MiB and 30 seconds long.", true);
      return;
    }
    transcribe(file);
  });

  record.addEventListener("click", () => {
    if (stopRecording) { stopRecording(true); return; }
    if (capturePending || !voiceEnabled || !navigator.mediaDevices?.getUserMedia) return;
    const ticket = ++captureNumber;
    capturePending = true;
    clearAudio();
    window.clearTimeout(expiryTimer);
    output.replaceChildren();
    setBusy(true);
    setStatus("Allow microphone access to record your request. You can cancel before recording starts.");
    void (async () => {
      let stream: MediaStream | null = null;
      let context: AudioContext | null = null;
      let cleaned = false;
      const cleanup = () => {
        if (cleaned) return;
        cleaned = true;
        stream?.getTracks().forEach((track) => track.stop());
        if (context && context.state !== "closed") void context.close().catch(() => {});
      };
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true }, video: false });
        if (ticket !== captureNumber) { cleanup(); return; }
        captureCleanup = cleanup;
        context = new AudioContext({ sampleRate: 16000 });
        await context.resume();
        if (ticket !== captureNumber) { cleanup(); return; }
        if (context.sampleRate < 8000 || context.sampleRate > 48000) throw new Error("This microphone's sample rate is unsupported. Upload a PCM WAV or type your request.");
        const sampleRate = context.sampleRate;
        const source = context.createMediaStreamSource(stream);
        // ScriptProcessor keeps this small recorder compatible without an external worklet URL.
        const processor = context.createScriptProcessor(4096, 1, 1);
        const silent = context.createGain();
        silent.gain.value = 0;
        const chunks: Float32Array[] = [];
        let frames = 0;
        let stopped = false;
        const limit = sampleRate * 30;
        const timer = window.setTimeout(() => stopRecording?.(true), 30000);
        stopRecording = (send) => {
          if (stopped) return;
          stopped = true;
          window.clearTimeout(timer);
          processor.onaudioprocess = null;
          source.disconnect(); processor.disconnect(); silent.disconnect();
          cleanup();
          captureCleanup = null;
          stopRecording = null;
          capturePending = false;
          record.textContent = "Record a request";
          setBusy(false);
          if (send) {
            try { transcribe(encodePcmWav(chunks, sampleRate)); }
            catch (error) { setStatus(error instanceof Error ? error.message : "No audio was recorded.", true); }
          }
        };
        processor.onaudioprocess = (event) => {
          const input = event.inputBuffer.getChannelData(0);
          const length = Math.min(input.length, limit - frames);
          if (length > 0) { chunks.push(input.slice(0, length)); frames += length; }
          if (frames >= limit) stopRecording?.(true);
        };
        source.connect(processor); processor.connect(silent); silent.connect(context.destination);
        capturePending = false;
        record.disabled = false;
        record.textContent = "Stop and transcribe";
        setStatus("Recording now. Choose Stop and transcribe when finished, or Cancel request to discard. Maximum 30 seconds.");
      } catch (error) {
        cleanup();
        if (ticket !== captureNumber) return;
        captureCleanup = null;
        capturePending = false;
        setBusy(false);
        setStatus(error instanceof DOMException && error.name === "NotAllowedError" ? "Microphone permission was denied. Upload a WAV recording or type your request." : error instanceof Error ? error.message : "Microphone unavailable. Upload a WAV recording or type your request.", true);
      }
    })();
  });

  const healthController = new AbortController();
  const healthTimer = window.setTimeout(() => healthController.abort(), 8000);
  const ready = fetch("/api/status", { signal: healthController.signal })
    .then(async (response) => {
      if (!response.ok) throw new Error("Planning service unavailable");
      const body = await response.json();
      if (body.status !== "ok" || !body.features) throw new Error("Planning service unavailable");
      plannerOnline = true;
      voiceEnabled = Boolean(body.features.voice);
      upload.disabled = !voiceEnabled || controller !== null || capturePending || stopRecording !== null;
      record.disabled = !voiceEnabled || !navigator.mediaDevices?.getUserMedia || controller !== null;
      capabilities.textContent = `${body.features.language ? "Language understanding configured" : "English request parsing available"} · ${voiceEnabled ? "Voice configured" : "Voice unavailable"} · ${body.features.venues ? "Venue reviews checked per request" : "Venue reviews unavailable"}`;
      return true;
    })
    .catch(() => {
      capabilities.textContent = "Ask BLR Air Window on ASI:One. Your request will be copied so you can paste it into the agent's chat. The quick forecast scan below also works here.";
      submit.textContent = "Ask on ASI:One ↗";
      return false;
    })
    .finally(() => window.clearTimeout(healthTimer));

  window.addEventListener("pagehide", () => {
    captureNumber++;
    stopRecording?.(false);
    captureCleanup?.();
    controller?.abort();
    healthController.abort();
    window.clearTimeout(expiryTimer);
    clearAudio();
  });
  return { ready };
}
