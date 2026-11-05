import * as THREE from "three";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { LOCALITIES } from "../config";
import { addOutline, faceted, outlineMaterial, stylize, toon } from "./toon";

// Equirectangular projection of Delhi NCR onto the ground plane (1 unit ≈ 2.8 km).
const LAT0 = 28.575;
const LON0 = 77.235;
const K = 40;
export function geo(lat: number, lon: number) {
  return new THREE.Vector2((lon - LON0) * K * Math.cos((LAT0 * Math.PI) / 180), -(lat - LAT0) * K);
}

export const CITY_RADIUS = 8.6;

function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const LAKES: [number, number, number, number][] = [
  // lat, lon, radius (units), stretch
  [28.7395, 77.164, 0.2, 1.5], // Bhalswa
  [28.613, 77.309, 0.13, 1.3], // Sanjay Lake
  [28.554, 77.193, 0.08, 1.2], // Hauz Khas Lake
  [28.415, 77.283, 0.14, 1.2], // Badkhal
];

const PARKS: [number, number, number][] = [
  [28.5931, 77.2197, 0.13], // Lodhi Garden
  [28.6395, 77.1815, 0.34], // Central Ridge
  [28.536, 77.177, 0.3], // Sanjay Van
  [28.472, 77.22, 0.72], // Asola Bhatti
  [28.73, 77.222, 0.26], // Yamuna Biodiversity Park
  [28.55, 77.31, 0.2], // Okhla Bird Sanctuary
];

// The Yamuna, north to south, past Wazirabad, ITO, Nizamuddin and the Okhla barrage.
const YAMUNA: [number, number][] = [
  [28.87, 77.21], [28.8, 77.218], [28.74, 77.232], [28.705, 77.238], [28.67, 77.25], [28.635, 77.257],
  [28.598, 77.265], [28.565, 77.285], [28.54, 77.305], [28.51, 77.325], [28.47, 77.345], [28.42, 77.375], [28.34, 77.41],
];
const RIVER_WIDTH = 0.26;
const RIVER = new THREE.CatmullRomCurve3(
  YAMUNA.map(([lat, lon]) => {
    const p = geo(lat, lon);
    return new THREE.Vector3(p.x, 0, p.y);
  }),
  false,
  "centripetal",
).getSpacedPoints(180);

const INDIA_GATE: [number, number] = [28.6129, 77.2295];

const ROADS: [number, number][][] = [
  // Ring Road (closed below)
  [
    [28.7075, 77.18], [28.705, 77.22], [28.6675, 77.228], [28.638, 77.249], [28.589, 77.257], [28.572, 77.259],
    [28.564, 77.234], [28.567, 77.209], [28.591, 77.162], [28.63, 77.139], [28.649, 77.122], [28.672, 77.125],
  ],
  [
    // Outer Ring Road
    [28.725, 77.23], [28.734, 77.156], [28.706, 77.132], [28.679, 77.092], [28.63, 77.09], [28.584, 77.098],
    [28.545, 77.124], [28.531, 77.217], [28.544, 77.251], [28.531, 77.29],
  ],
  [[28.591, 77.162], [28.545, 77.124], [28.481, 77.08], [28.4, 76.98]], // NH-48 to Gurugram
  [[28.7075, 77.18], [28.734, 77.156], [28.85, 77.1]], // NH-44, GT Karnal Road
  [[28.589, 77.257], [28.6128, 77.2773], [28.6469, 77.3152], [28.6692, 77.4538], [28.68, 77.55]], // NH-9 to Ghaziabad
  [[28.572, 77.259], [28.57, 77.32], [28.5355, 77.391], [28.47, 77.5]], // DND Flyway and Noida Expressway
  [[28.572, 77.259], [28.495, 77.303], [28.4089, 77.3178], [28.3, 77.33]], // Mathura Road to Faridabad
  [[28.5245, 77.2066], [28.48, 77.09]], // Mehrauli-Gurugram Road
  [[28.6514, 77.1907], [28.672, 77.125], [28.679, 77.092], [28.68, 76.95]], // Rohtak Road
  [[28.6143, 77.1994], [28.6129, 77.2295]], // Kartavya Path
  [[28.6514, 77.1907], [28.6315, 77.2167], [28.6129, 77.2295], [28.5931, 77.2197], [28.5494, 77.2001], [28.5245, 77.2066]], // core
];

