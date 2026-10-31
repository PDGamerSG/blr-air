import "@fontsource-variable/anybody/wdth.css";
import "@fontsource/roboto-mono/500.css";
import "@fontsource/roboto-mono/700.css";
import "@fontsource/kalam/400.css";
import "@fontsource/kalam/700.css";
import "./styles/main.css";
import "./styles/planner.css";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import Lenis from "lenis";
import { aqiColor } from "./air/scoring";
import { AGENT_ADDRESS, AGENT_HANDLE, LINKS, SUBMISSIONS_CLOSE } from "./config";
import { World } from "./scene/World";
import { drawDiagram } from "./ui/diagram";
import { initCityBoard, initMarquee, loadLive, MAP_LOCALITIES, renderHeroLive } from "./ui/live";
import { initScanner, promptFor } from "./ui/scanner";
import { initPlanner } from "./ui/planner";
import { initWheel } from "./ui/wheel";
import { copyText } from "./ui/agentLink";

gsap.registerPlugin(ScrollTrigger, SplitText);

// The working planner does not depend on WebGL or the scroll animation loading.
initPlanner();

const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel)!;
const $$ = <T extends Element = HTMLElement>(sel: string) => [...document.querySelectorAll<T>(sel)];
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const compact = matchMedia("(max-width: 760px)").matches;

document.body.classList.add("is-loading");

// ---------- links ----------
const linkMap: Record<string, string> = {
  "data-asi": LINKS.asiOne,
  "data-agentverse": LINKS.agentverse,
  "data-github": LINKS.github,
  "data-roast": LINKS.roast,
  "data-openmeteo": LINKS.openMeteo,
  "data-cams": LINKS.cams,
  "data-docs": LINKS.uagentDocs,
  "data-sb": LINKS.strangerBuilds,
};
for (const [attr, href] of Object.entries(linkMap)) $$<HTMLAnchorElement>(`a[${attr}]`).forEach((a) => (a.href = href));
$$("[data-address]").forEach((el) => (el.textContent = AGENT_ADDRESS));
$$(".handle").forEach((el) => (el.textContent = AGENT_HANDLE));

// ---------- toast + clipboard ----------
const toastEl = $(".toast");
let toastTimer = 0;
function toast(msg: string) {
  toastEl.textContent = msg;
  toastEl.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toastEl.classList.remove("is-on"), 3200);
}

// On-page requests always use the on-page planner; ASI:One chat stays on the extension links.
function askAgent(prompt: string) {
  const input = $<HTMLTextAreaElement>("#planner-query");
  input.value = prompt;
  $<HTMLInputElement>("#planner-venue").value = "";
  $<HTMLInputElement>("input[name=include_venue]").checked = false;
  $<HTMLFormElement>("[data-planner-form]").requestSubmit();
  lenis.scrollTo("#planner", { offset: -90 });
}

$("[data-copy-address]").addEventListener("click", () => copyText(AGENT_ADDRESS).then(() => toast("Agent address copied.")));
const finalPrompt = promptFor("HSR Layout", { hours: 1, activity: "run", day: "next48", period: "any" });
$(".final__prompt code").textContent = finalPrompt;
$("[data-prompt-copy]").addEventListener("click", () => copyText(finalPrompt).then(() => toast("Copied. Now paste it into ASI:One.")));

// ---------- world ----------
const canvas = $<HTMLCanvasElement>("#world");
let world: World | null = null;
try {
  world = new World(canvas);
} catch {
  document.body.classList.add("no-webgl");
  canvas.remove();
}

// ---------- smooth scroll ----------
const lenis = new Lenis({ lerp: reducedMotion ? 1 : 0.085, smoothWheel: !reducedMotion, anchors: { offset: 0 } });
lenis.stop();
lenis.on("scroll", ScrollTrigger.update);
gsap.ticker.lagSmoothing(0);

// ---------- preloader ----------
const countEl = $("#loadCount");
const loadState = { target: 0, shown: 0 };
const counter = gsap.ticker.add(() => {
  loadState.shown += (loadState.target - loadState.shown) * 0.12;
  countEl.textContent = String(Math.round(loadState.shown * 100)).padStart(3, "0");
});

const minDelay = new Promise((r) => setTimeout(r, reducedMotion ? 200 : 1400));
const worldReady = world ? world.load((p) => (loadState.target = p * 0.9)).catch((e) => console.warn("3D assets failed", e)) : Promise.resolve();

Promise.all([worldReady, document.fonts.ready, minDelay]).then(() => {
  loadState.target = 1;
  layoutAll();
  world?.snap();
  gsap.delayedCall(0.45, revealPage);
});

