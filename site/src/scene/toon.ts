import * as THREE from "three";

// Three-step ramp gives the flat, screen-printed comic look.
const ramp = (() => {
  const data = new Uint8Array([90, 170, 255]);
  const tex = new THREE.DataTexture(data, data.length, 1, THREE.RedFormat);
  tex.minFilter = tex.magFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.needsUpdate = true;
  return tex;
})();

export function toon(color: THREE.ColorRepresentation, extra: THREE.MeshToonMaterialParameters = {}) {
  return new THREE.MeshToonMaterial({ color, gradientMap: ramp, ...extra });
}

const outlineVert = /* glsl */ `
  uniform float thickness;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vec3 transformed = position;
    vec3 n = normal;
    #ifdef USE_INSTANCING
      transformed = (instanceMatrix * vec4(transformed, 1.0)).xyz;
      n = mat3(instanceMatrix) * n;
    #endif
    vec4 mvPosition = modelViewMatrix * vec4(transformed, 1.0);
    vec3 vn = normalize(normalMatrix * n);
    // Scale by depth so the ink line keeps a near-constant screen width.
    mvPosition.xyz += vn * thickness * max(0.6, -mvPosition.z) * 0.01;
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`;

const outlineFrag = /* glsl */ `
  uniform vec3 color;
  uniform float opacity;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    gl_FragColor = vec4(color, opacity);
    #include <fog_fragment>
  }
`;

export function outlineMaterial(thickness = 0.5, color = "#080b0d") {
  return new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([
      THREE.UniformsLib.fog,
      { thickness: { value: thickness }, color: { value: new THREE.Color(color) }, opacity: { value: 1 } },
    ]),
    vertexShader: outlineVert,
    fragmentShader: outlineFrag,
    side: THREE.BackSide,
    fog: true,
  });
}

// Flat per-face normals for a cut-paper, faceted look (toon has no flatShading flag).
export function faceted(geometry: THREE.BufferGeometry) {
  const flat = geometry.index ? geometry.toNonIndexed() : geometry.clone();
  flat.computeVertexNormals();
  return flat;
}

// Inverted-hull ink outline. Pass the smooth source geometry for faceted meshes,
// otherwise split face normals leave gaps in the hull.
export function addOutline(mesh: THREE.Mesh, thickness = 0.5, color = "#080b0d", geometry = mesh.geometry) {
  const hull = new THREE.Mesh(geometry, outlineMaterial(thickness, color));
  hull.name = `${mesh.name}__ink`;
  hull.raycast = () => {};
  mesh.add(hull);
  return hull;
}

// Re-shade a Blender export: flat toon by default, unlit for glow*, translucent for glass*.
export function stylize(root: THREE.Object3D, { outline = 0.55 } = {}) {
  const meshes: THREE.Mesh[] = [];
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh);
  });
  for (const mesh of meshes) {
    const src = mesh.material as THREE.MeshStandardMaterial;
    const name = src.name || "";
    const color = src.color ? src.color.clone() : new THREE.Color("#ffffff");
    if (name.startsWith("glow")) {
      mesh.material = new THREE.MeshBasicMaterial({ color: color.multiplyScalar(1.4), fog: true });
    } else if (name.startsWith("glass")) {
      mesh.material = toon(color, { transparent: true, opacity: 0.38, depthWrite: false });
      mesh.renderOrder = 2;
    } else {
      mesh.material = toon(color);
    }
    (mesh.material as THREE.Material).name = name;
    if (!name.startsWith("glass") && outline > 0) addOutline(mesh, outline);
  }
  return root;
}
