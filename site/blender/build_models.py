"""Builds the landing page's stylised models and exports them as GLB.

Run headless from the site directory:
    blender --background --factory-startup --python blender/build_models.py -- public/models

Materials only carry flat base colours; the page re-shades everything with a toon
material and ink outlines, keyed by material name (glow*, glass*).
"""

import math
import os
import sys

import bmesh
import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "public/models"
os.makedirs(OUT, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def linear(hex_color):
    hex_color = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hex_color[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def material(name, color, emission=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = linear(color)
    bsdf.inputs["Roughness"].default_value = 0.7
    if emission:
        bsdf.inputs["Emission Color"].default_value = linear(emission)
        bsdf.inputs["Emission Strength"].default_value = 1.5
    m.diffuse_color = linear(color)
    return m


def finish(obj, mat, name, smooth=True, subdiv=0):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if smooth:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_flat()
    if subdiv:
        mod = obj.modifiers.new("subd", "SUBSURF")
        mod.levels = subdiv
        mod.render_levels = subdiv
    return obj


def sphere(name, mat, r=1.0, loc=(0, 0, 0), scale=(1, 1, 1), seg=48, rings=24, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc)
    obj = bpy.context.active_object
    obj.scale = scale
    return finish(obj, mat, name, smooth)


def ico(name, mat, r=1.0, loc=(0, 0, 0), scale=(1, 1, 1), subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=r, location=loc)
    obj = bpy.context.active_object
    obj.scale = scale
    return finish(obj, mat, name, smooth=False)


def cylinder(name, mat, r=1.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), verts=32, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    return finish(bpy.context.active_object, mat, name, smooth)


def cone(name, mat, r1=1.0, r2=0.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), verts=32, smooth=True):
    bpy.ops.mesh.primitive_cone_add(
        vertices=verts, radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot
    )
    return finish(bpy.context.active_object, mat, name, smooth)


def torus(name, mat, major=1.0, minor=0.1, loc=(0, 0, 0), rot=(0, 0, 0), maj_seg=64, min_seg=12):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major,
        minor_radius=minor,
        major_segments=maj_seg,
        minor_segments=min_seg,
        location=loc,
        rotation=rot,
    )
    return finish(bpy.context.active_object, mat, name)


def box(name, mat, size=(1, 1, 1), loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.scale = size
    return finish(obj, mat, name, smooth=False)


def tube(name, mat, points, radius=0.05):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    curve.resolution_u = 16
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, p in zip(spline.bezier_points, points):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.active_object
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def prism(name, mat, width, height, depth, loc):
    # Triangular gable: a front triangle extruded along Y.
    w, d = width / 2, depth / 2
    verts = [(-w, -d, 0), (w, -d, 0), (0, -d, height), (-w, d, 0), (w, d, 0), (0, d, height)]
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    return finish(obj, mat, name, smooth=False)


def join(name, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    # Pivot at the model origin so the page can spin/animate parts in place.
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def export(filename):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT, filename),
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_texcoords=False,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )


# --- UFO: classic saucer, Stranger Builds magenta with yellow running lights ---
def build_ufo():
    reset()
    hull = material("hull", "#c04f93")
    hull_top = material("hull_top", "#e27ab4")
    belly = material("belly", "#5d2457")
    rim = material("rim", "#24122a")
    glass = material("glass_dome", "#8be9ed")
    lights = material("glow_lights", "#ffe62b", "#ffe62b")
    emitter = material("glow_emitter", "#c8fbff", "#8be9ed")
    tip = material("glow_tip", "#ff5b9e", "#ff5b9e")

    parts = [
        sphere("saucer", hull, 2.2, (0, 0, 0), (1, 1, 0.26), 72, 32),
        sphere("deck", hull_top, 1.35, (0, 0, 0.32), (1, 1, 0.34), 64, 24),
        sphere("underbelly", belly, 1.55, (0, 0, -0.2), (1, 1, 0.3), 64, 24),
        torus("rim", rim, 2.16, 0.075, (0, 0, 0.02)),
        torus("deck_ring", rim, 1.06, 0.05, (0, 0, 0.62)),
        torus("belly_ring", rim, 0.92, 0.06, (0, 0, -0.55)),
    ]
    for i in range(14):
        a = i / 14 * math.tau
        parts.append(sphere(f"light{i}", lights, 0.11, (math.cos(a) * 1.78, math.sin(a) * 1.78, 0.25), seg=16, rings=8))
    for i in range(3):
        a = i / 3 * math.tau + 0.4
        leg = cylinder(
            f"leg{i}", rim, 0.045, 0.7, (math.cos(a) * 1.15, math.sin(a) * 1.15, -0.72),
            (math.cos(a + math.pi / 2) * 0.35, math.sin(a + math.pi / 2) * 0.35, 0), 12,
        )
        foot = sphere(f"foot{i}", rim, 0.1, (math.cos(a) * 1.27, math.sin(a) * 1.27, -1.03), (1, 1, 0.45), 16, 8)
        parts.extend([leg, foot])
    bulbs = [p for p in parts if p.name.startswith("light")]
    shell = [p for p in parts if not p.name.startswith("light")]
    body = join("UfoBody", shell)
    join("UfoLights", bulbs)

    dome = sphere("UfoDome", glass, 0.98, (0, 0, 0.62), (1, 1, 0.92), 48, 24)
    # Keep only the upper hemisphere of the dome.
    bm = bmesh.new()
    bm.from_mesh(dome.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.01], context="VERTS")
    bm.to_mesh(dome.data)
    bm.free()

    cylinder("UfoEmitter", emitter, 0.62, 0.08, (0, 0, -0.6), verts=48)
    antenna = cylinder("antenna", rim, 0.03, 0.42, (0, 0, 1.72), verts=10)
    bulb = sphere("UfoTip", tip, 0.09, (0, 0, 1.96), seg=16, rings=8)
    bpy.ops.object.select_all(action="DESELECT")
    antenna.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    export("ufo.glb")


