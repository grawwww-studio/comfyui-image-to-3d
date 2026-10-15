"""Blender 4.5 headless renderer for the GLBs made by gen3d.py (stock Blender 4.5.x, no add-ons).
blender -b --factory-startup --python render_glb.py -- <glb> <outdir> <mode> [front_az_deg] [size] [samples] [level_deg] [frames]
(scripts/render.sh wraps this.) GPU (OptiX/CUDA) is used if Blender finds one, otherwise CPU.
modes: stills   -> front, q34, rear, top (+ side) PNG
       uv       -> uv_layout.png, the UV atlas drawn as lines (2048 px)
       turn     -> 72 frames turn_000..071.png (360 deg, linear)
       wire     -> wire_q34.png, wire_front.png (wireframe override, for the 50k LOD)
       test     -> 4 low-sample azimuths az0/90/180/270 to find which side faces the camera
Neutral studio light, plain grey background, soft shadow (shadow-catcher plane composited over flat grey)."""
import bpy, sys, math, os
from mathutils import Vector

glb, out, mode = sys.argv[sys.argv.index("--") + 1:][:3]
rest = sys.argv[sys.argv.index("--") + 4:]
front_az = float(rest[0]) if len(rest) > 0 else 0.0
SIZE = int(rest[1]) if len(rest) > 1 else 1080
SAMPLES = int(rest[2]) if len(rest) > 2 else 64
NFRAMES = int(rest[4]) if len(rest) > 4 else 72   # turntable frames over 360 deg (real frames, no retiming)
LEVEL = float(rest[3]) if len(rest) > 3 else 0.0   # pitch (deg, about X) to level a camera-space mesh (Pixal3D)
os.makedirs(out, exist_ok=True)
GREY = (0.36, 0.36, 0.37)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in sc.objects if o.type == "MESH"]
if mode == "uv":   # UV layout, drawn with numpy (bpy.ops.uv.export_layout needs a GUI, not available with -b)
    import numpy as np
    N = 2048; img = np.zeros((N, N), dtype=np.float32)
    for ob in meshes:
        me = ob.data; me.calc_loop_triangles()
        tl = np.empty(len(me.loop_triangles) * 3, dtype=np.int32); me.loop_triangles.foreach_get("loops", tl)
        uv = np.empty(len(me.loops) * 2, dtype=np.float32); me.uv_layers.active.data.foreach_get("uv", uv)
        p = uv.reshape(-1, 2)[tl].reshape(-1, 3, 2) * (N - 1)
        for a_, b_ in ((0, 1), (1, 2), (2, 0)):
            p0, p1 = p[:, a_], p[:, b_]
            n = np.maximum(np.abs(p1 - p0).max(1).astype(np.int32) + 1, 2)
            t = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
            f = (t / np.repeat(n - 1, n))[:, None]
            q = np.repeat(p0, n, 0) + f * (np.repeat(p1, n, 0) - np.repeat(p0, n, 0))
            x = np.clip(q[:, 0].round().astype(int), 0, N - 1); y = np.clip(q[:, 1].round().astype(int), 0, N - 1)
            img[y, x] = 1.0
    rgba = np.empty((N, N, 4), dtype=np.float32)
    rgba[..., :3] = (0.06 + 0.9 * img)[..., None]; rgba[..., 3] = 1.0
    im = bpy.data.images.new("uv", N, N); im.pixels.foreach_set(rgba.ravel()); im.filepath_raw = os.path.join(out, "uv_layout.png")
    im.file_format = "PNG"; im.save()
    print("RENDER_DONE", mode, flush=True); sys.exit(0)
piv = bpy.data.objects.new("piv", None); sc.collection.objects.link(piv)      # rotation about the vertical axis at the origin
hold = bpy.data.objects.new("hold", None); sc.collection.objects.link(hold); hold.parent = piv   # scale + offset
for o in meshes:
    o.parent = hold
bpy.context.view_layer.update()

def bbox():
    import numpy as np   # exact AABB from the vertices (o.bound_box corners over-estimate after a rotation)
    lo = np.full(3, 1e9); hi = np.full(3, -1e9)
    for o in meshes:
        n = len(o.data.vertices); co = np.empty(n * 3, dtype=np.float32); o.data.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        p = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        lo = np.minimum(lo, p.min(0)); hi = np.maximum(hi, p.max(0))
    return Vector(lo.tolist()), Vector(hi.tolist())
hold.rotation_euler = (math.radians(LEVEL), 0, 0)
bpy.context.view_layer.update()
mn, mx = bbox()
s = 1.0 / (mx.z - mn.z)            # unit height (z is up after the glTF import)
hold.scale = (s, s, s)
bpy.context.view_layer.update()
mn, mx = bbox()
hold.location = Vector((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z))   # centre xy on the axis, base on z=0
bpy.context.view_layer.update()
mn, mx = bbox()
size = mx - mn
print("BBOX", [round(v,3) for v in mn], [round(v,3) for v in mx], [(o.name, len(o.data.vertices)) for o in meshes], flush=True)
center = (mn + mx) / 2
r = size.length / 2

