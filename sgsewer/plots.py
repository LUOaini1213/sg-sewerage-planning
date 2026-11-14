"""Figures for the README. Every figure that shows the sewer layout says SYNTHETIC on it."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

LU_COLOURS = {"residential": "#f6d7a7", "mixed": "#f2b6a0", "commercial": "#e8a0a0", "industrial_b2": "#cdb9e0",
              "institutional": "#b9d6ea", "transport": "#d9d9d9", "none": "#eef3ea"}
PKG_COLOURS = ["#1b6ca8", "#d1495b", "#2e8b57", "#e6a400", "#6a4c93", "#444444"]


def plan(res: dict, geom_path: Path, out: Path) -> None:
    geom = json.loads(geom_path.read_text(encoding="utf-8"))
    cfg, g = res["cfg"], res["graph"]
    cls_of = cfg["flows"]["land_use_class"]
    fig, ax = plt.subplots(figsize=(10, 10))
    lu = {}
    import csv
    with (geom_path.parent / "parcels.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            lu[r["id"]] = cls_of.get(r["lu_desc"], "none")
    polys, cols = [], []
    for pid, rings in geom["parcels"].items():
        for ring in rings:
            polys.append(ring)
            cols.append(LU_COLOURS[lu[pid]])
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="white", linewidths=0.3))
    nodes = g["nodes"]
    ax.add_collection(LineCollection([[nodes[a], nodes[b]] for a, b, *_ in g["edges"]], colors="#9a9a9a",
                                     linewidths=0.6))
    owner = {rid: i for i, p in enumerate(res["packages"]) for rid in p["reaches"]}
    cen = res["costs"]["central"]
    for r in res["rows"]:
        xy = [nodes[n] for n in r["path"]]
        ax.plot([p[0] for p in xy], [p[1] for p in xy], color=PKG_COLOURS[owner[r["id"]]],
                linewidth=0.8 + r["d_mm"] / 300.0,
                linestyle="-" if cen[r["id"]]["method"] == "open cut" else (0, (3, 1.2)), solid_capstyle="round")
    ox, oy = res["summary"]["network"]["outlet_xy"]
    ax.plot(ox, oy, marker="v", color="black", markersize=12)
    ax.annotate("assumed outlet", (ox, oy), xytext=(ox + 60, oy - 160), fontsize=9)
    for s in geom["subzones"]:
        for ring in s["rings"]:
            ax.plot([p[0] for p in ring], [p[1] for p in ring], color="#555555", linewidth=0.8, linestyle=":")
        ring = s["rings"][0]
        ax.text(sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring), s["name"].title(),
                fontsize=8, ha="center", color="#333333", alpha=0.8)
    handles = [plt.Line2D([], [], color=PKG_COLOURS[i], linewidth=3, label=f"{p['id']} ({p['subzone'].title()})")
               for i, p in enumerate(res["packages"])]
    handles += [plt.Line2D([], [], color="black", linewidth=2, label="open cut"),
                plt.Line2D([], [], color="black", linewidth=2, linestyle=(0, (3, 1.2)), label="pipe jacking"),
                plt.Line2D([], [], color="#9a9a9a", linewidth=1, label="roads (OpenStreetMap)")]
    handles += [plt.Rectangle((0, 0), 1, 1, color=c, label=f"land use: {k.replace('_', ' ')}")
                for k, c in LU_COLOURS.items() if k != "none"]
    ax.legend(handles=handles, fontsize=7.5, loc="upper left", framealpha=0.9)
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_title("Tengah planning area: SYNTHETIC sewer layout on real roads and real Master Plan 2019 land use\n"
                 "line width grows with diameter; not PUB's network", fontsize=10)
    ax.set_xlabel("SVY21 easting (m)")
    ax.set_ylabel("SVY21 northing (m)")
    fig.text(0.99, 0.01, "Land use: URA Master Plan 2019 (data.gov.sg). Roads: (c) OpenStreetMap contributors.",
             ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def long_section(res: dict, out: Path) -> None:
    by = {r["id"]: r for r in res["rows"]}
    main = [by[i] for i in res["summary"]["network"]["main_trunk"]]
    limit = res["cfg"]["cost"]["geometry"]["max_open_cut_invert_depth_m"]["value"]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = 0.0
    for r in main:
        x1 = x + r["length_m"]
        ax.plot([x, x1], [-r["soffit_up_m"], -r["soffit_down_m"]], color="#1b6ca8", linewidth=1)
        ax.plot([x, x1], [-r["invert_up_m"], -r["invert_down_m"]], color="#1b6ca8", linewidth=1.6)
        ax.fill_between([x, x1], [-r["soffit_up_m"], -r["soffit_down_m"]], [-r["invert_up_m"], -r["invert_down_m"]],
                        color="#1b6ca8", alpha=0.25)
        ax.axvline(x, color="#bbbbbb", linewidth=0.5)
        if r["length_m"] > 120:
            ax.text((x + x1) / 2, -r["invert_down_m"] - 1.4, f"{r['d_mm']}\n1:{r['one_in']:.0f}", ha="center",
                    fontsize=7)
        x = x1
    ax.axhline(0, color="#5b8c3a", linewidth=2)
    ax.axhline(-limit, color="#d1495b", linewidth=1, linestyle="--")
    ax.text(0, -limit + 0.3, f"open-cut limit assumed in the costing ({limit:g} m to invert)", fontsize=8,
            color="#d1495b")
    ax.set_xlabel("distance along the main trunk, upstream end to assumed outlet (m)")
    ax.set_ylabel("depth below the assumed flat ground (m)")
    ax.set_title("Long section of the main trunk (SYNTHETIC layout, flat ground assumed): diameter in mm and slope",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def cost_norms(res: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    depths = sorted({n["invert_depth_m"] for n in res["norms"]})
    cmap = plt.get_cmap("viridis")
    for i, depth in enumerate(depths):
        rows = [n for n in res["norms"] if n["invert_depth_m"] == depth]
        c = cmap(i / max(1, len(depths) - 1))
        ax.plot([n["d_mm"] for n in rows], [n["budget_central"] for n in rows], color=c, marker="o", markersize=3,
                linestyle="-" if rows[0]["method"] == "open cut" else "--",
                label=f"{depth:g} m, {rows[0]['method']}")
        ax.fill_between([n["d_mm"] for n in rows], [n["budget_low"] for n in rows],
                        [n["budget_high"] for n in rows], color=c, alpha=0.08)
    ax.set_xlabel("nominal diameter (mm)")
    ax.set_ylabel(f"budget norm, S$ per metre ({res['cfg']['study']['price_base']} prices)")
    ax.set_title("Cost norm by diameter and invert depth: central line, low-high band\n"
                 "scenario build-up from a few public rates and stated assumptions, not PUB's cost norms", fontsize=10)
    ax.legend(fontsize=8, title="invert depth, method")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def cashflow(res: dict, out: Path) -> None:
    b = res["budget"]
    fys = sorted(b["fy_constant"])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    bottom = [0.0] * len(fys)
    for i, p in enumerate(res["packages"]):
        vals = [b["fy_by_package"].get(p["id"], {}).get(f, 0.0) / 1e6 for f in fys]
        ax.bar([f"FY{f % 100:02d}" for f in fys], vals, bottom=bottom, color=PKG_COLOURS[i],
               label=f"{p['id']} {p['subzone'].title()}")
        bottom = [x + y for x, y in zip(bottom, vals)]
    ax.plot([f"FY{f % 100:02d}" for f in fys], [b["fy_outturn"][f] / 1e6 for f in fys], color="black", marker="o",
            markersize=3, linewidth=1, label="total, outturn prices")
    nblock = len(b["block_years"])
    ax.axvspan(-0.5, nblock - 0.5, color="#f0e68c", alpha=0.3, zorder=0)
    ax.text(nblock / 2 - 0.5, ax.get_ylim()[1] * 0.93, "5-year block", ha="center", fontsize=9)
    ax.set_ylabel("S$ million (bars: constant prices)")
    ax.set_title("Expenditure phasing by financial year, central estimate", fontsize=10)
    ax.legend(fontsize=7.5)
    shifts = [t["shift_years"] for t in res["timing"]]
    ax2.bar([f"{k:+d}" if k else "0" for k in shifts], [t["block_constant"] / 1e6 for t in res["timing"]],
            color=["#d1495b" if t["packages_late"] else "#1b6ca8" for t in res["timing"]])
    ax2.set_xlabel("all need dates shifted by (years)")
    ax2.set_ylabel("spend inside the 5-year block, S$ million")
    ax2.set_title("Sensitivity to development timing\nred: at least one package cannot be ready in time", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def make_all(res: dict, inputs: Path, figdir: Path) -> None:
    figdir.mkdir(parents=True, exist_ok=True)
    plan(res, inputs / "map_geometry.json", figdir / "plan.png")
    long_section(res, figdir / "long_section_main_trunk.png")
    cost_norms(res, figdir / "cost_norms.png")
    cashflow(res, figdir / "cashflow_fy.png")