// Buildings: flat toon faces plus a lit-window grid that switches on at night.
const buildingVert = /* glsl */ `
  uniform float rise;
  varying vec3 vN;
  varying vec3 vWorld;
  varying vec3 vColor;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vec3 p = position;
    vec3 origin = vec3(instanceMatrix[3]);
    float g = clamp(rise * 1.7 - length(origin.xz) / 9.0, 0.0, 1.0);
    p.y *= max(g * g * (3.0 - 2.0 * g), 0.002);
    vec4 world = modelMatrix * instanceMatrix * vec4(p, 1.0);
    vWorld = world.xyz;
    vN = normalize(mat3(modelMatrix) * mat3(instanceMatrix) * normal);
    #ifdef USE_INSTANCING_COLOR
      vColor = instanceColor;
    #else
      vColor = vec3(0.2);
    #endif
    vec4 mvPosition = viewMatrix * world;
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`;

const buildingFrag = /* glsl */ `
  uniform vec3 lightDir;
  uniform float night;
  uniform float light;
  uniform vec3 windowColor;
  varying vec3 vN;
  varying vec3 vWorld;
  varying vec3 vColor;
  #include <common>
  #include <fog_pars_fragment>
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  void main() {
    vec3 n = normalize(vN);
    float l = dot(n, normalize(lightDir));
    float shade = l > 0.45 ? 1.0 : (l > 0.0 ? 0.74 : 0.52);
    vec3 col = vColor * shade * light;
    if (n.y > 0.5) {
      col = vColor * 1.25 * light;
    } else {
      float u = abs(n.x) > 0.5 ? vWorld.z : vWorld.x;
      vec2 g = vec2(u * 16.0, vWorld.y * 18.0);
      vec2 f = fract(g);
      float win = step(0.3, f.x) * step(f.x, 0.72) * step(0.3, f.y) * step(f.y, 0.72);
      float lit = step(0.58, hash(floor(g) + floor(vWorld.xz * 4.0)));
      col = mix(col, windowColor, win * lit * night * step(0.06, vWorld.y));
      col *= 1.0 - 0.35 * step(vWorld.y, 0.012);
    }
    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`;

const groundVert = /* glsl */ `
  varying vec3 vWorld;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    vec4 mvPosition = viewMatrix * world;
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`;

const groundFrag = /* glsl */ `
  uniform vec3 inner;
  uniform vec3 outer;
  uniform vec3 gridColor;
  uniform float grid;
  uniform float light;
  uniform float time;
  varying vec3 vWorld;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    float r = length(vWorld.xz);
    vec3 col = mix(inner, outer, smoothstep(6.0, 16.0, r)) * light;
    vec2 g = abs(fract(vWorld.xz * 2.0) - 0.5);
    float line = 1.0 - smoothstep(0.0, 0.035, min(g.x, g.y));
    float ringPulse = smoothstep(0.08, 0.0, abs(fract(r * 0.25 - time * 0.12) - 0.5));
    float inCity = 1.0 - smoothstep(8.0, 10.5, r);
    col += gridColor * (line * 0.22 + ringPulse * 0.08) * inCity * grid;
    // halftone dots on the far plain
    vec2 cell = fract(vWorld.xz * 1.4) - 0.5;
    float dots = step(length(cell), 0.12) * smoothstep(10.0, 18.0, r) * 0.07;
    col = mix(col, col * 0.6, dots);
    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`;

const roadFrag = /* glsl */ `
  uniform float time;
  uniform vec3 color;
  uniform float opacity;
  varying vec2 vUv;
  void main() {
    float x = fract(vUv.x * 26.0 - time * 0.35);
    float dash = smoothstep(0.0, 0.05, x) * (1.0 - smoothstep(0.05, 0.22, x));
    vec3 c = color * (0.45 + dash * 2.2);
    gl_FragColor = vec4(c, opacity * (0.35 + dash));
    #include <colorspace_fragment>
  }
`;

const pillarVert = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const pillarFrag = /* glsl */ `
  uniform vec3 color;
  uniform float opacity;
  uniform float time;
  varying vec2 vUv;
  void main() {
    float a = pow(1.0 - vUv.y, 1.4);
    float scan = 0.75 + 0.25 * step(0.5, fract(vUv.y * 14.0 - time * 1.4));
    gl_FragColor = vec4(color * 1.4, a * scan * opacity);
    #include <colorspace_fragment>
  }
`;

