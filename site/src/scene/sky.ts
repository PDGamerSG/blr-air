import * as THREE from "three";

const vert = /* glsl */ `
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_Position.z = gl_Position.w; // pin to the far plane
  }
`;

// Gradient sky with hashed twinkling stars and retro 70s horizon stripes for dawn.
const frag = /* glsl */ `
  uniform vec3 top;
  uniform vec3 mid;
  uniform vec3 bottom;
  uniform float stars;
  uniform float stripes;
  uniform float time;
  varying vec3 vDir;

  float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }

  void main() {
    float h = vDir.y;
    vec3 col = mix(bottom, mid, smoothstep(-0.05, 0.22, h));
    col = mix(col, top, smoothstep(0.22, 0.75, h));

    vec3 cell = floor(vDir * 180.0);
    float r = hash(cell);
    float star = step(0.9965, r) * smoothstep(0.02, 0.25, h);
    float tw = 0.55 + 0.45 * sin(time * (1.5 + r * 4.0) + r * 60.0);
    col += vec3(1.0, 0.97, 0.9) * star * tw * stars;

    // Horizon bands: pink / orange / yellow / cyan, like a 70s paperback cover.
    float band = smoothstep(0.0, 0.03, h) * (1.0 - smoothstep(0.16, 0.2, h));
    float idx = floor(h * 40.0);
    vec3 bandCol = mod(idx, 4.0) < 1.0 ? vec3(1.0, 0.36, 0.62)
                 : mod(idx, 4.0) < 2.0 ? vec3(1.0, 0.42, 0.16)
                 : mod(idx, 4.0) < 3.0 ? vec3(1.0, 0.9, 0.17) : vec3(0.55, 0.91, 0.93);
    float wobble = step(0.5, fract(h * 40.0 + 0.15 * sin(atan(vDir.z, vDir.x) * 6.0 + time * 0.3)));
    col = mix(col, bandCol, band * stripes * 0.55 * wobble);

    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
  }
`;

export class Sky {
  mesh: THREE.Mesh;
  uniforms = {
    top: { value: new THREE.Color() },
    mid: { value: new THREE.Color() },
    bottom: { value: new THREE.Color() },
    stars: { value: 1 },
    stripes: { value: 0 },
    time: { value: 0 },
  };
  moon: THREE.Sprite;
  sun: THREE.Sprite;

  constructor() {
    this.mesh = new THREE.Mesh(
      new THREE.SphereGeometry(400, 48, 24),
      new THREE.ShaderMaterial({
        uniforms: this.uniforms,
        vertexShader: vert,
        fragmentShader: frag,
        side: THREE.BackSide,
        depthWrite: false,
        fog: false,
      }),
    );
    this.mesh.renderOrder = -10;
    this.moon = new THREE.Sprite(new THREE.SpriteMaterial({ map: moonTexture(), fog: false, transparent: true, depthWrite: false }));
    this.moon.scale.setScalar(26);
    this.moon.position.set(-60, 70, -170);
    this.sun = new THREE.Sprite(new THREE.SpriteMaterial({ map: sunTexture(), fog: false, transparent: true, depthWrite: false }));
    this.sun.scale.setScalar(60);
    this.sun.position.set(30, 6, -190);
  }

  add(scene: THREE.Scene) {
    scene.add(this.mesh, this.moon, this.sun);
  }
}

function canvas(size: number) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  return [c, c.getContext("2d")!] as const;
}

function moonTexture() {
  const [c, g] = canvas(256);
  g.fillStyle = "#ff8a4c";
  g.beginPath();
  g.arc(128, 128, 100, 0, Math.PI * 2);
  g.fill();
  g.lineWidth = 8;
  g.strokeStyle = "#080b0d";
  g.stroke();
  g.fillStyle = "rgba(122, 5, 16, 0.35)";
  for (const [x, y, r] of [[95, 100, 18], [150, 150, 26], [160, 90, 11], [100, 165, 12]]) {
    g.beginPath();
    g.arc(x, y, r, 0, Math.PI * 2);
    g.fill();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// Spiky comic sun, as on the Stranger Builds stage deck.
function sunTexture() {
  const [c, g] = canvas(512);
  g.translate(256, 256);
  const spikes = 28;
  g.beginPath();
  for (let i = 0; i <= spikes * 2; i++) {
    const r = i % 2 ? 150 : 236 - (i % 4) * 22;
    const a = (i / (spikes * 2)) * Math.PI * 2;
    g.lineTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  g.fillStyle = "#ff5b9e";
  g.fill();
  g.beginPath();
  g.arc(0, 0, 138, 0, Math.PI * 2);
  g.fillStyle = "#ffe62b";
  g.fill();
  g.lineWidth = 10;
  g.strokeStyle = "#080b0d";
  g.stroke();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
