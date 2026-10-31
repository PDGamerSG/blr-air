import gsap from "gsap";
import { LOCALITIES } from "../config";
import { fetchCurrentMany } from "../air/openMeteo";
import { aqiCategory, aqiColor } from "../air/scoring";

export interface LiveReading {
  name: string;
  aqi: number;
  pm: number;
}

// Beacons cover every locality except the "Bengaluru" city-centre alias.
export const MAP_LOCALITIES = LOCALITIES.filter((l) => l.name !== "Bengaluru");

export async function loadLive(): Promise<{ city: LiveReading | null; map: (LiveReading | null)[] }> {
  const values = await fetchCurrentMany(LOCALITIES);
  const byName = new Map(LOCALITIES.map((l, i) => [l.name, values[i]]));
  const read = (name: string): LiveReading | null => {
    const v = byName.get(name);
    return v ? { name, ...v } : null;
  };
  return { city: read("Bengaluru"), map: MAP_LOCALITIES.map((l) => read(l.name)) };
}

export function renderHeroLive(reading: LiveReading | null) {
  const el = document.querySelector<HTMLElement>(".hero__live")!;
  if (!reading) return;
  el.hidden = false;
  el.querySelector(".hero__aqi")!.textContent = reading.aqi.toFixed(0);
  const cat = el.querySelector<HTMLElement>(".hero__aqi-cat")!;
  cat.textContent = `${aqiCategory(reading.aqi)} · PM2.5 ${reading.pm.toFixed(1)}`;
  el.style.background = aqiColor(reading.aqi);
  gsap.from(el, { scale: 0.4, rotate: -20, opacity: 0, duration: 0.9, ease: "back.out(2)" });
}

export function initMarquee(track: HTMLElement) {
  const fill = (readings: (LiveReading | null)[] = []) => {
    const items = MAP_LOCALITIES.map((l, i) => {
      const r = readings[i];
      const badge = r ? `<b style="--c:${aqiColor(r.aqi)}">AQI ${r.aqi.toFixed(0)}</b>` : "";
      return `<span>${l.name}${badge}</span><i>✦</i>`;
    }).join("");
    // Two copies make the -50% loop seamless.
    track.innerHTML = `<div style="display:flex">${items}</div><div style="display:flex" aria-hidden="true">${items}</div>`;
  };
  fill();
  const tween = gsap.to(track, { xPercent: -50, duration: 60, ease: "none", repeat: -1 });
  return { fill, tween };
}

export function initCityBoard(
  list: HTMLOListElement,
  labelsRoot: HTMLElement,
  hooks: { onHover: (i: number) => void; onPick: (name: string) => void },
) {
  const labels = MAP_LOCALITIES.map((l) => {
    const el = document.createElement("span");
    el.className = "beacon-label";
    el.innerHTML = `${l.name}<b>—</b>`;
    labelsRoot.append(el);
    return el;
  });
  let readings: (LiveReading | null)[] = [];

  const renderList = () => {
    const order = MAP_LOCALITIES.map((l, i) => ({ l, i, r: readings[i] })).sort(
      (a, b) => (a.r?.aqi ?? 1e9) - (b.r?.aqi ?? 1e9) || a.l.name.localeCompare(b.l.name),
    );
    list.innerHTML = order
      .map(
        ({ l, i, r }) =>
          `<li data-i="${i}" tabindex="0" role="button" aria-label="Scan ${l.name}"><span>${l.name}</span><b style="${r ? `--c:${aqiColor(r.aqi)}` : ""}">${r ? r.aqi.toFixed(0) : "—"}</b></li>`,
      )
      .join("");
  };
  renderList();

  list.addEventListener("pointerover", (e) => {
    const li = (e.target as HTMLElement).closest<HTMLElement>("li");
    if (li) hooks.onHover(Number(li.dataset.i));
  });
  list.addEventListener("pointerleave", () => hooks.onHover(-1));
  const pick = (e: Event) => {
    const li = (e.target as HTMLElement).closest<HTMLElement>("li");
    if (li) hooks.onPick(MAP_LOCALITIES[Number(li.dataset.i)].name);
  };
  list.addEventListener("click", pick);
  list.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick(e);
    }
  });

  return {
    setReadings(r: (LiveReading | null)[]) {
      readings = r;
      renderList();
      labels.forEach((el, i) => {
        const v = r[i];
        if (!v) return;
        const b = el.querySelector("b")!;
        b.textContent = v.aqi.toFixed(0);
        b.style.setProperty("--c", aqiColor(v.aqi));
      });
    },
    setHot(i: number) {
      labels.forEach((el, j) => el.classList.toggle("is-hot", j === i));
      list.querySelectorAll("li").forEach((li) => li.classList.toggle("is-hot", Number(li.dataset.i) === i));
    },
    place(points: { x: number; y: number; visible: boolean }[], visibility: number, compact: boolean, avoid: DOMRect[] = []) {
      labels.forEach((el, i) => {
        const p = points[i];
        const hot = el.classList.contains("is-hot");
        const covered = p && avoid.some((r) => p.x > r.left - 60 && p.x < r.right + 60 && p.y > r.top - 10 && p.y < r.bottom + 40);
        const show = p && p.visible && visibility > 0.4 && (hot || (!covered && (!compact || i % 3 === 0)));
        el.style.opacity = show ? String(Math.min(1, (visibility - 0.4) * 2.5)) : "0";
        if (p) el.style.transform = `translate(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px)`;
      });
    },
  };
}
