import * as THREE from "three";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { LOCALITIES } from "../config";
import { addOutline, faceted, outlineMaterial, stylize, toon } from "./toon";

// Equirectangular projection of Bengaluru onto the ground plane (1 unit ≈ 2.4 km).
const LAT0 = 12.965;
const LON0 = 77.655;
const K = 46;
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
  [12.935, 77.665, 0.42, 1.8],
  [12.945, 77.74, 0.28, 1.3],
  [12.982, 77.62, 0.16, 1.2],
  [13.045, 77.59, 0.2, 1.4],
  [12.908, 77.615, 0.2, 1.2],
  [12.922, 77.64, 0.14, 1.1],
  [13.01, 77.574, 0.11, 1.3],
  [13.09, 77.583, 0.24, 1.5],
  [12.947, 77.585, 0.08, 1],
];

const PARKS: [number, number, number][] = [
  [12.9763, 77.5929, 0.42], // Cubbon Park
  [12.9507, 77.5848, 0.36], // Lalbagh
];

const VIDHANA: [number, number] = [12.9796, 77.5907];

const ROADS: [number, number][][] = [
  // Outer Ring Road (closed below)
  [
    [13.0358, 77.597], [13.0405, 77.623], [13.025, 77.64], [13.006, 77.695], [12.956, 77.701], [12.927, 77.678],
    [12.92, 77.65], [12.917, 77.623], [12.908, 77.6], [12.918, 77.56], [12.944, 77.523], [12.965, 77.515],
    [13.028, 77.54], [13.04, 77.56],
  ],
  [[12.917, 77.623], [12.845, 77.66], [12.79, 77.7]], // Hosur Road
  [[13.0358, 77.597], [13.1005, 77.5963], [13.16, 77.63]], // Bellary Road
  [[12.98, 77.62], [13.006, 77.695], [13.025, 77.77]], // Old Madras Road
  [[12.956, 77.701], [12.9698, 77.75], [12.985, 77.8]], // Whitefield
  [[12.92, 77.65], [12.86, 77.786], [12.83, 77.83]], // Sarjapur Road
  [[12.977, 77.572], [12.944, 77.523], [12.92, 77.47]], // Mysore Road
  [[12.977, 77.572], [13.028, 77.54], [13.07, 77.48]], // Tumkur Road
  [[12.95, 77.585], [12.9, 77.6], [12.83, 77.6]], // Bannerghatta Road
  [[12.977, 77.572], [12.9796, 77.5907], [12.9756, 77.6066], [12.9784, 77.6408], [12.956, 77.701]], // core
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

  constructor(models: { tree: GLTF; vidhana: GLTF }, lite: boolean) {
    this.buildGround();
    this.buildLakesAndParks();
    this.buildBuildings(lite ? 1100 : 2400);
    this.buildRoads();
    this.buildTrees(models.tree, lite ? 40 : 80);
    this.buildVidhana(models.vidhana);
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

  private buildLakesAndParks() {
    const water = new THREE.MeshBasicMaterial({ color: "#1f6670", fog: true });
    const shore = new THREE.MeshBasicMaterial({ color: "#8be9ed", fog: true });
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
    for (const [lat, lon, r, s] of LAKES) {
      const p = geo(lat, lon);
      if (Math.hypot((x - p.x) / s, z - p.y) < r * 1.2 + pad) return true;
    }
    for (const [lat, lon, r] of PARKS) {
      const p = geo(lat, lon);
      if (Math.hypot(x - p.x, z - p.y) < r * 1.1 + pad) return true;
    }
    const v = geo(...VIDHANA);
    return Math.hypot(x - v.x, z - v.y) < 0.42;
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
    const towers = ["Whitefield", "Electronic City", "Bellandur", "Marathahalli", "Hebbal", "Koramangala"].map((n) => {
      const l = LOCALITIES.find((x) => x.name === n)!;
      return geo(l.lat, l.lon);
    });
    const cbd = geo(12.9716, 77.6);
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
      for (let i = 0; i < count * 0.32; i++) {
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

  private buildVidhana(model: GLTF) {
    const v = model.scene;
    stylize(v, { outline: 0.35 });
    const p = geo(...VIDHANA);
    v.scale.setScalar(0.085);
    v.position.set(p.x, 0, p.y);
    v.rotation.y = Math.PI * 0.08;
    this.group.add(v);
  }

  // Deccan-plateau buttes ringing the city, merged into a single draw (plus ink).
  private buildMesas() {
    const r = rng(99);
    const colors = ["#b94a7d", "#8a3466", "#cf5f55", "#a54a6a", "#6d2c5a"].map((c) => new THREE.Color(c));
    const flat: THREE.BufferGeometry[] = [];
    const smooth: THREE.BufferGeometry[] = [];
    const m = new THREE.Matrix4();
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2 + r() * 0.2;
      const d = 24 + r() * 26;
      const h = 2 + r() * 7;
      const rt = 1.5 + r() * 4;
      const base =
        r() < 0.3
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
    LOCALITIES.filter((l) => l.name !== "Bengaluru").forEach((l, i) => {
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
      b.target = 0.45 + v.aqi / 45;
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
