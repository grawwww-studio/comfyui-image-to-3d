#!/usr/bin/env python3
"""One photo -> textured GLB (PBR + UV) with Pixal3D or TRELLIS.2 on a running ComfyUI 0.37.0 (HTTP API only).

The API graph is hand-built from the bundled template `3d_pixal3d_trellis2_image_to_model` (ComfyUI 0.37.0):
BiRefNet matte -> ImageCropToMask -> (MoGe-2 FOV for Pixal3D) -> conditioning -> structure sampler -> shape 512 -> upsample
-> shape 1024+ -> texture sampler -> remesh (high-poly reference) -> decimate -> unwrap -> bake base/metal/rough + normal + AO
-> GLB. Two LODs (hi, lo) are produced from the same generation.

Example:
  COMFY_URL=http://127.0.0.1:8188 python3 scripts/gen3d.py --model pixal3d --image inputs/stool_met_c1670.jpg \
      --seed 777 --res 1024 --out runs/stool_pixal3d_s777
Offline (no server, no GPU): add --dump-graph to only write <out>/graph_api.json.
Stdlib only. Appends one row per run to --csv (default ./runs.csv).
Env: COMFY_URL (default http://127.0.0.1:8188), COMFY_CONTAINER (optional docker container name, enables RAM sampling).
"""
import argparse, csv, json, os, random, struct, subprocess, sys, threading, time, urllib.request, urllib.parse, uuid
from pathlib import Path

COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
CONTAINER = os.environ.get("COMFY_CONTAINER", "")   # optional: docker container running ComfyUI, for RAM sampling
UNET = {"pixal3d": "pixal3d_int8_convrot.safetensors", "trellis2": "trellis_2_int8_convrot.safetensors"}


