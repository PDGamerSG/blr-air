import * as THREE from "three";

const vert = /* glsl */ `
  uniform float time;
  uniform float density;
  uniform float pixelRatio;
  uniform vec3 push; // xyz = UFO position, pushes motes away
  attribute float seed;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    vec3 p = position;
    float t = time * (0.05 + seed * 0.08);
    p.x += sin(t + seed * 40.0) * 1.4;
    p.y += sin(t * 0.7 + seed * 13.0) * 0.6;
    p.z += cos(t * 0.9 + seed * 27.0) * 1.1;
    vec3 d = p - push;
    float dl = length(d);
    p += normalize(d + 1e-4) * smoothstep(3.2, 0.0, dl) * 1.6;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float visible = step(seed, density);
    gl_PointSize = (14.0 + seed * 46.0) * pixelRatio / max(1.0, -mv.z) * visible;
    vAlpha = visible * smoothstep(60.0, 8.0, -mv.z) * smoothstep(0.4, 2.0, -mv.z);
    vSeed = seed;
  }
`;

const frag = /* glsl */ `
  uniform vec3 colorA;
  uniform vec3 colorB;
  uniform float opacity;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    float a = smoothstep(0.5, 0.0, d);
    // A few motes are hard-edged "specks" for the comic texture.
    if (vSeed > 0.93) a = step(d, 0.32);
    vec3 col = mix(colorA, colorB, vSeed);
    gl_FragColor = vec4(col, a * vAlpha * opacity);
    #include <colorspace_fragment>
  }
`;

export class Haze {
  points: THREE.Points;
  uniforms = {
    time: { value: 0 },
    density: { value: 0.4 },
    opacity: { value: 0.5 },
    pixelRatio: { value: 1 },
    push: { value: new THREE.Vector3(0, -100, 0) },
    colorA: { value: new THREE.Color("#b07a52") },
    colorB: { value: new THREE.Color("#ff6a2a") },
  };

  constructor(count: number) {
    const pos = new Float32Array(count * 3);
    const seed = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 34;
      pos[i * 3 + 1] = 0.3 + Math.pow(Math.random(), 1.4) * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 30 + 2;
      seed[i] = Math.random();
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("seed", new THREE.BufferAttribute(seed, 1));
    this.points = new THREE.Points(
      geo,
      new THREE.ShaderMaterial({
        uniforms: this.uniforms,
        vertexShader: vert,
        fragmentShader: frag,
        transparent: true,
        depthWrite: false,
      }),
    );
    this.points.frustumCulled = false;
    this.points.renderOrder = 5;
  }
}