# floor shadow catcher
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
floor = bpy.context.object; floor.is_shadow_catcher = True

# world + lights
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.8, 0.8, 0.8, 1); bg.inputs[1].default_value = 0.9
def area(loc, energy, sz, shadow=True):
    d = bpy.data.lights.new("a", "AREA"); d.energy = energy; d.size = sz; d.use_shadow = shadow
    ob = bpy.data.objects.new("a", d); sc.collection.objects.link(ob); ob.location = loc
    tr = ob.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
tgt = bpy.data.objects.new("tgt", None); sc.collection.objects.link(tgt); tgt.location = center
area((2.2, -2.6, 3.2), 300, 1.5)
area((-3.0, -1.5, 1.8), 100, 2.5, False)
area((0.5, 3.0, 2.5), 120, 2.5, False)

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 60
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
tc = cam.constraints.new("TRACK_TO"); tc.target = tgt; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
fov = 2 * math.atan(18 / cam_d.lens)
rxy = math.hypot(size.x, size.y) / 2
dist = max(rxy, size.z / 2) / math.tan(fov / 2) * 1.12 + rxy * 0.6

def set_cam(elev_deg, az_deg=0.0, d=None):
    d = d or dist
    e = math.radians(elev_deg); a = math.radians(az_deg)   # camera sits at -Y (azimuth 0), rotate around Z
    cam.location = center + Vector((d * math.cos(e) * math.sin(a), -d * math.cos(e) * math.cos(a), d * math.sin(e)))

def rot(deg):
    piv.rotation_euler = (0, 0, math.radians(deg + front_az))

# render settings
sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.device = "CPU"
try:
    cp = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            cp.compute_device_type = kind; cp.get_devices()
            devs = [d for d in cp.devices if d.type == kind]
            if devs:
                for d in cp.devices: d.use = d.type == kind
                sc.cycles.device = "GPU"; print("DEVICE", kind, [d.name for d in devs], flush=True)
                if kind == "OPTIX": sc.cycles.denoiser = "OPTIX"
                break
        except Exception as e:
            print("dev err", e)
except Exception as e:
    print("no gpu", e)
sc.render.resolution_x = sc.render.resolution_y = SIZE
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
# composite over flat grey
sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
rl = nt.nodes.new("CompositorNodeRLayers"); ov = nt.nodes.new("CompositorNodeAlphaOver"); col = nt.nodes.new("CompositorNodeRGB")
col.outputs[0].default_value = (*GREY, 1); cmp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(col.outputs[0], ov.inputs[1]); nt.links.new(rl.outputs["Image"], ov.inputs[2]); nt.links.new(ov.outputs[0], cmp.inputs[0])

def shot(name, elev, az):
    set_cam(elev); rot(az)
    sc.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)

if mode == "test":
    sc.cycles.samples = 8
    for az in (0, 90, 180, 270):
        shot(f"az{az}", 12, az)
elif mode == "stills":
    shot("front", 25, 0); shot("q34", 22, 40); shot("side", 12, 90); shot("rear", 12, 180); shot("top", 89, 0)
elif mode == "turn":
    for i in range(NFRAMES):
        shot(f"turn_{i:03d}", 18, i * 360.0 / NFRAMES)
elif mode == "wire":
    floor.hide_render = True
    sc.render.film_transparent = False
    mat = bpy.data.materials.new("wire"); mat.use_nodes = True; nt2 = mat.node_tree; nt2.nodes.clear()
    wf = nt2.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs[0].default_value = 1.0
    em = nt2.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = (0.02, 0.02, 0.02, 1)
    df = nt2.nodes.new("ShaderNodeBsdfDiffuse"); df.inputs[0].default_value = (0.86, 0.86, 0.84, 1)
    mix = nt2.nodes.new("ShaderNodeMixShader"); outn = nt2.nodes.new("ShaderNodeOutputMaterial")
    nt2.links.new(wf.outputs[0], mix.inputs[0]); nt2.links.new(df.outputs[0], mix.inputs[1]); nt2.links.new(em.outputs[0], mix.inputs[2])
    nt2.links.new(mix.outputs[0], outn.inputs[0])
    sc.view_layers[0].material_override = mat
    # compositor: opaque render, no alpha-over needed
    nt.links.new(rl.outputs["Image"], cmp.inputs[0])
    shot("wire_front", 12, 0); shot("wire_q34", 22, 40)
print("RENDER_DONE", mode, flush=True)
