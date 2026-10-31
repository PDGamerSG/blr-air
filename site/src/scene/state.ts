import * as THREE from "three";

type V3 = [number, number, number];

// Everything the scroll timeline can animate. Each section declares one state at
// its start and optionally one at its end; the world interpolates in between.
export interface SceneState {
  cam: V3;
  look: V3;
  fov: number;
  shift: number; // horizontal lens shift: + puts the subject right of centre
  ufo: V3;
  ufoScale: number;
  beam: number;
  beamColor: string;
  scan: number; // how much the scanner's verdict colour tints the beam
  haze: number;
  hazeOpacity: number;
  hazeA: string;
  hazeB: string;
  city: number;
  beacons: number;
  signals: number;
  night: number;
  light: number;
  skyTop: string;
  skyMid: string;
  skyBottom: string;
  fogNear: number;
  fogFar: number;
  stars: number;
  stripes: number;
  moon: number;
  sun: number;
  sunY: number;
  gaali: number;
  mask: number; // 0 = mask on, 1 = mask off
}

const NIGHT: SceneState = {
  cam: [0, 2.1, 13],
  look: [1.6, 3.5, 0],
  fov: 42,
  shift: 0.24,
  ufo: [4.3, 4.3, -1],
  ufoScale: 1,
  beam: 0.85,
  beamColor: "#ffe62b",
  scan: 0,
  haze: 0.35,
  hazeOpacity: 0.45,
  hazeA: "#b07a52",
  hazeB: "#ff6a2a",
  city: 1,
  beacons: 0,
  signals: 0,
  night: 1,
  light: 0.85,
  skyTop: "#071219",
  skyMid: "#0e2a2e",
  skyBottom: "#3a2040",
  fogNear: 14,
  fogFar: 70,
  stars: 1,
  stripes: 0,
  moon: 1,
  sun: 0,
  sunY: -20,
  gaali: 0,
  mask: 0,
};

const at = (patch: Partial<SceneState>): SceneState => ({ ...NIGHT, ...patch });

const SMOG = {
  skyTop: "#1b1512",
  skyMid: "#3e2a20",
  skyBottom: "#6e4a33",
  hazeA: "#8a6040",
  hazeB: "#d0703a",
  stars: 0.05,
  moon: 0,
};

const DEEP = { skyTop: "#05080c", skyMid: "#10233f", skyBottom: "#2a1838" };

const DAWN = {
  skyTop: "#10233f",
  skyMid: "#9a4479",
  skyBottom: "#ff8a4c",
  stripes: 1,
  stars: 0.15,
  moon: 0,
  sun: 1,
  night: 0.15,
  light: 1.15,
  fogNear: 18,
  fogFar: 90,
};

