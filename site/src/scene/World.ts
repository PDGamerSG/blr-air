import * as THREE from "three";
import { GLTFLoader, type GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { City } from "./city";
import { Haze } from "./haze";
import { Signals } from "./signals";
import { Sky } from "./sky";
import { Gaali, Ufo } from "./ufo";
import { cloneState, mixState, SCENES, type SceneState } from "./state";

interface Key {
  y: number;
  state: SceneState;
}

const smooth = (t: number) => t * t * (3 - 2 * t);

export class World {
  renderer: THREE.WebGLRenderer;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1200);
  timer = new THREE.Timer();
  sky = new Sky();
  haze: Haze;
  city!: City;
  ufo!: Ufo;
  gaali!: Gaali;
  signals = new Signals();
  pointer = new THREE.Vector2();
  paused = false;
  lite: boolean;

  private keys: Key[] = [];
  private current: SceneState = cloneState(SCENES.hero.start);
  private target: SceneState = cloneState(SCENES.hero.start);
  private look = new THREE.Vector3();
  private time = 0;
  private raycaster = new THREE.Raycaster();
  private sun = new THREE.DirectionalLight("#fff1dc", 2.2);
  private hemi = new THREE.HemisphereLight("#8be9ed", "#5d2457", 1.3);
  private hovered = -1;
  private ndc = new THREE.Vector2(-9, -9);
  onBeaconHover?: (index: number) => void;

  constructor(canvas: HTMLCanvasElement) {
    this.lite = matchMedia("(max-width: 760px), (pointer: coarse)").matches;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: !this.lite, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, this.lite ? 1.5 : 1.75));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene.fog = new THREE.Fog("#3a2040", 14, 70);
    this.haze = new Haze(this.lite ? 2200 : 5200);
    this.sun.position.set(6, 10, 7);
    this.scene.add(this.sun, this.hemi);
    this.sky.add(this.scene);
    this.scene.add(this.haze.points);
  }

  async load(onProgress: (p: number) => void) {
    const manager = new THREE.LoadingManager();
    manager.onProgress = (_url, loaded, total) => onProgress(loaded / total);
    const loader = new GLTFLoader(manager);
    const base = import.meta.env.BASE_URL;
    const [ufo, gaali, vidhana, tree] = (await Promise.all(
      ["ufo", "gaali", "vidhana", "tree"].map((n) => loader.loadAsync(`${base}models/${n}.glb`)),
    )) as GLTF[];
    this.city = new City({ tree, vidhana }, this.lite);
    this.scene.add(this.city.group);
    this.ufo = new Ufo(ufo, gaali);
    this.ufo.add(this.scene);
    this.gaali = new Gaali(gaali.scene, 0.6);
    this.gaali.root.rotation.y = -0.35;
    this.scene.add(this.gaali.root);
    this.scene.add(this.signals.root);
    this.resize();
    // Compile shaders up front so the first scroll doesn't hitch.
    this.renderer.compile(this.scene, this.camera);
  }

  // Build scroll keyframes from the live layout of [data-scene] sections.
  layout() {
    const vh = innerHeight;
    this.keys = [];
    document.querySelectorAll<HTMLElement>("[data-scene]").forEach((el) => {
      const def = SCENES[el.dataset.scene!];
      if (!def) return;
      const top = el.getBoundingClientRect().top + scrollY;
      const span = Math.max(0, el.offsetHeight - vh);
      // Non-sticky sections reach their state while they scroll into the middle.
      const startY = el.hasAttribute("data-sticky") ? top : top - vh * 0.35;
      this.keys.push({ y: startY, state: def.start });
      this.keys.push({ y: startY + Math.max(span, vh * 0.3), state: def.end ?? def.start });
    });
    this.keys.sort((a, b) => a.y - b.y);
  }

  scrollTo(y: number) {
    const k = this.keys;
    if (!k.length) return;
    if (y <= k[0].y) this.target = k[0].state;
    else if (y >= k[k.length - 1].y) this.target = k[k.length - 1].state;
    else {
      let i = 0;
      while (i < k.length - 1 && y > k[i + 1].y) i++;
      const a = k[i];
      const b = k[i + 1];
      const t = b.y === a.y ? 1 : (y - a.y) / (b.y - a.y);
      this.target = mixState(a.state, b.state, smooth(Math.min(1, Math.max(0, t))));
    }
  }

  snap() {
    this.current = cloneState(this.target);
  }

  setPointer(x: number, y: number) {
    this.pointer.set((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1);
    this.ndc.copy(this.pointer);
  }

  resize() {
    const w = innerWidth;
    const h = innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.haze.uniforms.pixelRatio.value = this.renderer.getPixelRatio() * (h / 900);
  }

  // Click on the UFO: a beam pulse that shoves the haze aside.
  hitUfo(): boolean {
    if (!this.ufo) return false;
    this.raycaster.setFromCamera(this.ndc, this.camera);
    const hit = this.raycaster.intersectObject(this.ufo.craft, true).length > 0;
    if (hit) this.ufo.zap = 1;
    return hit;
  }

  setBeamColor(hex: string) {
    this.scanColor = hex;
  }

  private scanColor: string | null = null;
  private scanTint = new THREE.Color();

  setActiveSignal(i: number) {
    this.signals.active = i;
  }

  setHotBeacon(i: number) {
    if (!this.city) return;
    this.city.beacons.forEach((b, j) => (b.hot = j === i ? 1 : 0));
  }

  projectBeacons(out: { x: number; y: number; visible: boolean }[]) {
    if (!this.city) return;
    const v = new THREE.Vector3();
    this.city.beacons.forEach((b, i) => {
      v.set(b.group.position.x, b.height + 0.15, b.group.position.z).project(this.camera);
      out[i] = {
        x: (v.x * 0.5 + 0.5) * innerWidth,
        y: (-v.y * 0.5 + 0.5) * innerHeight,
        visible: v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05,
      };
    });
  }

  get beaconsVisible() {
    return this.current.beacons;
  }

  tick() {
    this.timer.update();
    const dt = Math.min(0.05, this.timer.getDelta());
    if (!this.paused) this.time += dt;
    const k = 1 - Math.exp(-dt * 4.5);
    this.current = mixState(this.current, this.target, k);
    const s = this.current;
    this.apply(s, dt);
    this.renderer.render(this.scene, this.camera);
  }

  private apply(s: SceneState, dt: number) {
    const t = this.time;
    const cam = this.camera;
    cam.position.set(...s.cam);
    // gentle parallax from the pointer
    cam.position.x += this.pointer.x * 0.35;
    cam.position.y += this.pointer.y * 0.2;
    this.look.set(...s.look);
    cam.lookAt(this.look);
    const portrait = cam.aspect < 0.9;
    cam.fov = portrait ? s.fov * 1.45 : s.fov;
    const w = innerWidth;
    const h = innerHeight;
    const shift = portrait ? 0 : s.shift;
    cam.setViewOffset(w, h, -shift * w * 0.5, 0, w, h);
    cam.updateProjectionMatrix();

    this.sky.mesh.position.copy(cam.position);
    this.sky.uniforms.top.value.set(s.skyTop);
    this.sky.uniforms.mid.value.set(s.skyMid);
    this.sky.uniforms.bottom.value.set(s.skyBottom);
    this.sky.uniforms.stars.value = s.stars;
    this.sky.uniforms.stripes.value = s.stripes;
    this.sky.uniforms.time.value = t;
    (this.sky.moon.material as THREE.SpriteMaterial).opacity = s.moon;
    this.sky.moon.visible = s.moon > 0.01;
    (this.sky.sun.material as THREE.SpriteMaterial).opacity = s.sun;
    this.sky.sun.visible = s.sun > 0.01;
    this.sky.sun.position.set(cam.position.x + 40, cam.position.y + s.sunY, cam.position.z - 190);
    this.sky.sun.material.rotation = t * 0.05;
    this.sky.moon.position.set(cam.position.x + 18, cam.position.y + 60, cam.position.z - 170);

    const fog = this.scene.fog as THREE.Fog;
    fog.color.set(s.skyBottom);
    fog.near = s.fogNear;
    fog.far = s.fogFar;

    this.haze.uniforms.time.value = t;
    this.haze.uniforms.density.value = s.haze;
    this.haze.uniforms.opacity.value = s.hazeOpacity;
    this.haze.uniforms.colorA.value.set(s.hazeA);
    this.haze.uniforms.colorB.value.set(s.hazeB);

    this.hemi.intensity = 1.1 * s.light;
    this.sun.intensity = 2.0 * s.light;

    if (!this.city) return;
    this.city.buildingUniforms.rise.value = s.city;
    this.city.buildingUniforms.night.value = s.night;
    this.city.buildingUniforms.light.value = 0.75 + 0.35 * s.light;
    this.city.groundUniforms.light.value = 0.7 + 0.4 * s.light;
    this.city.groundUniforms.grid.value = 0.4 + 0.6 * s.night;
    this.city.update(t, dt, s.beacons);

    const ufo = this.ufo;
    ufo.root.position.set(...s.ufo);
    ufo.root.scale.setScalar(s.ufoScale);
    ufo.root.rotation.y = t * 0.15;
    ufo.beamUniforms.color.value.set(s.beamColor);
    if (this.scanColor) ufo.beamUniforms.color.value.lerp(this.scanTint.set(this.scanColor), s.scan);
    ufo.update(t, dt, s.beam, this.pointer);
    this.haze.uniforms.push.value.set(s.ufo[0], s.ufo[1] - 1.5, s.ufo[2]);

    this.signals.root.position.set(...s.ufo);
    this.signals.update(t, dt, s.signals, cam.position);

    this.gaali.root.visible = s.gaali > 0.01;
    this.gaali.root.position.set(s.ufo[0], -1.8 * (1 - s.gaali), s.ufo[2]);
    this.gaali.root.scale.setScalar(Math.max(0.001, s.gaali));
    this.gaali.maskOff = s.mask;
    this.gaali.update(t, dt, this.pointer);
    this.gaali.root.position.y += Math.abs(Math.sin(t * 2.4)) * 0.08 * s.mask;

    this.updateHover(s);
  }

  private updateHover(s: SceneState) {
    if (s.beacons < 0.5) {
      if (this.hovered !== -1) {
        this.hovered = -1;
        this.onBeaconHover?.(-1);
      }
      return;
    }
    this.raycaster.setFromCamera(this.ndc, this.camera);
    const hits = this.raycaster.intersectObjects(this.city.beacons.map((b) => b.pick), false);
    const idx = hits.length ? (hits[0].object.userData.beacon as number) : -1;
    if (idx !== this.hovered) {
      this.hovered = idx;
      this.onBeaconHover?.(idx);
    }
  }
}
