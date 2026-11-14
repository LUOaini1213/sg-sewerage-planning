"""Turn the raw public downloads in data/raw/ into the small committed inputs in data/inputs/.

Needs shapely and pyproj (requirements-tools.txt). The pipeline and the tests only read data/inputs/.
Raw files (DATA_SOURCES.md says where each comes from; scripts/fetch_data.py downloads them):
  pa.geojson, subzone.geojson, mp19_landuse.geojson  URA Master Plan 2019 layers, data.gov.sg
  osm_roads.json                                      OpenStreetMap ways via Overpass
  gebiz.csv                                           MOF "Government Procurement via GeBIZ", data.gov.sg
  singstat_17863.json                                 SingStat Table Builder table 17863
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, shape
from shapely.ops import transform

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
OUT = REPO / "data" / "inputs"
PLANNING_AREA = "TENGAH"
ROAD_CLASSES = {"primary", "secondary", "tertiary", "residential", "unclassified",
                "primary_link", "secondary_link", "tertiary_link"}
TO_SVY21 = Transformer.from_crs(4326, 3414, always_xy=True).transform


def r1(v: float) -> float:
    return round(float(v), 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pa = json.loads((RAW / "pa.geojson").read_text(encoding="utf-8"))
    area = next(shape(f["geometry"]) for f in pa["features"] if f["properties"]["PLN_AREA_N"] == PLANNING_AREA)
    area_m = transform(TO_SVY21, area)

    # --- subzones -----------------------------------------------------------------------------------
    sz = json.loads((RAW / "subzone.geojson").read_text(encoding="utf-8"))
    subzones = []
    for f in sz["features"]:
        p = f["properties"]
        if p["PLN_AREA_N"] != PLANNING_AREA:
            continue
        g = transform(TO_SVY21, shape(f["geometry"]))
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        subzones.append({"name": p["SUBZONE_N"], "code": p["SUBZONE_C"], "geom": g,
                         "rings": [[[r1(x), r1(y)] for x, y in poly.exterior.coords] for poly in polys]})
    subzones.sort(key=lambda s: s["code"])

    # --- land-use parcels ---------------------------------------------------------------------------
    lu = json.loads((RAW / "mp19_landuse.geojson").read_text(encoding="utf-8"))
    parcels = []
    for f in lu["features"]:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        if not area.intersects(g):
            continue
        gm = transform(TO_SVY21, g).intersection(area_m)
        if gm.area < 1.0:
            continue
        p = f["properties"]
        c = gm.centroid if gm.contains(gm.centroid) else gm.representative_point()
        best = max(subzones, key=lambda s: s["geom"].intersection(gm).area)
        polys = list(gm.geoms) if gm.geom_type in ("MultiPolygon", "GeometryCollection") else [gm]
        rings = [[[r1(x), r1(y)] for x, y in poly.simplify(2.0).exterior.coords]
                 for poly in polys if poly.geom_type == "Polygon" and poly.area >= 1.0]
        parcels.append({"objectid": p["OBJECTID"], "lu_desc": p["LU_DESC"], "gpr": p["GPR"],
                        "area_m2": r1(gm.area), "x": r1(c.x), "y": r1(c.y), "subzone": best["name"],
                        "rings": rings})
    parcels.sort(key=lambda q: q["objectid"])
    for i, q in enumerate(parcels, 1):
        q["id"] = f"P{i:03d}"

    with (OUT / "parcels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["id", "ura_objectid", "lu_desc", "gpr", "area_m2", "x_svy21", "y_svy21", "subzone"])
        for q in parcels:
            w.writerow([q["id"], q["objectid"], q["lu_desc"], q["gpr"], q["area_m2"], q["x"], q["y"], q["subzone"]])
    (OUT / "map_geometry.json").write_text(json.dumps({
        "crs": "EPSG:3414 (SVY21), metres",
        "planning_area_m2": r1(area_m.area),
        "planning_area": [[r1(x), r1(y)] for x, y in area_m.simplify(2.0).exterior.coords],
        "subzones": [{"name": s["name"], "code": s["code"], "rings": s["rings"]} for s in subzones],
        "parcels": {q["id"]: q["rings"] for q in parcels},
    }, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

    # --- road graph ---------------------------------------------------------------------------------
    osm = json.loads((RAW / "osm_roads.json").read_text(encoding="utf-8"))
    clip = area_m.buffer(30.0)
    nodes: dict[tuple, tuple[float, float]] = {}
    edges: dict[tuple, dict] = {}
    for e in osm["elements"]:
        t = e.get("tags", {})
        hw = t.get("highway")
        status = "open"
        if hw == "construction":
            hw = t.get("construction")
            status = "construction"
        if hw not in ROAD_CLASSES:
            continue
        pts = [TO_SVY21(g["lon"], g["lat"]) for g in e["geometry"]]
        # the Overpass "out geom" output has no node ids: identical coordinates are the same OSM node
        ids = [(round(g["lon"], 7), round(g["lat"], 7)) for g in e["geometry"]]
        for i in range(len(ids) - 1):
            na, nb = ids[i], ids[i + 1]
            seg = LineString([pts[i], pts[i + 1]])
            key = (min(na, nb), max(na, nb))
            if na == nb or key in edges or not clip.contains(seg):
                continue
            nodes[na], nodes[nb] = pts[i], pts[i + 1]
            edges[key] = {"a": na, "b": nb, "length_m": round(seg.length, 2), "highway": hw,
                          "status": status, "name": t.get("name", "")}
    adj: dict[tuple, list] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen: set = set()
    comps = []
    for n in sorted(adj):
        if n in seen:
            continue
        stack, comp = [n], set()
        while stack:
            u = stack.pop()
            if u in comp:
                continue
            comp.add(u)
            stack.extend(adj[u])
        seen |= comp
        comps.append(comp)
    comps.sort(key=lambda c: (-len(c), min(c)))
    keep = comps[0]
    total_len = sum(e["length_m"] for e in edges.values())
    kept_edges = [e for (a, b), e in sorted(edges.items()) if a in keep]
    kept_len = sum(e["length_m"] for e in kept_edges)
    order = {n: i for i, n in enumerate(sorted(keep))}
    graph = {
        "crs": "EPSG:3414 (SVY21), metres",
        "source": "OpenStreetMap contributors (ODbL), via Overpass API",
        "osm_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base", ""),
        "road_classes": sorted(ROAD_CLASSES),
        "components_found": len(comps),
        "length_all_m": round(total_len, 1),
        "length_kept_m": round(kept_len, 1),
        "nodes": [[r1(nodes[n][0]), r1(nodes[n][1])] for n in sorted(keep)],
        "edges": [[order[e["a"]], order[e["b"]], e["length_m"], e["highway"], e["status"], e["name"]]
                  for e in kept_edges],
    }
    (OUT / "road_graph.json").write_text(json.dumps(graph, separators=(",", ":"), ensure_ascii=False) + "\n",
                                         encoding="utf-8", newline="\n")

    # --- GeBIZ: PUB sewer-related awards ------------------------------------------------------------
    rows = []
    with (RAW / "gebiz.csv").open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["agency"] == "Public Utilities Board" and "sewer" in r["tender_description"].lower():
                rows.append(r)
    rows.sort(key=lambda r: (r["tender_no"], r["supplier_name"]))
    with (OUT / "gebiz_pub_sewer_awards.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["tender_no", "tender_description", "award_date", "tender_detail_status", "supplier_name",
                    "awarded_amt"])
        for r in rows:
            w.writerow([r["tender_no"], " ".join(r["tender_description"].split()), r["award_date"],
                        r["tender_detail_status"], r["supplier_name"], r["awarded_amt"]])

    # --- SingStat household size --------------------------------------------------------------------
    hh = json.loads((RAW / "singstat_17863.json").read_text(encoding="utf-8"))["Data"]
    with (OUT / "singstat_household_size.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["year", "dwelling_type", "avg_household_size_persons"])
        for row in hh["row"]:
            for grp in row["columns"]:
                if grp["key"] != "Resident Households":
                    continue
                for c in grp["columns"]:
                    w.writerow([row["rowText"], c["key"], c.get("value", "")])

    # --- manifest -----------------------------------------------------------------------------------
    with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["file", "sha256", "bytes"])
        for p in sorted(OUT.iterdir()):
            if p.name == "manifest.csv":
                continue
            b = p.read_bytes()
            w.writerow([p.name, hashlib.sha256(b).hexdigest(), len(b)])
    print(f"parcels {len(parcels)}; subzones {len(subzones)}; road nodes {len(keep)}, edges {len(kept_edges)}, "
          f"kept {kept_len:.0f} of {total_len:.0f} m in {len(comps)} components; GeBIZ rows {len(rows)}")


if __name__ == "__main__":
    main()
