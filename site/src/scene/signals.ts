import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { addOutline, faceted, toon } from "./toon";

// Four floating "specimens" for AQI, PM2.5, rain and heat that orbit the UFO.
export class Signals {
  root = new THREE.Group();
  items: THREE.Group[] = [];
  active = 0;
  private spin = 0;

  constructor() {
    this.items = [this.aqi(), this.particles(), this.rain(), this.heat()];
    this.items.forEach((g) => this.root.add(g));
  }

  private aqi() {
    const g = new THREE.Group();
    const planetGeo = new THREE.IcosahedronGeometry(0.62, 2);
    const planet = new THREE.Mesh(faceted(planetGeo), toon("#ff6a2a"));
    addOutline(planet, 0.6, undefined, planetGeo);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.98, 0.07, 10, 64), toon("#ffe62b"));
    ring.rotation.x = Math.PI / 2.4;
    addOutline(ring, 0.5);
    const moon = new THREE.Mesh(new THREE.SphereGeometry(0.13, 16, 12), toon("#7cff5b"));
    moon.position.set(1.1, 0.25, 0);
    addOutline(moon, 0.5);
    g.add(planet, ring, moon);
    g.userData.spin = (t: number) => {
      planet.rotation.y = t * 0.6;
      moon.position.set(Math.cos(t * 1.4) * 1.1, 0.25, Math.sin(t * 1.4) * 1.1);
    };
    return g;
  }

  private particles() {
    const g = new THREE.Group();
    const smoothGeo = new THREE.IcosahedronGeometry(1, 0);
    const geo = faceted(smoothGeo);
    const mats = [toon("#5a3a2e"), toon("#b07a52"), toon("#ead9c8")];
    const bits: THREE.Mesh[] = [];
    for (let i = 0; i < 26; i++) {
      const m = new THREE.Mesh(geo, mats[i % 3]);
      const r = 0.06 + Math.random() * 0.12;
      m.scale.setScalar(r);
      m.userData.seed = Math.random() * 100;
      m.userData.rad = 0.25 + Math.random() * 0.7;
      addOutline(m, 0.9, undefined, smoothGeo);
      bits.push(m);
      g.add(m);
    }
    g.userData.spin = (t: number) => {
      bits.forEach((b) => {
        const s = b.userData.seed as number;
        const r = b.userData.rad as number;
        b.position.set(Math.cos(t * 0.8 + s) * r, Math.sin(t * 1.1 + s * 2) * 0.6, Math.sin(t * 0.8 + s) * r);
        b.rotation.set(t + s, t * 0.7, 0);
      });
    };
    return g;
  }

  private rain() {
    const g = new THREE.Group();
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 24; i++) {
      const t = i / 24;
      const y = 1 - t * 1.9;
      const r = t < 0.55 ? Math.sin((t / 0.55) * Math.PI * 0.5) * 0.55 * Math.pow(t / 0.55, 0.6) : Math.sin(((1 - t) / 0.45) * Math.PI * 0.5) * 0.55 + 0.001;
      pts.push(new THREE.Vector2(Math.max(0.001, r), y));
    }
    pts.reverse(); // bottom-to-top so lathe normals face outward
    const drop = new THREE.Mesh(new THREE.LatheGeometry(pts, 40), toon("#8be9ed"));
    drop.position.y = 0.3;
    addOutline(drop, 0.6);
    const shine = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 8), new THREE.MeshBasicMaterial({ color: "#ffffff" }));
    shine.position.set(-0.2, 0.05, 0.45);
    g.add(drop, shine);
    const minis: THREE.Mesh[] = [];
    for (let i = 0; i < 6; i++) {
      const m = drop.clone();
      m.scale.setScalar(0.18);
      m.userData.seed = i / 6;
      minis.push(m);
      g.add(m);
    }
    g.userData.spin = (t: number) => {
      drop.rotation.y = t * 0.5;
      minis.forEach((m) => {
        const k = (t * 0.5 + (m.userData.seed as number)) % 1;
        const a = (m.userData.seed as number) * Math.PI * 2;
        m.position.set(Math.cos(a) * 0.95, 0.9 - k * 1.8, Math.sin(a) * 0.95);
      });
    };
    return g;
  }

  private heat() {
    const g = new THREE.Group();
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.5, 32, 16), toon("#ffe62b"));
    addOutline(core, 0.6);
    g.add(core);
    // One merged mesh for all the sun's spikes instead of ~40 separate cones.
    const cones: THREE.BufferGeometry[] = [];
    const dirs = new THREE.IcosahedronGeometry(1, 1).getAttribute("position");
    const seen = new Set<string>();
    const q = new THREE.Quaternion();
    for (let i = 0; i < dirs.count; i++) {
      const v = new THREE.Vector3().fromBufferAttribute(dirs, i).normalize();
      const key = v.toArray().map((n) => n.toFixed(2)).join();
      if (seen.has(key)) continue;
      seen.add(key);
      q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v);
      cones.push(new THREE.ConeGeometry(0.11, 0.42, 6).translate(0, 0.72, 0).applyQuaternion(q));
    }
    const coneSmooth = mergeGeometries(cones);
    const spikes = new THREE.Mesh(faceted(coneSmooth), toon("#ff5b9e"));
    addOutline(spikes, 0.6, undefined, coneSmooth);
    g.add(spikes);
    g.userData.spin = (t: number) => {
      spikes.rotation.y = t * 0.4;
      spikes.rotation.z = t * 0.25;
      const p = 1 + Math.sin(t * 3) * 0.05;
      core.scale.setScalar(p);
    };
    return g;
  }

  update(time: number, dt: number, visible: number, cameraPos: THREE.Vector3) {
    this.root.visible = visible > 0.01;
    if (!this.root.visible) return;
    // Rotate the ring so the active specimen swings to the side facing the camera.
    const toCam = Math.atan2(cameraPos.x - this.root.position.x, cameraPos.z - this.root.position.z);
    const goal = toCam - (this.active / 4) * Math.PI * 2 - 0.6;
    let diff = goal - this.spin;
    diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    this.spin += diff * Math.min(1, dt * 3);
    this.items.forEach((g, i) => {
      const a = this.spin + (i / 4) * Math.PI * 2;
      const isActive = i === this.active;
      const r = 2.7;
      g.position.set(Math.sin(a) * r, Math.sin(time * 1.2 + i) * 0.18 + (isActive ? 0.2 : 0), Math.cos(a) * r);
      const target = (isActive ? 0.95 : 0.5) * visible;
      const s = g.scale.x + (target - g.scale.x) * Math.min(1, dt * 5);
      g.scale.setScalar(Math.max(0.0001, s));
      (g.userData.spin as (t: number) => void)(time);
    });
  }
}