function revealPage() {
  gsap.ticker.remove(counter);
  countEl.textContent = "100";
  const pre = $(".preloader");
  gsap.to(pre, {
    clipPath: "circle(0% at 50% 50%)",
    duration: reducedMotion ? 0.01 : 1.1,
    ease: "expo.inOut",
    onComplete: () => pre.remove(),
  });
  document.body.classList.remove("is-loading");
  lenis.start();
  intro();
}

// ---------- text splitting + reveals ----------
const splits = new Map<HTMLElement, SplitText>();
$$("[data-split]").forEach((el) => splits.set(el, new SplitText(el, { type: "words,chars", charsClass: "char", wordsClass: "word" })));

function intro() {
  const tl = gsap.timeline({ defaults: { ease: "back.out(1.7)" } });
  const heroChars = $$(".hero__title .char");
  tl.from(heroChars, { yPercent: 120, rotate: 12, opacity: 0, duration: 0.9, stagger: 0.03 }, 0.25)
    .from(".hero .reveal", { y: 30, opacity: 0, duration: 0.8, stagger: 0.12, ease: "power3.out" }, 0.5)
    .from(".hero__pilot", { scale: 0, rotate: -40, duration: 0.8 }, 1)
    .from(".scroll-hint", { opacity: 0, y: 20, duration: 0.6 }, 1.2)
    .from(".nav", { yPercent: -100, duration: 0.8, ease: "power3.out" }, 0.3);
}

splits.forEach((split, el) => {
  if (el.closest(".hero")) return;
  gsap.from(split.chars, {
    yPercent: 110,
    rotate: 8,
    opacity: 0,
    duration: 0.8,
    ease: "back.out(1.8)",
    stagger: 0.022,
    scrollTrigger: { trigger: el, start: "top 85%", once: true },
  });
});

ScrollTrigger.batch(".section-head .eyebrow, .section-head__lede, .scanner__grid, .hire__cols, .builds__meta, .builds__lede, .builds__side, .final__lede, .final__ctas, .final__prompt, .builds .hero__ctas", {
  start: "top 88%",
  once: true,
  onEnter: (els) => gsap.from(els, { y: 50, opacity: 0, duration: 0.9, stagger: 0.1, ease: "power3.out" }),
});

// ---------- hero rotator ----------
const rotator = $(".rotator span");
const verbs = ["run.", "cycle.", "walk.", "commute.", "take the kids out."];
let verbIndex = 0;
const rotatorTimer = gsap.delayedCall(2.4, function swap() {
  verbIndex = (verbIndex + 1) % verbs.length;
  gsap.to(rotator, {
    yPercent: -110,
    duration: 0.3,
    ease: "power2.in",
    onComplete: () => {
      rotator.textContent = verbs[verbIndex];
      gsap.fromTo(rotator, { yPercent: 110 }, { yPercent: 0, duration: 0.45, ease: "back.out(2)" });
    },
  });
  rotatorTimer.restart(true);
});

// ---------- marquee + live data ----------
const marquee = initMarquee($(".marquee__track"));
const board = initCityBoard($<HTMLOListElement>(".city__list"), $(".city__labels"), {
  onHover: (i) => {
    world?.setHotBeacon(i);
    board.setHot(i);
  },
  onPick: (name) => {
    scanner.setPlace(name);
    lenis.scrollTo("#scanner", { offset: -40, duration: 1.6 });
    setTimeout(() => scanner.scan(), 900);
  },
});
if (world) world.onBeaconHover = (i) => board.setHot(i);

loadLive()
  .then(({ city, map }) => {
    renderHeroLive(city);
    marquee.fill(map);
    board.setReadings(map);
    worldReady.then(() => world?.city?.setAqi(map, aqiColor));
  })
  .catch(() => {
    // The page still works without live readings; beacons just stay cyan.
  });

// ---------- scanner ----------
// The first visit scans HSR Layout automatically so the chart is never empty.
new IntersectionObserver((entries, io) => {
  if (entries.some((e) => e.isIntersecting)) {
    io.disconnect();
    scanner.scan();
  }
}, { rootMargin: "0px 0px -30% 0px" }).observe($(".scanner__grid"));
const scanner = initScanner({
  onResult: (color) => {
    world?.setBeamColor(color ?? "#ff6a2a");
    if (world?.ufo) world.ufo.zap = 1;
  },
  onAsk: askAgent,
  onCopy: (p) => copyText(p).then(() => toast("Prompt copied.")),
});