export interface Beacon {
  name: string;
  group: THREE.Group;
  pillar: THREE.Mesh<THREE.CylinderGeometry, THREE.ShaderMaterial>;
  cap: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  ring: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>;
  pick: THREE.Mesh;
  height: number;
  target: number;
  hot: number;
  phase: number;
}

export class City {
  group = new THREE.Group();
  beacons: Beacon[] = [];
  buildingUniforms = {
    rise: { value: 1 },
    night: { value: 1 },
    light: { value: 1 },
    lightDir: { value: new THREE.Vector3(0.5, 0.8, 0.3) },
    windowColor: { value: new THREE.Color("#ffd27a") },
  };
  groundUniforms = {
    inner: { value: new THREE.Color("#1b1a2c") },
    outer: { value: new THREE.Color("#5a2740") },
    gridColor: { value: new THREE.Color("#8be9ed") },
    grid: { value: 1 },
    light: { value: 1 },
    time: { value: 0 },
  };
  roadMaterials: THREE.ShaderMaterial[] = [];
  pillarMaterials: THREE.ShaderMaterial[] = [];
  mesas = new THREE.Group();
  beaconGroup = new THREE.Group();

  constructor(models: { tree: GLTF; gate: GLTF }, lite: boolean) {
    this.buildGround();
    this.buildLakesAndParks();
    this.buildBuildings(lite ? 1100 : 2400);
    this.buildRoads();
    this.buildTrees(models.tree, lite ? 40 : 80);
    this.buildIndiaGate(models.gate);
    this.buildMesas();
    this.buildBeacons();
    this.group.add(this.mesas, this.beaconGroup);
  }