def http(path, data=None, raw=False, timeout=60):
    """GET (data=None) or POST json to the ComfyUI server; returns bytes."""
    req = urllib.request.Request(COMFY + path, data=data, headers={"Content-Type": "application/json"} if data and not raw else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {path}: {e.read().decode()[:3000]}")


def upload(image: Path) -> str:
    """multipart upload to /upload/image; returns the name stored in ComfyUI's input/."""
    b = uuid.uuid4().hex
    name = f"i23d_{image.name}"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
        + image.read_bytes() + (f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{b}--\r\n").encode()
    req = urllib.request.Request(COMFY + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    return json.load(urllib.request.urlopen(req, timeout=120))["name"]


def graph(model, image_name, seed, res, tex, faces_hi, faces_lo, prefix):
    pix = model == "pixal3d"
    g = {}
    def n(i, cls, **inp):
        g[str(i)] = {"class_type": cls, "inputs": inp}
        return [str(i), 0]
    def o(ref, slot):  # another output slot of the same node
        return [ref[0], slot]
    img = n(1, "LoadImage", image=image_name)
    bgm = n(2, "LoadBackgroundRemovalModel", bg_removal_name="birefnet.safetensors")
    mask = n(3, "RemoveBackground", bg_removal_model=bgm, image=img)
    crop = n(4, "ImageCropToMask", images=img, masks=mask, width=1024, height=1024,
             pad_factor=1.1 if pix else 1.0, grow_mask=0, background="#000000")
    clipv = n(5, "CLIPVisionLoader", clip_name="dino_v3_L_naf_fp32.safetensors")
    if pix:
        moge = n(6, "LoadMoGeModel", model_name="moge_2_vitl_normal_fp16.safetensors")
        geo = n(7, "MoGeInference", moge_model=moge, image=crop, resolution_level=9, fov_x_degrees=0, batch_size=4,
                force_projection=True, apply_mask=True, refine_steps=3)
        fov = n(8, "MoGeGeometryToFOV", moge_geometry=geo, axis="horizontal", unit="degrees")
        n(9, "PreviewAny", source=fov)
        cond = n(10, "Pixal3DConditioning", clip_vision_model=clipv, image=crop, camera_angle_x=fov)
    else:
        cond = n(10, "Trellis2Conditioning", clip_vision_model=clipv, image=crop)
    pos, neg = cond, o(cond, 1)
    unet = n(11, "UNETLoader", unet_name=UNET[model], weight_dtype="default")
    vae_s = n(12, "VAELoader", vae_name="trellis_2_shape_vae_bf16.safetensors")
    vae_t = n(13, "VAELoader", vae_name="trellis_2_texture_vae_bf16.safetensors")
    # model chains copied from the template
    c1 = n(14, "CFGOverride", model=unet, cfg=1, start_percent=0.667, end_percent=1)
    r1 = n(15, "RescaleCFG", model=c1, multiplier=0.7)
    ms = n(16, "ModelSamplingSD3", model=r1, shift=5)
    c2 = n(17, "CFGOverride", model=unet, cfg=1, start_percent=0.769, end_percent=1)
    r2 = n(18, "RescaleCFG", model=c2, multiplier=0.5)
    # 1) sparse structure
    empty = n(20, "EmptyTrellis2LatentStructure", batch_size=1)
    ks_s = n(21, "KSampler", model=ms, seed=seed, steps=12, cfg=7.5, sampler_name="euler", scheduler="normal",
             positive=pos, negative=neg, latent_image=empty, denoise=1)
    vox = n(22, "VaeDecodeStructureTrellis2", samples=ks_s, vae=vae_s, resolution="32")
    # 2) shape 512 -> upsample -> shape
    sh = n(23, "Trellis2ShapeStage", positive=pos, negative=neg, voxel=vox)
    ks_a = n(24, "KSampler", model=r2, seed=seed, steps=20, cfg=7.5, sampler_name="euler", scheduler="normal",
             positive=sh, negative=o(sh, 1), latent_image=o(sh, 2), denoise=1)
    up = n(25, "Trellis2UpsampleStage", positive=sh, negative=o(sh, 1), shape_latent=ks_a, vae=vae_s, target_resolution=res)
    ks_b = n(26, "KSampler", model=r2, seed=seed, steps=12, cfg=7.5, sampler_name="euler", scheduler="simple",
             positive=up, negative=o(up, 1), latent_image=o(up, 2), denoise=1)
    shape = n(27, "VaeDecodeShapeTrellis", samples=ks_b, vae=vae_s)
    # 3) texture
    ts = n(28, "Trellis2TextureStage", positive=up, negative=o(up, 1), shape_latent=ks_b)
    ks_t = n(29, "KSampler", model=unet, seed=seed + 1, steps=12, cfg=1, sampler_name="euler", scheduler="normal",
             positive=ts, negative=o(ts, 1), latent_image=o(ts, 2), denoise=1)
    tex_v = n(30, "VaeDecodeTextureTrellis", samples=ks_t, vae=vae_t, shape_subdivides=o(shape, 1))
    # 4) mesh post: raw -> remesh (reference) -> per-LOD decimate/unwrap/bake
    info = n(31, "GetMeshInfo", mesh=shape)
    n(32, "PreviewAny", source=o(info, 1))
    rem = n(33, "RemeshMesh", mesh=info, resolution=768, sign_mode="udf", **{"sign_mode.qef": False, "sign_mode.drop_inverted_components": False,
            "sign_mode.drop_enclosed_components": False}, band=1, project_back=0, fix_poles=False, smooth_iters=20,
            drop_small_components=0.01, precluster_max_verts=20000000)
    base = 40
    for lod, faces in (("hi", faces_hi), ("lo", faces_lo)):
        k = base; base += 20
        dec = n(k, "DecimateMesh", mesh=rem, target_face_count=faces, placement_mode="midpoint")
        sm = n(k + 1, "MeshSmoothNormals", mesh=dec, crease_angle=180)
        unw = n(k + 2, "UnwrapMesh", mesh=sm, segmenter="pec", resolution=tex, padding=1, weld_distance=0.0002)
        bk = n(k + 3, "BakeTextureFromVoxel", mesh=unw, voxel_colors=tex_v, texture_size=tex, reference_mesh=shape)
        nm = n(k + 4, "BakeNormalMapFromMesh", low_poly=unw, high_poly=rem, resolution=tex, cage_distance=0.05, ignore_backfaces=True)
        ao = n(k + 5, "BakeAmbientOcclusion", low_poly=unw, high_poly=rem, resolution=min(tex, 1024), samples=64,
               max_distance=0.71, strength=1, bias=0.01)
        app = n(k + 6, "ApplyTextureToMesh", mesh=unw, base_color=bk, metallic=o(bk, 1), roughness=o(bk, 2), occlusion=ao, normal_map=nm)
        sm2 = n(k + 7, "MeshSmoothNormals", mesh=app, crease_angle=180)
        n(k + 8, "SaveGLB", mesh=sm2, filename_prefix=f"{prefix}_{lod}")
        if lod == "hi":
            uv = n(k + 9, "RenderUVAtlas", mesh=unw, resolution=2048)
            n(k + 10, "SaveImage", images=uv, filename_prefix=f"{prefix}_uv")
    return g


def glb_stats(path: Path):
    b = path.read_bytes()
    jl, _ = struct.unpack_from("<II", b, 12)
    j = json.loads(b[20:20 + jl])
    off = 20 + jl + 8
    binb = b[off:]
    tris = verts = 0
    for m in j.get("meshes", []):
        for p in m["primitives"]:
            if "indices" in p:
                tris += j["accessors"][p["indices"]]["count"] // 3
            verts += j["accessors"][p["attributes"]["POSITION"]]["count"]
    texs = []
    for im in j.get("images", []):
        bv = j["bufferViews"][im["bufferView"]]
        d = binb[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        if d[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", d[16:24])
        elif d[:4] == b"RIFF":  # webp
            w = h = 0
        else:
            w = h = 0
        texs.append(f"{im.get('mimeType','?').split('/')[-1]}:{w}x{h}")
    mats = j.get("materials", [])
    return dict(tris=tris, verts=verts, textures=";".join(texs), n_materials=len(mats), file_mb=round(path.stat().st_size / 1e6, 2))


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = False; self.vram = []; self.ram = []
    def run(self):
        last = 0
        while not self.stop:
            try:
                v = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
                self.vram.append(int(v.split()[0]))
            except Exception:
                pass
            if CONTAINER and time.time() - last > 2.5:
                last = time.time()
                try:
                    s = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", CONTAINER], capture_output=True, text=True, timeout=15).stdout.split("/")[0].strip()
                    val = float(''.join(c for c in s if c in '0123456789.'))
                    self.ram.append(val * (1024 if "GiB" in s else 1 if "MiB" in s else 1 / 1024))
                except Exception:
                    pass
            time.sleep(0.4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=["pixal3d", "trellis2"], required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--res", type=int, default=1024, help="Trellis2UpsampleStage target resolution (1024..2048, step 128)")
    ap.add_argument("--tex", type=int, default=2048, help="texture/atlas size of the baked maps")
    ap.add_argument("--faces-hi", type=int, default=150000)
    ap.add_argument("--faces-lo", type=int, default=50000)
    ap.add_argument("--out", required=True, help="output dir for this run (GLBs, uv atlas, run.json)")
    ap.add_argument("--csv", default="runs.csv", help="append one row per run here")
    ap.add_argument("--dump-graph", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    image = Path(a.image).resolve()
    tag = f"{image.stem}_{a.model}_s{a.seed}_r{a.res}"
    prefix = f"image-to-3d/{tag}"
    if a.dump_graph:   # offline: no upload, no server
        g = graph(a.model, f"i23d_{image.name}", a.seed, a.res, a.tex, a.faces_hi, a.faces_lo, prefix)
        (out / "graph_api.json").write_text(json.dumps(g, indent=1)); print("wrote", out / "graph_api.json"); return
    g = graph(a.model, upload(image), a.seed, a.res, a.tex, a.faces_hi, a.faces_lo, prefix)
    (out / "graph_api.json").write_text(json.dumps(g, indent=1))
    http("/free", json.dumps({"unload_models": True, "free_memory": True}).encode())
    time.sleep(3)
    smp = Sampler(); smp.start(); time.sleep(3)
    base_vram = smp.vram[-1] if smp.vram else 0
    base_ram = smp.ram[-1] if smp.ram else 0
    t0 = time.time()
    pid = json.loads(http("/prompt", json.dumps({"prompt": g, "client_id": "image-to-3d"}).encode()))["prompt_id"]
    hist = None
    while True:
        time.sleep(2)
        h = json.loads(http(f"/history/{pid}"))
        if pid in h and h[pid].get("status", {}).get("completed") is not None and (h[pid]["status"]["completed"] or h[pid]["status"]["status_str"] == "error"):
            hist = h[pid]; break
        if time.time() - t0 > 3600:
            raise SystemExit("timeout")
    secs = time.time() - t0
    time.sleep(1); smp.stop = True; smp.join(timeout=20)
    (out / "history.json").write_text(json.dumps(hist, indent=1))
    st = hist["status"]
    if st["status_str"] != "success":
        msgs = [m for m in st["messages"] if m[0] == "execution_error"]
        print("FAILED:", json.dumps(msgs)[:2000]); http("/free", json.dumps({"unload_models": True, "free_memory": True}).encode())
        sys.exit(1)
    # collect outputs
    fov = ""; meshinfo = ""
    files = {}
    for nid, o in hist["outputs"].items():
        for key, vals in o.items():
            if key == "text":
                t = vals[0] if isinstance(vals, list) else vals
                if nid == "9": fov = t
                if nid == "32": meshinfo = t
            elif isinstance(vals, list):
                for v in vals:
                    if isinstance(v, dict) and "filename" in v:
                        files[nid] = v
    rows = {}
    for nid, v in files.items():
        q = urllib.parse.urlencode({"filename": v["filename"], "subfolder": v.get("subfolder", ""), "type": v.get("type", "output")})
        dst = out / v["filename"]
        dst.write_bytes(http("/view?" + q, timeout=600)); rows[nid] = dst
    row = dict(tag=tag, model=a.model, photo=image.stem, seed=a.seed, res=a.res, tex=a.tex, seconds=round(secs, 1),
               vram_peak_mb=max(smp.vram or [0]), vram_base_mb=base_vram, vram_delta_mb=max(smp.vram or [0]) - base_vram,
               ram_peak_mb=round(max(smp.ram or [0])), ram_base_mb=round(base_ram), fov_deg=fov.strip(), meshinfo=meshinfo.strip().replace("\n", " | "))
    for lod in ("hi", "lo"):
        f = next((p for p in rows.values() if p.name.endswith(f"_{lod}_00001_.glb") or f"_{lod}_" in p.name and p.suffix == ".glb"), None)
        if f:
            s = glb_stats(f)
            row.update({f"{lod}_{k}": v for k, v in s.items()}); row[f"{lod}_file"] = f.name
    (out / "run.json").write_text(json.dumps(row, indent=1))
    new = not Path(a.csv).exists()
    with open(a.csv, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()), extrasaction="ignore")
        if new: w.writeheader()
        w.writerow(row)
    print(json.dumps(row, indent=1))
    http("/free", json.dumps({"unload_models": True, "free_memory": True}).encode())


if __name__ == "__main__":
    main()