// ---------- diagram ----------
const sketch = drawDiagram($<SVGSVGElement>(".hire__sketch"));
const drawTl = gsap.timeline({ scrollTrigger: { trigger: ".hire__board", start: "top 80%", end: "bottom 55%", scrub: 0.6 } });
[...sketch.nodeLayers, ...sketch.edgeLayers].forEach((g, i) => {
  const paths = [...g.querySelectorAll("path")];
  paths.forEach((p) => {
    const len = p.getTotalLength();
    p.style.strokeDasharray = `${len}`;
    p.style.strokeDashoffset = `${len}`;
  });
  drawTl
    .fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.15 }, i * 0.35)
    .to(paths, { strokeDashoffset: 0, duration: 0.6, stagger: 0.01, ease: "none" }, i * 0.35);
});

// ---------- prompts wheel ----------
const wheel = initWheel($(".wheel"), (text) => askAgent(`${AGENT_HANDLE} ${text}`));

// ---------- fine print ----------
const fineTl = gsap.timeline({ scrollTrigger: { trigger: ".file", start: "top 70%", end: "bottom 75%", scrub: 0.5 } });
$$(".redact").forEach((el, i) => fineTl.fromTo(el, { "--cover": 1 }, { "--cover": 0, duration: 1, ease: "power2.inOut" }, i * 0.5));
fineTl.to(".file__stamp", { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(3)" });

// ---------- countdown ----------
const cd = Object.fromEntries($$("[data-cd]").map((el) => [el.dataset.cd!, el]));
function tickCountdown() {
  const ms = Math.max(0, SUBMISSIONS_CLOSE.getTime() - Date.now());
  const s = Math.floor(ms / 1000);
  const parts = { d: Math.floor(s / 86400), h: Math.floor(s / 3600) % 24, m: Math.floor(s / 60) % 60, s: s % 60 };
  for (const [k, v] of Object.entries(parts)) cd[k].textContent = String(v).padStart(2, "0");
}
tickCountdown();
setInterval(tickCountdown, 1000);

// ---------- sticky section controllers ----------
const sections = {
  haze: $("#haze"),
  signals: $("#signals"),
  city: $("#city"),
  prompts: $("#prompts"),
};

function progress(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  return clamp(-r.top / Math.max(1, el.offsetHeight - innerHeight));
}

const hazeSteps = $$("#haze [data-step]");
let hazeStep = -2;
function updateHaze() {
  const r = sections.haze.getBoundingClientRect();
  const p = progress(sections.haze);
  const step = r.top > innerHeight * 0.55 ? -1 : p < 0.3 ? 0 : p < 0.58 ? 1 : 2;
  if (step === hazeStep) return;
  hazeStep = step;
  hazeSteps.forEach((el) => el.classList.toggle("is-shown", Number(el.dataset.step) <= step));
}

const signalCards = $$(".signal");
const formulaTerms = $$(".formula__term");
const signalDots = $$(".signals__dots li");
let activeSignal = -1;
function updateSignals() {
  const i = Math.min(3, Math.floor(progress(sections.signals) * 4));
  if (i === activeSignal) return;
  const prev = signalCards[activeSignal];
  const dir = i > activeSignal ? 1 : -1;
  activeSignal = i;
  world?.setActiveSignal(i);
  if (prev) gsap.to(prev, { x: -60 * dir, rotate: -5 * dir, opacity: 0, duration: 0.35, ease: "power2.in", onComplete: () => gsap.set(prev, { visibility: "hidden" }) });
  gsap.fromTo(
    signalCards[i],
    { x: 80 * dir, rotate: 7 * dir, opacity: 0, visibility: "visible" },
    { x: 0, rotate: dir * -1.5, opacity: 1, duration: 0.7, ease: "back.out(1.6)", delay: prev ? 0.15 : 0 },
  );
  formulaTerms.forEach((t, j) => {
    t.classList.toggle("is-lit", j <= i);
    t.classList.toggle("is-on", j === i);
  });
  signalDots.forEach((d, j) => d.classList.toggle("is-on", j <= i));
}

// ---------- altimeter + nav ----------
const altUfo = $(".altimeter__ufo");
const altTicks = $(".altimeter__ticks");
const tickNames: [string, string][] = [
  ["top", "Orbit"],
  ["haze", "Haze"],
  ["signals", "Signals"],
  ["scanner", "Scan"],
  ["city", "City"],
  ["hire", "Hire"],
  ["prompts", "Prompts"],
  ["fine-print", "Fine print"],
  ["stranger-builds", "Origin"],
  ["open", "Landing"],
];
altTicks.innerHTML = tickNames.map(([, n]) => `<li data-name="${n}">${n}</li>`).join("");
const tickEls = $$(".altimeter__ticks li");
const navLinks = $$<HTMLAnchorElement>(".nav__links a");
let sectionTops: number[] = [];

function layoutAll() {
  world?.resize();
  world?.layout();
  ScrollTrigger.refresh();
  const max = document.documentElement.scrollHeight - innerHeight;
  sectionTops = tickNames.map(([id]) => document.getElementById(id)!.getBoundingClientRect().top + scrollY);
  tickEls.forEach((li, i) => (li.style.top = `${clamp(sectionTops[i] / max) * 100}%`));
  if (world) {
    world.scrollTo(scrollY);
  }
}

const nav = $(".nav");
let lastY = 0;
function updateChrome(y: number) {
  const max = document.documentElement.scrollHeight - innerHeight;
  altUfo.style.top = `${clamp(y / max) * 100}%`;
  const mid = y + innerHeight * 0.45;
  let current = 0;
  sectionTops.forEach((t, i) => {
    if (mid >= t) current = i;
  });
  tickEls.forEach((li, i) => li.classList.toggle("is-active", i === current));
  const id = tickNames[current][0];
  navLinks.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === `#${id}`));
  nav.classList.toggle("is-hidden", y > lastY + 2 && y > innerHeight * 0.6);
  if (y < lastY - 2) nav.classList.remove("is-hidden");
  lastY = y;
}