export const SCENES: Record<string, { start: SceneState; end?: SceneState }> = {
  hero: {
    start: NIGHT,
    end: at({ cam: [0, 2.4, 11.5], look: [1.6, 3.4, 0], haze: 0.45 }),
  },
  haze: {
    start: at({ ...SMOG, cam: [-0.4, 2.8, 8], look: [0.6, 3.2, 0], shift: 0, ufo: [3.5, 7.2, -5], beam: 0.25, beamColor: "#ff6a2a", haze: 1, hazeOpacity: 0.85, fogNear: 4, fogFar: 26 }),
    end: at({ ...SMOG, cam: [0.6, 3.2, 5.6], look: [0.4, 3.4, 0], shift: 0, ufo: [2, 8, -6], beam: 0.15, beamColor: "#ff6a2a", haze: 1, hazeOpacity: 0.95, fogNear: 3, fogFar: 22 }),
  },
  signals: {
    start: at({ ...DEEP, cam: [0, 4.6, 8.6], look: [0, 4.1, 0], shift: -0.2, ufo: [0, 4.1, 0], ufoScale: 0.85, beam: 0.35, haze: 0.25, hazeOpacity: 0.35, signals: 1, fogNear: 12, fogFar: 60 }),
    end: at({ ...DEEP, cam: [6.4, 5.6, 5.2], look: [0, 4.0, 0], shift: -0.2, ufo: [0, 4.1, 0], ufoScale: 0.85, beam: 0.35, haze: 0.25, hazeOpacity: 0.35, signals: 1, fogNear: 12, fogFar: 60 }),
  },
  scanner: {
    start: at({ ...DEEP, cam: [0, 10, 12.5], look: [0, 0.8, 0], shift: 0, ufo: [-6.2, 4.6, 1.5], ufoScale: 0.8, beam: 0.6, scan: 1, haze: 0.2, hazeOpacity: 0.3 }),
    end: at({ ...DEEP, cam: [-2, 9, 12], look: [0, 0.8, 0], shift: 0, ufo: [-6.6, 4.6, 2.5], ufoScale: 0.8, beam: 0.6, scan: 1, haze: 0.2, hazeOpacity: 0.3 }),
  },
  city: {
    start: at({ ...DEEP, cam: [0, 17.5, 5.5], look: [0, 0, 0.4], fov: 46, shift: -0.06, ufo: [0, 13, -9], ufoScale: 0.6, beam: 0, beacons: 1, haze: 0.1, hazeOpacity: 0.2, fogNear: 25, fogFar: 80 }),
    end: at({ ...DEEP, cam: [-4.5, 11.5, 10.5], look: [0.4, 0, -0.2], fov: 46, shift: -0.06, ufo: [0, 13, -9], ufoScale: 0.6, beam: 0, beacons: 1, haze: 0.1, hazeOpacity: 0.2, fogNear: 25, fogFar: 80 }),
  },
  hire: {
    start: at({ ...DEEP, cam: [-9, 3.4, 10], look: [0, 2.6, 0], shift: 0, ufo: [-1.5, 5.2, -1.5], beam: 0.4, haze: 0.3 }),
    end: at({ ...DEEP, cam: [-6, 2.6, 12], look: [0, 3, 0], shift: 0, ufo: [0.5, 5.4, -2], beam: 0.4, haze: 0.3 }),
  },
  prompts: {
    start: at({ ...DEEP, cam: [8, 3.6, 9.5], look: [0, 3.4, 0], shift: 0, ufo: [1.5, 5.6, -3], beam: 0.7, beamColor: "#ff5b9e", haze: 0.35 }),
    end: at({ ...DEEP, cam: [10, 4.4, 4], look: [0, 3.4, 0], shift: 0, ufo: [1.5, 5.6, -3], beam: 0.7, beamColor: "#ff5b9e", haze: 0.35 }),
  },
  fine: {
    start: at({ ...DEEP, cam: [0, 6, 14], look: [0, 3, 0], shift: 0, ufo: [-3.5, 6, -2], beam: 0.2, haze: 0.2, moon: 1 }),
  },
  builds: {
    start: at({ ...DEEP, cam: [-3.5, 1.3, 12], look: [0, 5.2, 0], shift: 0.15, ufo: [-4.5, 2.6, 2], ufoScale: 0.8, beam: 0.5, haze: 0.25, moon: 0 }),
    end: at({ ...DEEP, cam: [-2.5, 1.2, 11.5], look: [0.5, 5.2, 0], shift: 0.15, ufo: [-1.2, 3.0, 1], ufoScale: 0.8, beam: 0.5, haze: 0.25, moon: 0 }),
  },
  final: {
    start: at({ ...DAWN, cam: [0, 1.3, 11.5], look: [1.4, 2.3, 0], shift: 0.3, ufo: [2.6, 3.9, 2.2], ufoScale: 0.62, beam: 1, beamColor: "#7cff5b", haze: 0.15, hazeOpacity: 0.25, gaali: 1, mask: 0, sunY: 4 }),
    end: at({ ...DAWN, cam: [0, 1.1, 11], look: [1.4, 2.2, 0], shift: 0.3, ufo: [2.6, 3.8, 2.2], ufoScale: 0.62, beam: 1, beamColor: "#7cff5b", haze: 0.05, hazeOpacity: 0.2, gaali: 1, mask: 1, sunY: 16 }),
  },
};

const tmpA = new THREE.Color();
const tmpB = new THREE.Color();

function mixColor(a: string, b: string, t: number) {
  return `#${tmpA.set(a).lerp(tmpB.set(b), t).getHexString()}`;
}

export function mixState(a: SceneState, b: SceneState, t: number): SceneState {
  const out = { ...a } as Record<string, unknown>;
  for (const key of Object.keys(a) as (keyof SceneState)[]) {
    const va = a[key];
    const vb = b[key];
    if (typeof va === "number") out[key] = va + ((vb as number) - va) * t;
    else if (typeof va === "string") out[key] = mixColor(va, vb as string, t);
    else out[key] = (va as V3).map((v, i) => v + ((vb as V3)[i] - v) * t);
  }
  return out as unknown as SceneState;
}

export function cloneState(s: SceneState): SceneState {
  return mixState(s, s, 0);
}
