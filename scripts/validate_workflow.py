#!/usr/bin/env python3
"""Validate the workflows without running them (no GPU, no generation).

  python3 scripts/validate_workflow.py [--offline]

Online (needs ComfyUI up, COMFY_URL default http://127.0.0.1:8188, reads only GET /object_info and the model lists):
  1. every node class_type exists in /object_info and every input name is known;
  2. the UI workflow is converted back to API format and must equal workflows/<model>_image_to_3d.api.json exactly
     (so what you drag into the frontend is what gen3d.py runs);
  3. combo values (model file names, sampler names, ...) are among the options the server offers. A missing model file
     is reported as a WARNING (you have not downloaded it yet), anything else is an error.
--offline: only JSON/link integrity (every link ends on an existing node, ids unique), no server.
Exit code 0 = all good.
"""
import json, os, sys, urllib.request
from pathlib import Path

URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
WF = Path(__file__).resolve().parent.parent / "workflows"
PRIM = {"INT", "FLOAT", "STRING", "BOOLEAN"}
errors, warnings = [], []


def is_widget(s):
    return isinstance(s[0], list) or s[0] in PRIM or s[0] in ("COMBO", "COMFY_DYNAMICCOMBO_V3") or (len(s) > 1 and isinstance(s[1], dict) and s[1].get("socketless"))


def options(s):
    if isinstance(s[0], list):
        return s[0]
    if s[0] == "COMBO":
        return s[1].get("options")
    return None


def ui_to_api(ui, oi):
    links = {l[0]: l for l in ui["links"]}
    api = {}
    for nd in ui["nodes"]:
        info = oi[nd["type"]]
        order = info["input_order"]["required"] + info["input_order"].get("optional", [])
        spec = {**info["input"]["required"], **info["input"].get("optional", {})}
        linked = {i["name"]: i["link"] for i in nd["inputs"] if i.get("link") is not None}
        ws = list(nd["widgets_values"]); k = 0; inp = {}
        for name in order:
            s = spec[name]
            if is_widget(s):
                v = ws[k]; k += 1
                if s[0] == "COMFY_DYNAMICCOMBO_V3":
                    opt = next(o for o in s[1]["options"] if o["key"] == v)
                    subs = [(sub, ss) for grp in ("required", "optional") for sub, ss in opt.get("inputs", {}).get(grp, {}).items()]
                    inp[name] = v
                    for sub, _ in subs:
                        inp[f"{name}.{sub}"] = ws[k]; k += 1
                    continue
                if name in linked:
                    l = links[linked[name]]; inp[name] = [str(l[1]), l[2]]
                else:
                    inp[name] = v
                if len(s) > 1 and s[1].get("control_after_generate"): k += 1
                if len(s) > 1 and (s[1].get("image_upload") or s[1].get("video_upload")): k += 1
            elif name in linked:
                l = links[linked[name]]; inp[name] = [str(l[1]), l[2]]
        if k != len(ws):
            errors.append(f"node {nd['id']} {nd['type']}: consumed {k} of {len(ws)} widget values")
        api[str(nd["id"])] = {"class_type": nd["type"], "inputs": inp}
    return api


def main():
    offline = "--offline" in sys.argv
    oi = None if offline else json.load(urllib.request.urlopen(URL + "/object_info", timeout=60))
    for model in ("pixal3d", "trellis2"):
        ui = json.load(open(WF / f"{model}_image_to_3d.json")); api = json.load(open(WF / f"{model}_image_to_3d.api.json"))
        ids = [n["id"] for n in ui["nodes"]]
        if len(ids) != len(set(ids)): errors.append(f"{model}: duplicate node ids")
        for l in ui["links"]:
            if l[1] not in ids or l[3] not in ids: errors.append(f"{model}: link {l[0]} points to a missing node")
        for k, n in api.items():
            for v in n["inputs"].values():
                if isinstance(v, list) and v[0] not in api: errors.append(f"{model}: API node {k} links to missing {v[0]}")
        if offline:
            print(f"{model}: {len(ui['nodes'])} UI nodes, {len(ui['links'])} links, {len(api)} API nodes (structure only)"); continue
        for k, n in api.items():
            if n["class_type"] not in oi:
                errors.append(f"{model}: node type {n['class_type']} not in /object_info"); continue
            info = oi[n["class_type"]]
            spec = {**info["input"]["required"], **info["input"].get("optional", {})}
            for name, v in n["inputs"].items():
                base = name.split(".")[0]
                if base not in spec:
                    errors.append(f"{model}: {n['class_type']} has no input {base}"); continue
                if "." not in name and not isinstance(v, list):
                    opts = options(spec[name])
                    if opts is not None and v not in opts:
                        (warnings if name.endswith("_name") or name == "image" else errors).append(
                            f"{model}: node {k} {n['class_type']}.{name}={v!r} not offered by this server")
        back = ui_to_api(ui, oi)
        if back != api:
            diff = [(k, i) for k in api for i in api[k]["inputs"] if back.get(k, {}).get("inputs", {}).get(i) != api[k]["inputs"][i]]
            errors.append(f"{model}: UI -> API round trip differs from the API graph at {diff[:6]}")
        print(f"{model}: {len(ui['nodes'])} UI nodes, {len(api)} API nodes, round trip {'OK' if back == api else 'DIFFERS'}")
    for w in warnings: print("WARNING", w)
    for e in errors: print("ERROR", e)
    print("RESULT", "FAIL" if errors else "OK", f"({len(warnings)} warnings, {len(errors)} errors)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
