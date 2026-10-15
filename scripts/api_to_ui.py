#!/usr/bin/env python3
"""Convert an API-format ComfyUI graph to a UI-format workflow (nodes + links + layout) so it can be opened,
read and screenshotted in the frontend. Needs a running ComfyUI (reads /object_info; set COMFY_URL) (reads /object_info).

  python3 scripts/api_to_ui.py in_api.json out_ui.json [--titles titles.json] [--bypass 24,31]
"""
import json, os, sys, urllib.request
from collections import defaultdict

URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
PRIM = {"INT", "FLOAT", "STRING", "BOOLEAN"}
_OI = None


def object_info():
    global _OI
    if _OI is None:
        _OI = json.load(urllib.request.urlopen(URL + "/object_info", timeout=60))
    return _OI


def is_widget(spec):
    t = spec[0]
    return isinstance(t, list) or t in PRIM or t in ("COMBO", "COMFY_DYNAMICCOMBO_V3") or (len(spec) > 1 and isinstance(spec[1], dict) and spec[1].get("socketless"))   # newer nodes declare combos as ("COMBO", {"options": [...]})


def convert(api, titles=None, bypass=(), groups=None, colors=None, col_w=400, max_h=1000):
    oi = object_info(); titles = titles or {}; colors = colors or {}
    ids = sorted(api, key=int)
    # depth
    depth = {}
    def d(n):
        if n in depth: return depth[n]
        ps = [v[0] for v in api[n]["inputs"].values() if isinstance(v, list)]
        depth[n] = 0 if not ps else 1 + max(d(p) for p in ps)
        return depth[n]
    for n in ids: d(n)
    links, nodes, link_id = [], {}, 0
    outlinks = defaultdict(list)
    # build nodes
    for n in ids:
        ct = api[n]["class_type"]; info = oi[ct]
        order = info["input_order"]["required"] + info["input_order"].get("optional", [])
        spec = {**info["input"]["required"], **info["input"].get("optional", {})}
        inputs, widgets = [], []
        for name in order:
            s = spec[name]; val = api[n]["inputs"].get(name)
            if is_widget(s):
                if isinstance(val, list):   # a widget fed by a link (e.g. camera_angle_x): input slot with widget + its stored value
                    inputs.append({"name": name, "type": s[0], "widget": {"name": name}, "link": None})
                    widgets.append(s[1].get("default", 0) if len(s) > 1 else 0)
                    continue
                if s[0] == "COMFY_DYNAMICCOMBO_V3":   # key, then the selected option's sub-widgets (stored flat as "<name>.<sub>")
                    widgets.append(val)
                    opt = next(o for o in s[1]["options"] if o["key"] == val)
                    for grp in ("required", "optional"):
                        for sub, ss in opt.get("inputs", {}).get(grp, {}).items():
                            widgets.append(api[n]["inputs"].get(f"{name}.{sub}", ss[1].get("default")))
                    continue
                widgets.append(val if val is not None else (s[1].get("default") if len(s) > 1 and "default" in s[1] else (s[0][0] if isinstance(s[0], list) else None)))
                if len(s) > 1 and s[1].get("control_after_generate"): widgets.append("fixed")
                if len(s) > 1 and s[1].get("image_upload"): widgets.append("image")
                if len(s) > 1 and s[1].get("video_upload"): widgets.append("video")
            else:
                inputs.append({"name": name, "type": s[0], "link": None})
        outs = [{"name": nm, "type": t, "links": [], "slot_index": i}
                for i, (nm, t) in enumerate(zip(info["output_name"], info["output"]))]
        nodes[n] = {"id": int(n), "type": ct, "pos": [0, 0], "size": [330, 60], "flags": {}, "order": depth[n],
                    "mode": 4 if n in bypass else 0, "inputs": inputs, "outputs": outs,
                    "properties": {"Node name for S&R": ct}, "widgets_values": widgets}
        if n in titles: nodes[n]["title"] = titles[n]
        if n in colors: nodes[n]["color"] = colors[n][0]; nodes[n]["bgcolor"] = colors[n][1]
    for n in ids:
        for name, v in api[n]["inputs"].items():
            if isinstance(v, list):
                link_id += 1
                src, slot = str(v[0]), v[1]
                inp = next(i for i in nodes[n]["inputs"] if i["name"] == name)
                inp["link"] = link_id
                nodes[src]["outputs"][slot]["links"].append(link_id)
                links.append([link_id, int(src), slot, int(n), nodes[n]["inputs"].index(inp), inp["type"]])
        nd = nodes[n]; ct = nd["type"]
        nw = len([w for w in nd["widgets_values"]])
        h = 46 + 24 * max(len(nd["inputs"]), len(nd["outputs"])) + 26 * max(nw, 0)
        if ct == "CLIPTextEncode": h = 230; nd["size"][0] = 420
        if ct in ("LoadImage", "LoadImageMask", "SaveImage", "PreviewImage"): h = 330; nd["size"][0] = 340
        nd["size"][1] = h
    cols = defaultdict(list)
    for n in ids: cols[depth[n]].append(n)
    x = 40
    for dd in sorted(cols):
        y = 60; wmax = max(nodes[n]["size"][0] for n in cols[dd])
        for n in cols[dd]:
            if y + nodes[n]["size"][1] > max_h and y > 60:
                x += wmax + 60; y = 60
            nodes[n]["pos"] = [x, y]; y += nodes[n]["size"][1] + 40
        x += wmax + 80
    return {"id": "00000000-0000-0000-0000-000000000000", "revision": 0, "last_node_id": max(map(int, ids)),
            "last_link_id": link_id, "nodes": [nodes[n] for n in ids], "links": links,
            "groups": groups or [], "config": {}, "extra": {"ds": {"scale": 0.6, "offset": [0, 0]}}, "version": 0.4}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(2)
    titles = json.load(open(a[a.index("--titles") + 1])) if "--titles" in a else {}
    byp = a[a.index("--bypass") + 1].split(",") if "--bypass" in a else []
    json.dump(convert(json.load(open(a[0])), titles, byp), open(a[1], "w"), indent=1)
