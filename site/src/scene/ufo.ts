import * as THREE from "three";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { stylize } from "./toon";

const beamVert = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalV;
  varying vec3 vViewDir;
  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormalV = normalize(normalMatrix * normal);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

// Tractor beam: bright at the emitter, scanlines falling to the ground, rim glow.
const beamFrag = /* glsl */ `
  uniform vec3 color;
  uniform float intensity;
  uniform float time;
  varying vec2 vUv;
  varying vec3 vNormalV;
  varying vec3 vViewDir;
  void main() {
    float down = vUv.y; // 1 at emitter, 0 at ground
    float fall = 0.55 + 0.45 * step(0.45, fract(down * 18.0 + time * 1.6));
    float rim = pow(1.0 - abs(dot(vNormalV, vViewDir)), 1.5);
    float a = (0.12 + 0.55 * rim) * mix(0.35, 1.0, down) * fall * intensity;
    gl_FragColor = vec4(color * (1.0 + rim), a);
    #include <colorspace_fragment>
  }
`;

export class Ufo {
  root = new THREE.Group();
  craft = new THREE.Group();
  lights?: THREE.Object3D;
  beam: THREE.Mesh<THREE.CylinderGeometry, THREE.ShaderMaterial>;
  spot: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>;
  pilot: Gaali;
  beamUniforms = {
    color: { value: new THREE.Color("#ffe62b") },
    intensity: { value: 0 },
    time: { value: 0 },
  };
  tilt = new THREE.Vector2();
  zap = 0;

  constructor(ufo: GLTF, gaali: GLTF) {
    const model = stylize(ufo.scene, { outline: 0.5 });
    this.lights = model.getObjectByName("UfoLights") ?? undefined;
    this.craft.add(model);
    this.pilot = new Gaali(gaali.scene.clone(true), 0.4);
    this.pilot.root.position.set(0, 0.5, 0.05);
    this.craft.add(this.pilot.root);
    this.root.add(this.craft);

    this.beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.55, 2.4, 1, 48, 1, true).translate(0, -0.5, 0),
      new THREE.ShaderMaterial({
        uniforms: this.beamUniforms,
        vertexShader: beamVert,
        fragmentShader: beamFrag,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      }),
    );
    this.beam.renderOrder = 6;
    this.spot = new THREE.Mesh(
      new THREE.RingGeometry(0.2, 2.5, 48).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({
        color: "#ffe62b",
        transparent: true,
        opacity: 0,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
  }

  add(scene: THREE.Scene) {
    scene.add(this.root, this.beam, this.spot);
  }

  update(time: number, dt: number, beam: number, pointer: THREE.Vector2) {
    const bob = Math.sin(time * 1.3) * 0.12;
    this.craft.position.y = bob;
    this.tilt.lerp(pointer, Math.min(1, dt * 2.5));
    this.craft.rotation.z = -this.tilt.x * 0.22 + Math.sin(time * 0.9) * 0.04;
    this.craft.rotation.x = this.tilt.y * 0.16 + Math.cos(time * 0.7) * 0.03;
    if (this.lights) this.lights.rotation.y = time * 0.9;
    this.pilot.update(time, dt, pointer);

    this.zap = Math.max(0, this.zap - dt * 1.4);
    const strength = Math.min(1.6, beam + this.zap * 1.5);
    this.beamUniforms.time.value = time;
    this.beamUniforms.intensity.value = strength;
    const world = new THREE.Vector3();
    this.craft.getWorldPosition(world);
    const scale = this.root.scale.x;
    const top = world.y - 0.55 * scale;
    this.beam.visible = strength > 0.01 && top > 0.05;
    this.beam.position.set(world.x, top, world.z);
    this.beam.scale.set(scale * (0.9 + this.zap * 0.4), top, scale * (0.9 + this.zap * 0.4));
    this.spot.position.set(world.x, 0.05, world.z);
    this.spot.scale.setScalar(scale * (0.9 + 0.08 * Math.sin(time * 4)));
    this.spot.material.opacity = Math.min(0.5, strength * 0.35);
    this.spot.material.color.copy(this.beamUniforms.color.value);
  }
}

// The mascot. Eye follows the pointer, blinks, antennae sway, mask can come off.
export class Gaali {
  root = new THREE.Group();
  model: THREE.Object3D;
  eye: THREE.Object3D[] = [];
  pupil?: THREE.Object3D;
  mask?: THREE.Object3D;
  antennae?: THREE.Object3D;
  maskOff = 0;
  private blinkAt = 2;
  private pupilHome = new THREE.Vector3();
  private maskHome = new THREE.Vector3();

  constructor(model: THREE.Object3D, scale: number) {
    this.model = stylize(model, { outline: 0.45 });
    this.model.scale.setScalar(scale);
    this.root.add(this.model);
    for (const n of ["GaaliEye", "GaaliPupil", "GaaliShine"]) {
      const o = this.model.getObjectByName(n);
      if (o) this.eye.push(o);
    }
    this.pupil = this.model.getObjectByName("GaaliPupil") ?? undefined;
    if (this.pupil) this.pupilHome.copy(this.pupil.position);
    this.mask = this.model.getObjectByName("GaaliMask") ?? undefined;
    if (this.mask) this.maskHome.copy(this.mask.position);
    this.antennae = this.model.getObjectByName("GaaliAntennae") ?? undefined;
  }

  update(time: number, dt: number, pointer: THREE.Vector2) {
    if (this.pupil) {
      this.pupil.position.x = this.pupilHome.x + pointer.x * 0.09;
      this.pupil.position.y = this.pupilHome.y + pointer.y * 0.06;
    }
    this.blinkAt -= dt;
    const blink = this.blinkAt < 0.12 ? Math.abs(Math.sin((this.blinkAt / 0.12) * Math.PI)) : 1;
    if (this.blinkAt < 0) this.blinkAt = 2 + Math.random() * 3.5;
    for (const e of this.eye) e.scale.y = Math.max(0.08, blink);
    if (this.antennae) this.antennae.rotation.z = Math.sin(time * 2.2) * 0.05;
    if (this.mask) {
      const k = this.maskOff;
      this.mask.visible = k < 0.98;
      this.mask.position.copy(this.maskHome).add(new THREE.Vector3(k * 0.6, k * 2.6, k * 1.2));
      this.mask.rotation.set(-k * 2.2, k * 0.8, k * 1.4);
      this.mask.scale.setScalar(1 - k * 0.6);
    }
  }
}
