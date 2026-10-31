import rough from "roughjs";

interface Node {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  sub: string;
  fill: string;
}

const NODES: Node[] = [
  { id: "you", x: 30, y: 40, w: 250, h: 104, title: "You", sub: "runner · parent · commuter", fill: "#ffe62b" },
  { id: "asi", x: 420, y: 40, w: 300, h: 104, title: "ASI:One", sub: "Agents on · asi1-mini parses", fill: "#8be9ed" },
  { id: "agent", x: 420, y: 300, w: 320, h: 124, title: "@blr-air uAgent", sub: "scores every 1–2 h window", fill: "#ff5b9e" },
  { id: "planner", x: 30, y: 320, w: 280, h: 104, title: "day-planner agent", sub: "hires it with WindowRequest", fill: "#ead9c8" },
  { id: "meteo", x: 860, y: 300, w: 320, h: 124, title: "Open-Meteo + CAMS", sub: "hourly AQI · PM2.5 · rain · °C", fill: "#7cff5b" },
  { id: "reply", x: 860, y: 40, w: 320, h: 104, title: "e.g. “Go 06:00–07:00”", sub: "+ worst hour, source, caveats", fill: "#ffffff" },
];

type Edge = [from: string, to: string, label: string, bend?: number];

const EDGES: Edge[] = [
  ["you", "asi", "plain words"],
  ["asi", "agent", "Chat Protocol"],
  ["planner", "agent", "WindowRequest"],
  ["agent", "meteo", "fetch forecast", -30],
  ["meteo", "agent", "hourly data", 30],
  ["agent", "reply", "WindowResponse"],
  ["reply", "you", "answer + caveats", -70],
];

const NS = "http://www.w3.org/2000/svg";

function anchor(n: Node, toward: Node) {
  const cx = n.x + n.w / 2;
  const cy = n.y + n.h / 2;
  const dx = toward.x + toward.w / 2 - cx;
  const dy = toward.y + toward.h / 2 - cy;
  const sx = dx === 0 ? Infinity : n.w / 2 / Math.abs(dx);
  const sy = dy === 0 ? Infinity : n.h / 2 / Math.abs(dy);
  const s = Math.min(sx, sy) * 1.08;
  return [cx + dx * s, cy + dy * s] as const;
}

// Hand-drawn, Excalidraw-style architecture sketch. Every stroke is returned so the
// caller can "draw" it on scroll.
export function drawDiagram(svg: SVGSVGElement) {
  const rc = rough.svg(svg);
  const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));
  const strokes: SVGPathElement[] = [];
  const nodeLayers: SVGGElement[] = [];
  const edgeLayers: SVGGElement[] = [];

  const text = (x: number, y: number, str: string, size: number, weight = 400, anchorPos = "middle") => {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", String(x));
    t.setAttribute("y", String(y));
    t.setAttribute("font-size", String(size));
    t.setAttribute("font-weight", String(weight));
    t.setAttribute("text-anchor", anchorPos);
    t.textContent = str;
    return t;
  };

  EDGES.forEach(([a, b, label, bend = 0], i) => {
    const from = byId[a];
    const to = byId[b];
    const [x1, y1] = anchor(from, to);
    const [x2, y2] = anchor(to, from);
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const len = Math.hypot(x2 - x1, y2 - y1);
    const nx = -(y2 - y1) / len;
    const ny = (x2 - x1) / len;
    const cx = mx + nx * bend;
    const cy = my + ny * bend;
    const g = document.createElementNS(NS, "g");
    g.append(
      rc.curve(
        [
          [x1, y1],
          [cx, cy],
          [x2, y2],
        ],
        { stroke: "#080b0d", strokeWidth: 2.4, roughness: 1.4, seed: i + 3 },
      ),
    );
    const ang = Math.atan2(y2 - cy, x2 - cx);
    for (const d of [0.45, -0.45]) {
      g.append(
        rc.line(x2, y2, x2 - Math.cos(ang + d) * 18, y2 - Math.sin(ang + d) * 18, {
          stroke: "#080b0d",
          strokeWidth: 2.4,
          roughness: 1.2,
          seed: i + 10,
        }),
      );
    }
    const lx = (x1 + 2 * cx + x2) / 4;
    const ly = (y1 + 2 * cy + y2) / 4;
    const pill = rc.rectangle(lx - label.length * 5.4 - 10, ly - 18, label.length * 10.8 + 20, 30, {
      fill: "#fff7ef",
      fillStyle: "solid",
      stroke: "#080b0d",
      strokeWidth: 1.4,
      roughness: 1.6,
      seed: i + 20,
    });
    g.append(pill, text(lx, ly + 4, label, 18));
    edgeLayers.push(g);
  });

  NODES.forEach((n, i) => {
    const g = document.createElementNS(NS, "g");
    g.append(
      rc.rectangle(n.x, n.y, n.w, n.h, {
        fill: n.fill,
        fillStyle: n.id === "reply" ? "solid" : "hachure",
        hachureGap: 7,
        fillWeight: 1.6,
        stroke: "#080b0d",
        strokeWidth: 3,
        roughness: 1.5,
        bowing: 1.4,
        seed: i + 40,
      }),
      text(n.x + n.w / 2, n.y + n.h / 2 - 2, n.title, 27, 700),
      text(n.x + n.w / 2, n.y + n.h / 2 + 26, n.sub, 17),
    );
    nodeLayers.push(g);
  });

  // Nodes first, then arrows in reading order.
  [...nodeLayers, ...edgeLayers].forEach((g) => {
    svg.append(g);
    g.querySelectorAll("path").forEach((p) => strokes.push(p));
  });
  const note = text(600, 540, "one agent, two doors: chat for humans, typed messages for agents", 20, 400);
  note.setAttribute("opacity", "0.7");
  svg.append(note);
  return { nodeLayers, edgeLayers, strokes };
}
