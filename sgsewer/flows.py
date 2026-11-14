"""Used-water flow projection by land-use parcel.

Residential: the published number of homes for the town is spread over the Master Plan parcels in
proportion to their residential gross floor area (site area x gross plot ratio), then
    ADWF = homes x persons per dwelling x litres per capita per day          (COPSSW Table 4)
Non-residential: ADWF = GFA x water use per m2 GFA x return factor (proxy rates, see config).
Peak flow = peak factor x ADWF.
"""
from __future__ import annotations

import csv
from pathlib import Path

DAY_S = 86400.0


def read_parcels(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["area_m2"] = float(r["area_m2"])
        r["x"] = float(r.pop("x_svy21"))
        r["y"] = float(r.pop("y_svy21"))
    return rows


def plot_ratio(gpr: str) -> float | None:
    try:
        return float(gpr)
    except (TypeError, ValueError):
        return None


def blended_lpcd(fc: dict) -> float:
    """Litres per capita per day for the town's public / private mix."""
    pub, prv = fc["homes_public"]["value"], fc["homes_private"]["value"]
    return (pub * fc["lpcd_public"]["value"] + prv * fc["lpcd_private"]["value"]) / (pub + prv)


def nonres_lpd_per_m2(water_m3_per_m2_year: float, return_factor: float) -> float:
    """Used water in litres per m2 GFA per day from a yearly water-use benchmark."""
    return water_m3_per_m2_year * 1000.0 / 365.0 * return_factor


def project(parcels: list[dict], fc: dict, persons_per_dwelling: float | None = None,
            industrial_factor: float = 1.0) -> list[dict]:
    """One row per parcel that generates flow."""
    ppd = fc["persons_per_dwelling"]["value"] if persons_per_dwelling is None else persons_per_dwelling
    share = fc["cr_residential_gfa_share"]["value"]
    lpcd = blended_lpcd(fc)
    rf = fc["return_factor_nonres"]["value"]
    out = []
    for p in parcels:
        cls = fc["land_use_class"].get(p["lu_desc"])
        if cls is None:
            raise KeyError(f"land use {p['lu_desc']!r} has no class in config")
        if cls == "none":
            continue
        pr = plot_ratio(p["gpr"])
        res_gfa = nonres_gfa = 0.0
        nonres_cls = None
        pr_assumed = False
        if cls == "residential":
            res_gfa = p["area_m2"] * pr
        elif cls == "mixed":
            res_gfa = p["area_m2"] * pr * share
            nonres_gfa = p["area_m2"] * pr * (1.0 - share)
            nonres_cls = "commercial"
        else:
            nonres_cls = cls
            if pr is None:
                pr = fc["nonres"][cls]["plot_ratio_if_unspecified"]
                pr_assumed = True
            nonres_gfa = p["area_m2"] * pr
        out.append({"id": p["id"], "lu_desc": p["lu_desc"], "subzone": p["subzone"], "x": p["x"], "y": p["y"],
                    "area_m2": p["area_m2"], "plot_ratio": pr, "plot_ratio_assumed": pr_assumed,
                    "res_gfa_m2": res_gfa, "nonres_gfa_m2": nonres_gfa, "nonres_class": nonres_cls})
    total_res_gfa = sum(r["res_gfa_m2"] for r in out)
    homes_total = fc["homes_total"]["value"]
    for r in out:
        r["homes"] = homes_total * r["res_gfa_m2"] / total_res_gfa
        r["population"] = r["homes"] * ppd
        r["adwf_res_m3d"] = r["population"] * lpcd / 1000.0
        if r["nonres_class"]:
            k = fc["nonres"][r["nonres_class"]]
            rate = nonres_lpd_per_m2(k["water_m3_per_m2_gfa_year"], rf)
            if r["nonres_class"] == "industrial_b2":
                rate *= industrial_factor
            r["adwf_nonres_m3d"] = r["nonres_gfa_m2"] * rate / 1000.0
        else:
            r["adwf_nonres_m3d"] = 0.0
        r["adwf_m3d"] = r["adwf_res_m3d"] + r["adwf_nonres_m3d"]
        r["peak_ls"] = fc["peak_factor"]["value"] * r["adwf_m3d"] * 1000.0 / DAY_S
    return out


def totals(rows: list[dict], fc: dict) -> dict:
    res_gfa = sum(r["res_gfa_m2"] for r in rows)
    adwf = sum(r["adwf_m3d"] for r in rows)
    by_sub: dict[str, dict] = {}
    for r in rows:
        s = by_sub.setdefault(r["subzone"], {"homes": 0.0, "adwf_res_m3d": 0.0, "adwf_nonres_m3d": 0.0,
                                             "adwf_m3d": 0.0, "parcels": 0})
        s["homes"] += r["homes"]
        s["adwf_res_m3d"] += r["adwf_res_m3d"]
        s["adwf_nonres_m3d"] += r["adwf_nonres_m3d"]
        s["adwf_m3d"] += r["adwf_m3d"]
        s["parcels"] += 1
    by_class: dict[str, float] = {}
    for r in rows:
        by_class["residential"] = by_class.get("residential", 0.0) + r["adwf_res_m3d"]
        if r["nonres_class"]:
            by_class[r["nonres_class"]] = by_class.get(r["nonres_class"], 0.0) + r["adwf_nonres_m3d"]
    homes = sum(r["homes"] for r in rows)
    return {
        "parcels_with_flow": len(rows),
        "residential_gfa_m2": res_gfa,
        "nonres_gfa_m2": sum(r["nonres_gfa_m2"] for r in rows),
        "homes": homes,
        "implied_gfa_per_home_m2": res_gfa / homes,
        "population": sum(r["population"] for r in rows),
        "blended_lpcd": blended_lpcd(fc),
        "adwf_m3d": adwf,
        "adwf_res_m3d": sum(r["adwf_res_m3d"] for r in rows),
        "adwf_nonres_m3d": sum(r["adwf_nonres_m3d"] for r in rows),
        "nonres_share": sum(r["adwf_nonres_m3d"] for r in rows) / adwf,
        "peak_ls": fc["peak_factor"]["value"] * adwf * 1000.0 / DAY_S,
        "by_subzone": by_sub,
        "by_class_m3d": by_class,
    }
