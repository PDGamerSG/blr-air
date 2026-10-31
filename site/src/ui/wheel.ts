import { AGENT_HANDLE, PROMPTS } from "../config";

const COLORS = [
  ["#ffe62b", "#e20b1b"],
  ["#8be9ed", "#c04f93"],
  ["#ff5b9e", "#080b0d"],
  ["#ead9c8", "#e20b1b"],
  ["#7cff5b", "#c04f93"],
  ["#ff6a2a", "#080b0d"],
];

// A drum of prompt "tickets": scroll turns it, drag flings it, arrows step it.
export function initWheel(root: HTMLElement, onPick: (prompt: string) => void) {
  const ring = root.querySelector<HTMLElement>(".wheel__ring")!;
  const n = PROMPTS.length;
  const step = 360 / n;
  const cards = PROMPTS.map((p, i) => {
    const [bg, accent] = COLORS[i % COLORS.length];
    const card = document.createElement("button");
    card.type = "button";
    card.className = "ticket";
    card.style.setProperty("--bg", bg);
    card.style.setProperty("--accent", accent);
    card.innerHTML = `
      <span class="ticket__top"><span>Transmission ${String(i + 1).padStart(2, "0")}</span><span>${p.tag}</span></span>
      <span class="ticket__text" data-handle="${AGENT_HANDLE}">${p.text}</span>
      <span class="ticket__foot">Tap to ask Gaali</span>`;
    card.setAttribute("aria-label", `Ask: ${p.text}`);
    ring.append(card);
    return card;
  });

  let radius = 400;
  let scrollRot = 0;
  let dragRot = 0;
  let velocity = 0;
  let dragging = false;
  let moved = 0;
  let lastX = 0;

  function measure() {
    const w = Math.min(330, Math.max(230, innerWidth * 0.24));
    root.style.setProperty("--w", `${w}px`);
    root.style.setProperty("--hh", `${w * 1.18}px`);
    radius = (w / 2 / Math.tan(Math.PI / n)) * 1.12;
    cards.forEach((c, i) => {
      c.style.transform = `rotateY(${i * step}deg) translateZ(${radius}px)`;
    });
  }

  function render() {
    const rot = scrollRot + dragRot;
    ring.style.transform = `translateZ(${-radius}px) rotateX(-7deg) rotateY(${-rot}deg)`;
    cards.forEach((c, i) => {
      let d = (((i * step - rot) % 360) + 540) % 360 - 180;
      d = Math.abs(d);
      c.style.filter = `brightness(${1 - Math.min(0.55, d / 160)})`;
      c.tabIndex = d < step / 2 ? 0 : -1;
    });
  }

  root.addEventListener("pointerdown", (e) => {
    dragging = true;
    moved = 0;
    lastX = e.clientX;
    velocity = 0;
    root.setPointerCapture(e.pointerId);
  });
  root.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - lastX;
    lastX = e.clientX;
    moved += Math.abs(dx);
    velocity = -dx * 0.22;
    dragRot += velocity;
  });
  const end = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    root.releasePointerCapture(e.pointerId);
    if (moved < 6) {
      const card = (document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null)?.closest<HTMLElement>(".ticket");
      if (card) onPick(PROMPTS[cards.indexOf(card as HTMLButtonElement)].text);
    }
  };
  root.addEventListener("pointerup", end);
  root.addEventListener("pointercancel", end);
  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") dragRot += step;
    else if (e.key === "ArrowLeft") dragRot -= step;
    else if (e.key === "Enter" && document.activeElement?.classList.contains("ticket")) {
      onPick(PROMPTS[cards.indexOf(document.activeElement as HTMLButtonElement)].text);
    } else return;
    e.preventDefault();
  });

  measure();
  render();
  addEventListener("resize", measure);

  return {
    setProgress(p: number) {
      scrollRot = p * 360 * 0.85;
    },
    tick() {
      if (!dragging) {
        dragRot += velocity;
        velocity *= 0.93;
        if (Math.abs(velocity) < 0.01) velocity = 0;
      }
      render();
    },
  };
}