# --- Gaali (ಗಾಳಿ, "air"): one-eyed sky reader in a gas mask ---
def build_gaali():
    reset()
    skin = material("skin", "#8dfc6a")
    belly = material("belly", "#d7ffb8")
    eye_white = material("eye_white", "#fff7ef")
    pupil = material("pupil", "#080b0d")
    shine = material("glow_shine", "#ffffff", "#ffffff")
    mask = material("mask", "#26252e")
    filt = material("filter", "#ffe62b")
    strap = material("strap", "#e20b1b")
    sensor = material("glow_sensor", "#ff5b9e", "#ff5b9e")

    body = sphere("GaaliBody", skin, 1.0, (0, 0, 1.15), (1, 0.95, 1.12), 64, 32)
    tummy = sphere("tummy", belly, 0.62, (0, -0.55, 0.85), (1, 0.5, 1.0), 48, 24)
    feet = [sphere(f"foot{s}", skin, 0.32, (s * 0.42, -0.12, 0.14), (1, 1.3, 0.55), 32, 16) for s in (-1, 1)]
    arms = [
        sphere(f"arm{s}", skin, 0.22, (s * 1.0, -0.15, 0.95), (0.8, 0.8, 1.5), 24, 12) for s in (-1, 1)
    ]
    join("GaaliBody", [body, tummy, *feet, *arms])

    sphere("GaaliEye", eye_white, 0.46, (0, -0.7, 1.6), (1, 0.72, 1), 48, 24)
    sphere("GaaliPupil", pupil, 0.16, (0.03, -1.02, 1.56), (1, 0.5, 1.15), 32, 16)
    sphere("GaaliShine", shine, 0.05, (0.1, -1.1, 1.64), seg=12, rings=6)

    lid = sphere("lid", skin, 0.47, (0, -0.68, 1.78), (1.06, 0.78, 0.55), 32, 16)
    lid.name = "GaaliLid"

    ant = []
    for s in (-1, 1):
        ant.append(tube(f"ant{s}", skin, [(s * 0.3, 0, 2.15), (s * 0.55, 0.05, 2.7), (s * 0.9, 0.15, 3.0)], 0.045))
        ant.append(sphere(f"tip{s}", sensor, 0.13, (s * 0.9, 0.15, 3.02), seg=20, rings=10))
    join("GaaliAntennae", ant)

    snout = cylinder("snout", mask, 0.3, 0.42, (0, -0.98, 1.05), (math.radians(90), 0, 0), 32)
    grill = torus("grill", filt, 0.24, 0.05, (0, -1.2, 1.05), (math.radians(90), 0, 0), 32, 8)
    cans = []
    for s in (-1, 1):
        cans.append(cylinder(f"can{s}", mask, 0.2, 0.28, (s * 0.5, -0.86, 0.92), (math.radians(90), 0, s * math.radians(35)), 24))
        cans.append(cylinder(f"cap{s}", filt, 0.21, 0.06, (s * 0.58, -0.98, 0.92), (math.radians(90), 0, s * math.radians(35)), 24))
    band = torus("band", strap, 0.98, 0.05, (0, 0.02, 1.15), (math.radians(8), 0, 0), 64, 8)
    join("GaaliMask", [snout, grill, *cans, band])
    export("gaali.glb")


