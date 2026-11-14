"""SYNTHETIC sewer layout: a tree along real roads, and its level design.

The roads are real (OpenStreetMap). The sewer layout is not: every flow-generating parcel is attached to
its nearest road node, and the sewers are the union of the shortest road paths from those nodes to one
assumed outlet. Nothing here is taken from PUB's network.
"""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

from . import hydraulics as hy


def read_graph(path: Path) -> dict:
    g = json.loads(path.read_text(encoding="utf-8"))
    adj: dict[int, list[tuple[int, float, int]]] = {i: [] for i in range(len(g["nodes"]))}
    for k, (a, b, length, *_rest) in enumerate(g["edges"]):
        adj[a].append((b, length, k))
        adj[b].append((a, length, k))
    g["adj"] = adj
    return g


def pick_outlet(g: dict, rule: str) -> int:
    if rule == "westmost node of the road graph":
        return min(range(len(g["nodes"])), key=lambda i: (g["nodes"][i][0], g["nodes"][i][1]))
    raise ValueError(f"unknown outlet rule {rule!r}")


def dijkstra(adj: dict, source: int) -> tuple[dict[int, float], dict[int, int]]:
    """Shortest distance to source and the next node towards it, for every reachable node."""
    dist = {source: 0.0}
    nxt: dict[int, int] = {}
    heap = [(0.0, source)]
    done: set[int] = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        for v, w, _k in adj[u]:
            nd = d + w
            if nd < dist.get(v, math.inf) - 1e-9:
                dist[v] = nd
                nxt[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, nxt


def nearest_node(g: dict, x: float, y: float) -> tuple[int, float]:
    best, bd = -1, math.inf
    for i, (nx, ny) in enumerate(g["nodes"]):
        d = (nx - x) ** 2 + (ny - y) ** 2
        if d < bd:
            best, bd = i, d
    return best, math.sqrt(bd)


def build_tree(g: dict, loads: list[dict], outlet: int) -> dict:
    """Reaches of the sewer tree. loads: rows with x, y, subzone, adwf_m3d.

    A reach runs from one 'key' node (a load point, a junction or a dead end) down to the next.
    """
    dist, nxt = dijkstra(g["adj"], outlet)
    node_load: dict[int, dict[str, float]] = {}
    snaps = []
    for ld in loads:
        n, d = nearest_node(g, ld["x"], ld["y"])
        snaps.append({"id": ld["id"], "node": n, "snap_m": d})
        by = node_load.setdefault(n, {})
        by[ld["subzone"]] = by.get(ld["subzone"], 0.0) + ld["adwf_m3d"]
    used: set[int] = set()
    for n in node_load:
        u = n
        while u != outlet and u not in used:
            used.add(u)
            u = nxt[u]
    used.add(outlet)
    children: dict[int, list[int]] = {u: [] for u in used}
    for u in used:
        if u != outlet:
            children[nxt[u]].append(u)
    key = {u for u in used if u == outlet or u in node_load or len(children[u]) != 1}
    reaches = []
    for u in sorted(key - {outlet}, key=lambda k: (-dist[k], k)):
        path = [u]
        while True:
            path.append(nxt[path[-1]])
            if path[-1] in key:
                break
        length = dist[u] - dist[path[-1]]
        reaches.append({"up": u, "down": path[-1], "path": path, "length_m": length,
                        "dist_up_m": dist[u], "own_adwf": dict(node_load.get(u, {}))})
    by_up = {r["up"]: r for r in reaches}
    # accumulate flow by subzone, upstream first (reaches are sorted by distance from the outlet)
    for r in reaches:
        r["adwf_by_subzone"] = dict(r["own_adwf"])
    for r in reaches:
        dn = by_up.get(r["down"])
        if dn is not None:
            for s, v in r["adwf_by_subzone"].items():
                dn["adwf_by_subzone"][s] = dn["adwf_by_subzone"].get(s, 0.0) + v
    for i, r in enumerate(reaches, 1):
        r["id"] = f"R{i:03d}"
        r["adwf_m3d"] = sum(r["adwf_by_subzone"].values())
        r["upstream_ids"] = []
    for r in reaches:
        dn = by_up.get(r["down"])
        r["down_id"] = dn["id"] if dn else "OUTLET"
        if dn:
            dn["upstream_ids"].append(r["id"])
    outlet_load = sum(node_load.get(outlet, {}).values())
    return {"reaches": reaches, "outlet": outlet, "snaps": snaps, "outlet_own_adwf": outlet_load,
            "road_name": _road_names(g)}


def _road_names(g: dict) -> dict[tuple[int, int], str]:
    return {(min(a, b), max(a, b)): name for a, b, _l, _hw, _st, name in g["edges"]}


def reach_road(tree: dict, r: dict) -> str:
    """Name of the road that carries most of the reach."""
    by: dict[str, float] = {}
    names = tree["road_name"]
    for a, b in zip(r["path"], r["path"][1:]):
        nm = names.get((min(a, b), max(a, b)), "") or "(unnamed road)"
        by[nm] = by.get(nm, 0.0) + 1.0
    return max(sorted(by), key=lambda k: by[k])


def design(tree: dict, hp: dict, peak_factor: float, n: float | None = None,
           v_ceiling: float | None = None) -> list[dict]:
    """Size every reach and set its levels (depths below a flat ground level).

    Upstream first. Diameter never decreases downstream. At a manhole the outgoing soffit is at the
    lowest incoming soffit (COPSSW cl. 3.2.2(e): incoming pipes join at the soffit level of the
    outgoing sewer), and never shallower than the minimum cover.
    """
    cover = hp["min_cover_to_soffit_m"]["value"]
    spacing = hp["manhole_max_spacing_m"]["value"]
    out: dict[str, dict] = {}
    for r in tree["reaches"]:
        ups = [out[i] for i in r["upstream_ids"]]
        q = peak_factor * r["adwf_m3d"] / 86400.0
        d_min = max([u["d_mm"] for u in ups], default=0)
        s = hy.size_reach(q, d_min, hp, n, v_ceiling)
        d = s["d_mm"] / 1000.0
        soffit_up = max([cover] + [u["soffit_down_m"] for u in ups])
        fall = s["slope"] * r["length_m"]
        nn = hp["manning_n"]["value"] if n is None else n
        r_avg = hy.ratio_for_flow(r["adwf_m3d"] / 86400.0, d, s["slope"], nn)
        row = {
            "id": r["id"], "down_id": r["down_id"], "length_m": r["length_m"],
            "adwf_m3d": r["adwf_m3d"], "q_peak_ls": q * 1000.0, **s,
            "one_in": 1.0 / s["slope"],
            "velocity_at_adwf": hy.velocity(d, r_avg, s["slope"], nn),
            "soffit_up_m": soffit_up, "soffit_down_m": soffit_up + fall,
            "invert_up_m": soffit_up + d, "invert_down_m": soffit_up + fall + d,
            "mean_invert_depth_m": soffit_up + d + fall / 2.0,
            "manholes": max(1, math.ceil(r["length_m"] / spacing - 1e-9)),
            "adwf_by_subzone": r["adwf_by_subzone"], "upstream_ids": r["upstream_ids"],
        }
        out[r["id"]] = row
    return [out[r["id"]] for r in tree["reaches"]]