function onScroll() {
  const y = scrollY;
  world?.scrollTo(y);
  updateHaze();
  updateSignals();
  wheel.setProgress(progress(sections.prompts));
  updateChrome(y);
  marquee.tween.timeScale(1 + Math.min(6, Math.abs(lenis.velocity) * 0.15));
}
lenis.on("scroll", onScroll);
onScroll();

// ---------- per-frame ----------
const beaconPoints: { x: number; y: number; visible: boolean }[] = [];
// Map labels hide behind the city heading and leaderboard instead of covering them.
const avoidEls = [$(".city__head .title"), $(".city__head .section-head__lede"), $(".city__board")];
let avoid: DOMRect[] = [];
const cursor = $(".cursor");
const cursorPos = { x: innerWidth / 2, y: innerHeight / 2, tx: innerWidth / 2, ty: innerHeight / 2 };

gsap.ticker.add((time) => {
  lenis.raf(time * 1000);
  wheel.tick();
  cursorPos.x += (cursorPos.tx - cursorPos.x) * 0.22;
  cursorPos.y += (cursorPos.ty - cursorPos.y) * 0.22;
  cursor.style.transform = `translate(${cursorPos.x}px, ${cursorPos.y}px)`;
  if (!world || document.hidden) return;
  world.tick();
  if (world.city && world.beaconsVisible > 0.05) {
    avoid = avoidEls.map((el) => el.getBoundingClientRect());
    world.projectBeacons(beaconPoints);
    board.place(beaconPoints, world.beaconsVisible, compact, avoid);
  }
});

// ---------- pointer ----------
addEventListener("pointermove", (e) => {
  cursorPos.tx = e.clientX;
  cursorPos.ty = e.clientY;
  world?.setPointer(e.clientX, e.clientY);
  const hover = (e.target as HTMLElement).closest("a, button, select, input, .ticket, .city__list li, .bar");
  cursor.classList.toggle("is-hover", !!hover);
});

addEventListener("click", (e) => {
  if (!world || (e.target as HTMLElement).closest("a, button, input, select, .panel, .wheel, .card, .signal")) return;
  world.setPointer(e.clientX, e.clientY);
  if (world.hitUfo()) toast("Zap! Gaali says: keep scrolling, the air gets better.");
});

// ---------- motion toggle ----------
const motionBtn = $<HTMLButtonElement>("[data-motion]");
function setPaused(paused: boolean) {
  document.body.classList.toggle("is-paused", paused);
  motionBtn.setAttribute("aria-pressed", String(paused));
  motionBtn.textContent = paused ? "Resume motion" : "Pause motion";
  if (world) world.paused = paused;
  marquee.tween.paused(paused);
  if (paused) rotatorTimer.pause();
  else rotatorTimer.resume();
}
motionBtn.addEventListener("click", () => setPaused(!document.body.classList.contains("is-paused")));
if (reducedMotion) setPaused(true);

// ---------- resize ----------
let resizeTimer = 0;
const relayout = () => {
  clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    layoutAll();
    onScroll();
  }, 150);
};
addEventListener("resize", relayout);
new ResizeObserver(relayout).observe($("main"));

// Exposed in dev for console debugging and scripted screenshots.
if (import.meta.env.DEV) Object.assign(window, { __blr: { world, lenis, MAP_LOCALITIES } });