# --- Vidhana Soudha, simplified to read at a distance ---
def build_vidhana():
    reset()
    stone = material("stone", "#ead9c8")
    shade = material("stone_shade", "#c9b49c")
    dome = material("dome", "#f2e6d4")
    window = material("window", "#3a2b3f")
    finial = material("glow_finial", "#ffe62b", "#ffe62b")

    parts = [
        box("plinth", shade, (6.4, 2.6, 0.3), (0, 0, 0.15)),
        box("main", stone, (5.8, 2.0, 1.1), (0, 0, 0.85)),
        box("cornice", shade, (6.0, 2.2, 0.12), (0, 0, 1.46)),
        box("tower", stone, (1.6, 1.4, 0.8), (0, 0, 1.92)),
        box("tower_cap", shade, (1.75, 1.55, 0.1), (0, 0, 2.36)),
        box("portico", stone, (1.9, 0.7, 1.35), (0, -1.3, 0.95)),
        box("steps1", shade, (2.6, 0.5, 0.1), (0, -1.9, 0.05)),
        box("steps2", shade, (2.3, 0.4, 0.2), (0, -1.75, 0.1)),
    ]
    parts.append(prism("pediment", shade, 2.1, 0.5, 0.8, (0, -1.3, 1.62)))
    for i in range(6):
        x = -0.8 + i * 0.32
        parts.append(cylinder(f"col{i}", stone, 0.07, 1.25, (x, -1.68, 0.85), verts=12))
    for row in (0.65, 1.1):
        for i in range(14):
            x = -2.7 + i * 0.41
            if -1.1 < x < 1.1:
                continue
            parts.append(box(f"win{row}{i}", window, (0.16, 0.05, 0.24), (x, -1.01, row)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box(f"pav{sx}{sy}", stone, (0.6, 0.6, 0.45), (sx * 2.6, sy * 0.7, 1.72)))
            parts.append(sphere(f"cdome{sx}{sy}", dome, 0.3, (sx * 2.6, sy * 0.7, 1.95), (1, 1, 1.1), 24, 12))
    body = join("Vidhana", parts)
    drum = cylinder("drum", shade, 0.62, 0.35, (0, 0, 2.58), verts=40)
    big = sphere("bigdome", dome, 0.7, (0, 0, 2.75), (1, 1, 1.05), 48, 24)
    spike = cone("spike", shade, 0.08, 0.0, 0.35, (0, 0, 3.6), verts=12)
    join("Vidhana", [body, drum, big, spike])
    sphere("VidhanaFinial", finial, 0.07, (0, 0, 3.8), seg=12, rings=6)
    export("vidhana.glb")


# --- Pink trumpet tree (Tabebuia rosea), Bengaluru's spring signature ---
def build_tree():
    reset()
    bark = material("bark", "#5a2d1e")
    pink = material("bloom", "#ff5b9e")
    light = material("bloom_light", "#ff9ccb")
    trunk = cone("trunk", bark, 0.14, 0.07, 1.2, (0, 0, 0.6), verts=10, smooth=False)
    b1 = cone("b1", bark, 0.06, 0.03, 0.7, (0.22, 0, 1.2), (0, math.radians(35), 0), 8, smooth=False)
    b2 = cone("b2", bark, 0.06, 0.03, 0.7, (-0.2, 0.1, 1.25), (math.radians(-15), math.radians(-35), 0), 8, smooth=False)
    join("TreeTrunk", [trunk, b1, b2])
    blobs = [
        ((0, 0, 1.75), 0.62, pink),
        ((0.5, 0.1, 1.55), 0.45, light),
        ((-0.48, 0.15, 1.6), 0.46, pink),
        ((0.15, -0.38, 1.6), 0.42, light),
        ((-0.1, 0.42, 1.62), 0.4, pink),
        ((0.1, 0.05, 2.15), 0.38, light),
    ]
    canopy = [ico(f"c{i}", m, r, p, subdivisions=1) for i, (p, r, m) in enumerate(blobs)]
    join("TreeCanopy", canopy)
    export("tree.glb")


build_ufo()
build_gaali()
build_vidhana()
build_tree()
print("exported to", os.path.abspath(OUT))