  private buildGround() {
    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(260, 96).rotateX(-Math.PI / 2),
      new THREE.ShaderMaterial({
        uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, this.groundUniforms]),
        vertexShader: groundVert,
        fragmentShader: groundFrag,
        fog: true,
      }),
    );
    // Merge cloned the uniform objects; point back at ours so updates propagate.
    Object.assign((ground.material as THREE.ShaderMaterial).uniforms, this.groundUniforms);
    ground.renderOrder = -1;
    this.group.add(ground);
  }

  private blob(radius: number, stretch: number, seed: number) {
    const r = rng(seed);
    const shape = new THREE.Shape();
    const n = 28;
    const phase = r() * 6;
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2;
      const k = radius * (1 + 0.18 * Math.sin(a * 3 + phase) + 0.08 * Math.sin(a * 5 + phase * 2));
      const x = Math.cos(a) * k * stretch;
      const y = Math.sin(a) * k;
      if (i === 0) shape.moveTo(x, y);
      else shape.lineTo(x, y);
    }
    return new THREE.ShapeGeometry(shape).rotateX(-Math.PI / 2);
  }

  private ribbon(points: THREE.Vector3[], width: number) {
    const position: number[] = [];
    const index: number[] = [];
    points.forEach((p, i) => {
      const next = points[Math.min(i + 1, points.length - 1)];
      const prev = points[Math.max(i - 1, 0)];
      const dir = next.clone().sub(prev).normalize();
      // Vary the channel a little so the river doesn't read as a drawn line.
      const half = (width / 2) * (1 + 0.28 * Math.sin(i * 0.31) + 0.14 * Math.sin(i * 0.83));
      position.push(p.x - dir.z * half, 0, p.z + dir.x * half, p.x + dir.z * half, 0, p.z - dir.x * half);
      if (i) index.push(i * 2 - 2, i * 2 - 1, i * 2, i * 2 - 1, i * 2 + 1, i * 2);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
    geometry.setIndex(index);
    return geometry;
  }

  private buildLakesAndParks() {
    const water = new THREE.MeshBasicMaterial({ color: "#1f6670", fog: true, side: THREE.DoubleSide });
    const shore = new THREE.MeshBasicMaterial({ color: "#8be9ed", fog: true, side: THREE.DoubleSide });
    const bank = new THREE.Mesh(this.ribbon(RIVER, RIVER_WIDTH * 1.3), shore);
    const river = new THREE.Mesh(this.ribbon(RIVER, RIVER_WIDTH), water);
    bank.position.y = 0.006;
    river.position.y = 0.012;
    this.group.add(bank, river);
    LAKES.forEach(([lat, lon, r, s], i) => {
      const p = geo(lat, lon);
      const edge = new THREE.Mesh(this.blob(r * 1.12, s, i + 1), shore);
      const lake = new THREE.Mesh(this.blob(r, s, i + 1), water);
      edge.position.set(p.x, 0.006, p.y);
      lake.position.set(p.x, 0.012, p.y);
      edge.rotation.y = lake.rotation.y = i * 0.7;
      this.group.add(edge, lake);
    });
    const grass = new THREE.MeshBasicMaterial({ color: "#2c4a35", fog: true });
    PARKS.forEach(([lat, lon, r], i) => {
      const p = geo(lat, lon);
      const park = new THREE.Mesh(this.blob(r, 1.15, 40 + i), grass);
      park.position.set(p.x, 0.008, p.y);
      this.group.add(park);
    });
  }

  private blocked(x: number, z: number, pad = 0.05) {
    for (const p of RIVER) {
      if (Math.hypot(x - p.x, z - p.z) < RIVER_WIDTH * 0.65 + pad) return true;
    }
    for (const [lat, lon, r, s] of LAKES) {
      const p = geo(lat, lon);
      if (Math.hypot((x - p.x) / s, z - p.y) < r * 1.2 + pad) return true;
    }
    for (const [lat, lon, r] of PARKS) {
      const p = geo(lat, lon);
      if (Math.hypot(x - p.x, z - p.y) < r * 1.1 + pad) return true;
    }
    const v = geo(...INDIA_GATE);
    return Math.hypot(x - v.x, z - v.y) < 0.3;
  }

  private buildBuildings(count: number) {
    const r = rng(2026);
    const geom = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
    const material = new THREE.ShaderMaterial({
      uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, this.buildingUniforms]),
      vertexShader: buildingVert,
      fragmentShader: buildingFrag,
      fog: true,
    });
    Object.assign(material.uniforms, this.buildingUniforms);
    const mesh = new THREE.InstancedMesh(geom, material, count);
    const palette = ["#232c4f", "#2c2142", "#3c2552", "#243f4a", "#47283d", "#5d2457", "#1d3a3f", "#33325a"].map(
      (c) => new THREE.Color(c),
    );
    const accents = ["#ff5b9e", "#ead9c8", "#8be9ed", "#ff6a2a"].map((c) => new THREE.Color(c));
    const hubs = LOCALITIES.map((l) => geo(l.lat, l.lon));
    const towers = ["Gurugram", "Noida", "Connaught Place", "Saket", "Okhla", "Ghaziabad"].map((n) => {
      const l = LOCALITIES.find((x) => x.name === n)!;
      return geo(l.lat, l.lon);
    });
    const cbd = geo(28.6315, 77.2167); // Connaught Place
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const p = new THREE.Vector3();
    let placed = 0;
    let guard = 0;
    while (placed < count && guard++ < count * 6) {
      let x: number;
      let z: number;
      if (r() < 0.62) {
        const hub = r() < 0.25 ? cbd : hubs[Math.floor(r() * hubs.length)];
        const a = r() * Math.PI * 2;
        const d = Math.pow(r(), 0.8) * 1.15;
        x = hub.x + Math.cos(a) * d;
        z = hub.y + Math.sin(a) * d;
      } else {
        const a = r() * Math.PI * 2;
        const d = Math.sqrt(r()) * CITY_RADIUS;
        x = Math.cos(a) * d;
        z = Math.sin(a) * d * 1.05;
      }
      const dist = Math.hypot(x, z);
      if (dist > CITY_RADIUS || this.blocked(x, z)) continue;
      const nearTower = Math.min(...towers.map((t) => Math.hypot(x - t.x, z - t.y)));
      const nearCbd = Math.hypot(x - cbd.x, z - cbd.y);
      let h = 0.05 + Math.pow(r(), 3) * 0.28;
      if (nearCbd < 1.4) h += Math.pow(r(), 2) * 0.55 * (1 - nearCbd / 1.4);
      if (nearTower < 0.7) h += Math.pow(r(), 2) * 0.75 * (1 - nearTower / 0.7);
      h *= 1 - Math.min(0.6, dist / 22);
      const w = 0.07 + r() * 0.13;
      const d2 = 0.07 + r() * 0.13;
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), (r() - 0.5) * 0.5);
      p.set(x, 0, z);
      s.set(w, h, d2);
      m.compose(p, q, s);
      mesh.setMatrixAt(placed, m);
      const c = r() < 0.06 ? accents[Math.floor(r() * accents.length)] : palette[Math.floor(r() * palette.length)];
      mesh.setColorAt(placed, c);
      placed++;
    }
    mesh.count = placed;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.frustumCulled = false;
    this.group.add(mesh);
  }

  private buildRoads() {
    ROADS.forEach((road, i) => {
      const pts = road.map(([lat, lon]) => {
        const v = geo(lat, lon);
        return new THREE.Vector3(v.x, 0.03, v.y);
      });
      const curve = new THREE.CatmullRomCurve3(pts, i === 0, "centripetal");
      const material = new THREE.ShaderMaterial({
        uniforms: {
          time: { value: 0 },
          color: { value: new THREE.Color(i === 0 ? "#ffe62b" : "#ff6a2a") },
          opacity: { value: 0.9 },
        },
        vertexShader: pillarVert,
        fragmentShader: roadFrag,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      this.roadMaterials.push(material);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, i === 0 ? 240 : 90, i === 0 ? 0.028 : 0.02, 5, i === 0), material);
      this.group.add(tube);
    });
  }

  private buildTrees(model: GLTF, count: number) {
    const r = rng(77);
    const spots: THREE.Vector3[] = [];
    PARKS.forEach(([lat, lon, rad]) => {
      const c = geo(lat, lon);
      for (let i = 0; i < (count * 0.64) / PARKS.length; i++) {
        const a = r() * Math.PI * 2;
        const d = Math.sqrt(r()) * rad * 0.95;
        spots.push(new THREE.Vector3(c.x + Math.cos(a) * d * 1.1, 0, c.y + Math.sin(a) * d));
      }
    });
    while (spots.length < count) {
      const a = r() * Math.PI * 2;
      const d = Math.sqrt(r()) * CITY_RADIUS * 0.95;
      const x = Math.cos(a) * d;
      const z = Math.sin(a) * d;
      if (!this.blocked(x, z, 0)) spots.push(new THREE.Vector3(x, 0, z));
    }
    const meshes: THREE.Mesh[] = [];
    model.scene.updateMatrixWorld(true);
    model.scene.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh);
    });
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const scales = spots.map(() => 0.1 + r() * 0.07);
    const turns = spots.map(() => r() * Math.PI * 2);
    for (const src of meshes) {
      const geom = src.geometry.clone().applyMatrix4(src.matrixWorld);
      const color = (src.material as THREE.MeshStandardMaterial).color;
      const inst = new THREE.InstancedMesh(geom, toon(color), spots.length);
      const ink = new THREE.InstancedMesh(geom, outlineMaterial(0.32), spots.length);
      spots.forEach((p, i) => {
        q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), turns[i]);
        m.compose(p, q, new THREE.Vector3().setScalar(scales[i]));
        inst.setMatrixAt(i, m);
        ink.setMatrixAt(i, m);
      });
      inst.frustumCulled = ink.frustumCulled = false;
      this.group.add(inst, ink);
    }
  }

  private buildIndiaGate(model: GLTF) {
    const v = model.scene;
    stylize(v, { outline: 0.35 });
    const p = geo(...INDIA_GATE);
    v.scale.setScalar(0.12);
    v.position.set(p.x, 0, p.y);
    v.rotation.y = Math.PI / 2; // The arch faces west, down Kartavya Path.
    this.group.add(v);
  }

  // Low, weathered ridges in the spirit of the Aravallis, merged into a single draw (plus ink).
  private buildMesas() {
    const r = rng(99);
    const colors = ["#a8566f", "#7f3f62", "#b9695a", "#935069", "#633058"].map((c) => new THREE.Color(c));
    const flat: THREE.BufferGeometry[] = [];
    const smooth: THREE.BufferGeometry[] = [];
    const m = new THREE.Matrix4();
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2 + r() * 0.2;
      const d = 24 + r() * 26;
      const h = 1.6 + r() * 5;
      const rt = 1.5 + r() * 4;
      const base =
        r() < 0.7
          ? new THREE.IcosahedronGeometry(1, 1).scale(rt * 0.9, h * 0.55, rt * 0.8).translate(0, h * 0.2, 0)
          : new THREE.CylinderGeometry(rt, rt * (1.25 + r() * 0.4), h, 6 + Math.floor(r() * 3), 1).translate(0, h / 2, 0);
      m.makeRotationY(r() * Math.PI).setPosition(Math.cos(a) * d, 0, Math.sin(a) * d);
      const geom = (base.index ? base.toNonIndexed() : base).applyMatrix4(m);
      const facets = faceted(geom);
      const color = colors[i % colors.length];
      const rgb = new Float32Array(facets.getAttribute("position").count * 3);
      for (let v = 0; v < rgb.length; v += 3) color.toArray(rgb, v);
      facets.setAttribute("color", new THREE.BufferAttribute(rgb, 3));
      flat.push(facets);
      smooth.push(geom);
    }
    const strip = (g: THREE.BufferGeometry) => {
      for (const name of Object.keys(g.attributes)) if (!["position", "normal", "color"].includes(name)) g.deleteAttribute(name);
      return g;
    };
    const mesh = new THREE.Mesh(mergeGeometries(flat.map(strip)), toon("#ffffff", { vertexColors: true }));
    addOutline(mesh, 0.5, undefined, mergeGeometries(smooth.map(strip)));
    this.mesas.add(mesh);
  }

  private buildBeacons() {
    const pillarGeo = new THREE.CylinderGeometry(0.045, 0.06, 1, 14, 1, true).translate(0, 0.5, 0);
    const ringGeo = new THREE.RingGeometry(0.1, 0.15, 32).rotateX(-Math.PI / 2);
    const capGeo = new THREE.SphereGeometry(0.07, 16, 8);
    const pickGeo = new THREE.CylinderGeometry(0.3, 0.3, 1, 8).translate(0, 0.5, 0);
    const pickMat = new THREE.MeshBasicMaterial({ visible: false });
    LOCALITIES.filter((l) => l.name !== "Delhi").forEach((l, i) => {
      const p = geo(l.lat, l.lon);
      const group = new THREE.Group();
      group.position.set(p.x, 0, p.y);
      const material = new THREE.ShaderMaterial({
        uniforms: { color: { value: new THREE.Color("#8be9ed") }, opacity: { value: 1 }, time: { value: 0 } },
        vertexShader: pillarVert,
        fragmentShader: pillarFrag,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      });
      this.pillarMaterials.push(material);
      const pillar = new THREE.Mesh(pillarGeo, material);
      const cap = new THREE.Mesh(capGeo, new THREE.MeshBasicMaterial({ color: "#8be9ed" }));
      const ring = new THREE.Mesh(
        ringGeo,
        new THREE.MeshBasicMaterial({ color: "#8be9ed", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }),
      );
      ring.position.y = 0.04;
      const pick = new THREE.Mesh(pickGeo, pickMat);
      pick.userData.beacon = i;
      group.add(pillar, cap, ring, pick);
      this.beaconGroup.add(group);
      this.beacons.push({ name: l.name, group, pillar, cap, ring, pick, height: 0.01, target: 1.2, hot: 0, phase: i * 0.7 });
    });
  }

  setAqi(values: ({ aqi: number } | null)[], colorFor: (aqi: number) => string) {
    this.beacons.forEach((b, i) => {
      const v = values[i];
      if (!v) return;
      const c = new THREE.Color(colorFor(v.aqi));
      b.pillar.material.uniforms.color.value.copy(c);
      b.cap.material.color.copy(c);
      b.ring.material.color.copy(c);
      b.target = 0.45 + Math.min(v.aqi, 500) / 150;
    });
  }

  update(time: number, dt: number, visible: number) {
    this.groundUniforms.time.value = time;
    for (const m of this.roadMaterials) m.uniforms.time.value = time;
    this.beaconGroup.visible = visible > 0.01;
    for (const b of this.beacons) {
      const goal = b.target * visible * (1 + b.hot * 0.25);
      b.height += (goal - b.height) * Math.min(1, dt * 3);
      const h = Math.max(0.001, b.height);
      b.pillar.scale.y = h;
      b.pillar.scale.x = b.pillar.scale.z = 1 + b.hot * 0.8;
      b.pick.scale.y = h + 0.3;
      b.cap.position.y = h;
      b.cap.scale.setScalar((0.6 + 0.4 * visible) * (1 + b.hot * 0.6));
      const pulse = (time * 0.6 + b.phase) % 1;
      b.ring.scale.setScalar(1 + pulse * 2.4);
      b.ring.material.opacity = (1 - pulse) * visible;
      b.pillar.material.uniforms.time.value = time;
      b.pillar.material.uniforms.opacity.value = visible;
    }
  }
}
