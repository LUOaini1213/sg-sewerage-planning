"""Fill docs/*.template.md from the files under results/ (and the stated assumptions in config/).

Placeholders look like {{name}}. A placeholder with no value is an error, so a number cannot be typed
into the README by hand and silently go stale.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def m(v: float, nd: int = 1) -> str:
    """S$ million."""
    return f"{float(v) / 1e6:,.{nd}f}"


def i(v) -> str:
    return f"{float(v):,.0f}"


def pct(v: float, nd: int = 0) -> str:
    return f"{100 * float(v):.{nd}f}%"


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def context(results: Path, config: Path) -> dict[str, str]:
    s = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    cfg = json.loads(config.read_text(encoding="utf-8"))
    f, n, c, p, rs = s["flows"], s["network"], s["cost"], s["programme"], s["receiving_sewer"]
    fc, hp, pc, cc = cfg["flows"], cfg["hydraulics"], cfg["programme"], cfg["cost"]
    design = _csv(results / "network_design.csv")
    norms = _csv(results / "cost_norms.csv")
    pk = _csv(results / "packages.csv")
    sch = _csv(results / "schedule.csv")
    fy = _csv(results / "cashflow_fy.csv")
    timing = _csv(results / "timing_sensitivity.csv")
    trig = _csv(results / "capacity_trigger.csv")
    sens = _csv(results / "sensitivity_design.csv")
    trade = _csv(results / "velocity_tradeoff.csv")
    onc = _csv(results / "gebiz_oncost_ratios.csv")
    flowfy = _csv(results / "flow_by_fy.csv")
    b = c["budget"]
    block = p["block_years"]
    ctx: dict[str, str] = {}

    # ---- flows
    ctx.update({
        "homes": i(f["homes"]), "homes_public": i(fc["homes_public"]["value"]),
        "homes_private": i(fc["homes_private"]["value"]),
        "ppd": f"{fc['persons_per_dwelling']['value']:g}", "population": i(f["population"]),
        "lpcd_public": i(fc["lpcd_public"]["value"]), "lpcd_private": i(fc["lpcd_private"]["value"]),
        "lpcd_blend": f"{f['blended_lpcd']:.1f}", "peak_factor": f"{fc['peak_factor']['value']:g}",
        "res_gfa_ha": f"{f['residential_gfa_m2'] / 1e4:,.0f}", "gfa_per_home": f"{f['implied_gfa_per_home_m2']:.0f}",
        "adwf_mld": f"{f['adwf_m3d'] / 1000:.1f}", "adwf_res_mld": f"{f['adwf_res_m3d'] / 1000:.1f}",
        "adwf_nonres_mld": f"{f['adwf_nonres_m3d'] / 1000:.1f}", "nonres_share": pct(f["nonres_share"]),
        "peak_ls": i(f["peak_ls"]), "peak_m3s": f"{f['peak_ls'] / 1000:.2f}",
        "parcels_with_flow": str(f["parcels_with_flow"]),
        "cr_share": pct(fc["cr_residential_gfa_share"]["value"]),
        "return_factor": f"{fc['return_factor_nonres']['value']:g}",
        "hh_observed": f"{s['household_size_observed']:g}",
        "b2_m3d": i(f["by_class_m3d"].get("industrial_b2", 0)),
    })
    order = sorted(f["by_subzone"], key=lambda k: -f["by_subzone"][k]["adwf_m3d"])
    ctx["flow_table"] = table(
        ["Subzone (URA)", "Parcels with flow", "Homes allocated", "Residential ADWF (m3/d)",
         "Non-residential ADWF (m3/d)", "Peak flow (L/s)"],
        [[k.title(), v["parcels"], i(v["homes"]), i(v["adwf_res_m3d"]), i(v["adwf_nonres_m3d"]),
          i(fc["peak_factor"]["value"] * v["adwf_m3d"] * 1000 / 86400)] for k, v in ((k, f["by_subzone"][k])
                                                                                    for k in order)]
        + [["**Town**", f["parcels_with_flow"], i(f["homes"]), i(f["adwf_res_m3d"]), i(f["adwf_nonres_m3d"]),
            i(f["peak_ls"])]])
    ctx["class_table"] = table(
        ["Flow class", "ADWF (m3/d)", "Share"],
        [[k.replace("_", " "), i(v), pct(v / f["adwf_m3d"], 1)]
         for k, v in sorted(f["by_class_m3d"].items(), key=lambda kv: -kv[1])])

    # ---- network
    gov = n["governs"]
    ctx.update({
        "reaches": str(n["reaches"]), "length_km": f"{n['length_m'] / 1000:.1f}", "length_m": i(n["length_m"]),
        "manholes": str(n["manholes"]), "trunk_km": f"{n['trunk_m'] / 1000:.1f}",
        "branch_km": f"{n['branch_m'] / 1000:.1f}", "d_min": str(n["d_min_mm"]), "d_max": str(n["d_max_mm"]),
        "outlet_d": str(n["outlet_d_mm"]), "max_depth": f"{n['max_invert_depth_m']:.1f}",
        "mean_depth": f"{n['mean_invert_depth_m']:.1f}",
        "open_cut_km": f"{n['open_cut_m'] / 1000:.1f}", "jacking_km": f"{n['jacking_m'] / 1000:.1f}",
        "jacking_share_len": pct(n["jacking_m"] / n["length_m"]),
        "gov_depth": str(gov.get("depth limit", 0)), "gov_vel": str(gov.get("self-cleansing velocity", 0)),
        "gov_flag": str(gov.get("maximum grade (not self-cleansing)", 0)),
        "flag_km": f"{n['length_not_self_cleansing_m'] / 1000:.1f}",
        "v_low": f"{n['v_min']:.2f}", "v_high": f"{n['v_max']:.2f}",
        "slope_steep": f"{n['slope_steepest_one_in']:.0f}", "slope_flat": f"{n['slope_flattest_one_in']:.0f}",
        "depth_all_ok": "yes" if n["all_depth_ok"] else "NO",
        "snap_median": f"{n['snap_median_m']:.0f}", "snap_max": i(n["snap_max_m"]),
        "snap_over_200": str(n["snap_over_200m"]),
        "road_km": f"{n['road_graph_m'] / 1000:.1f}", "road_components": str(n["road_components"]),
        "road_dropped_m": i(n["road_graph_all_m"] - n["road_graph_m"]), "osm_date": n["osm_timestamp"][:10],
        "outlet_own_m3d": i(n["outlet_own_adwf_m3d"]), "parcels_at_outlet": str(n["parcels_at_outlet"]),
        "outlet_own_share": pct(n["outlet_own_adwf_m3d"] / f["adwf_m3d"]),
        "main_trunk_km": f"{n['main_trunk_m'] / 1000:.2f}",
        "manning_n": f"{hp['manning_n']['value']:g}", "v_ceiling": f"{hp['v_design_ceiling']['value']:g}",
        "v_min_cop": f"{hp['v_min']['value']:g}", "v_max_cop": f"{hp['v_max']['value']:g}",
        "v_target_cop": f"{hp['v_target_cop']['value']:g}", "min_cover": f"{hp['min_cover_to_soffit_m']['value']:g}",
        "mh_spacing": f"{hp['manhole_max_spacing_m']['value']:g}",
        "max_slope_one_in": f"{1 / hp['max_slope']['value']:.0f}",
        "open_cut_limit": f"{cc['geometry']['max_open_cut_invert_depth_m']['value']:g}",
    })
    by = {r["reach"]: r for r in design}
    ctx["trunk_table"] = table(
        ["Reach", "Road (OSM)", "L (m)", "Peak Q (L/s)", "D (mm)", "Slope 1 in", "d/D", "V (m/s)", "Invert depth, "
         "downstream (m)", "Method", "Governed by"],
        [[r["reach"], r["road"], i(r["length_m"]), i(r["q_peak_ls"]), r["d_mm"], i(r["slope_one_in"]),
          f"{float(r['depth_ratio']):.2f}", f"{float(r['velocity_ms']):.2f}", f"{float(r['invert_down_m']):.1f}",
          r["method"], r["governs"]] for r in (by[k] for k in n["main_trunk"])])
    ctx["diameter_table"] = table(["Diameter (mm)", "Length (m)"],
                                  [[k, i(v)] for k, v in n["length_by_d_mm"].items()])
    ctx["tradeoff_table"] = table(
        ["Velocity ceiling when choosing a diameter (m/s)", "Length-weighted peak velocity (m/s)",
         "Outlet diameter (mm)", "Mean invert depth (m)", "Deepest invert (m)", "Pipe jacking (km)",
         "Budget, central (S$ m)"],
        [[t["v_ceiling_ms"] + (" (this study)" if float(t["v_ceiling_ms"]) == hp["v_design_ceiling"]["value"]
                                else " (COPSSW target)" if float(t["v_ceiling_ms"]) == hp["v_target_cop"]["value"]
                                else ""),
          f"{float(t['length_weighted_velocity_ms']):.2f}", t["outlet_d_mm"], t["mean_invert_depth_m"],
          f"{float(t['max_invert_depth_m']):.1f}", f"{float(t['jacking_m']) / 1000:.1f}", m(t["budget_central"])]
         for t in trade])
    t15 = next(t for t in trade if float(t["v_ceiling_ms"]) == hp["v_target_cop"]["value"])
    tb = [float(t["budget_central"]) for t in trade]
    ctx["tradeoff_spread"] = m(max(tb) - min(tb))
    ctx["tradeoff_15_vmean"] = f"{float(t15['length_weighted_velocity_ms']):.2f}"
    ctx["sens_table"] = table(
        ["Case", "Outlet peak (L/s)", "Outlet D (mm)", "Deepest invert (m)", "Pipe jacking (km)",
         "Budget, central (S$ m)", "Reaches not self-cleansing"],
        [[x["case"], i(x["peak_outlet_ls"]), x["outlet_d_mm"], f"{float(x['max_invert_depth_m']):.1f}",
          f"{float(x['jacking_m']) / 1000:.1f}", m(x["budget_central"]), x["reaches_not_self_cleansing"]]
         for x in sens])

    # ---- cost
    ctx.update({
        "price_base": cfg["study"]["price_base"], "escalation": f"{c['escalation']:.3f}",
        "tpi_base": f"{cc['escalation']['tpi_base']:g}", "tpi_now": f"{cc['escalation']['tpi_now']:g}",
        "budget_c": m(b["central"]["budget"]), "budget_l": m(b["low"]["budget"]), "budget_h": m(b["high"]["budget"]),
        "budget_c0": m(b["central"]["budget"], 0), "budget_l0": m(b["low"]["budget"], 0),
        "budget_h0": m(b["high"]["budget"], 0),
        "direct_c": m(b["central"]["direct"]), "prelim_c": m(b["central"]["preliminaries"]),
        "contract_c": m(b["central"]["contract"]), "contingency_c": m(b["central"]["contingency"]),
        "pes_c": m(b["central"]["pes_fee"]), "acm_c": m(b["central"]["ac_and_monitoring"]),
        "range_low": f"{100 * c['range_low_pct']:.0f}%", "range_high": f"+{100 * c['range_high_pct']:.0f}%",
        "per_m_c": i(c["budget_per_m"]["central"]), "per_m_l": i(c["budget_per_m"]["low"]),
        "per_m_h": i(c["budget_per_m"]["high"]),
        "jacking_share_cost": pct(c["jacking_share_of_direct"]),
        "prelim_pct": pct(cc["oncosts"]["preliminaries"]["central"]),
        "contingency_pct": pct(cc["oncosts"]["contingency"]["central"]),
        "pes_pct": pct(cc["oncosts"]["pes_fee"]["central"]),
        "acm_pct": pct(c["oncosts_gebiz"]["central"], 1),
        "ac_min": pct(c["oncosts_gebiz"]["ac_min"], 2), "ac_max": pct(c["oncosts_gebiz"]["ac_max"], 2),
        "mon_pct": pct(c["oncosts_gebiz"]["monitoring"], 2),
        "gebiz_n": str(c["gebiz_packages"]["count"]), "gebiz_min": m(c["gebiz_packages"]["min"], 2),
        "gebiz_median": m(c["gebiz_packages"]["median"]), "gebiz_max": m(c["gebiz_packages"]["max"]),
        "gebiz_total": m(c["gebiz_packages"]["total"], 0),
        "gebiz_years": f"{c['gebiz_packages']['first_year']} to {c['gebiz_packages']['last_year']}",
        "jack_low": i(c["jacking_norm_contract_per_m"]["low"]), "jack_high": i(c["jacking_norm_contract_per_m"]["high"]),
        "jack_c750": i(c["jacking_norm_contract_per_m"]["central_d750"]),
        "fx": f"{cfg['eur_to_sgd_2015']['value']:g}",
    })
    depths = sorted({float(x["invert_depth_m"]) for x in norms})
    show = [d for d in (200, 300, 450, 600, 900, 1200, 1500, 1800) if any(int(x["d_mm"]) == d for x in norms)]
    cell = {(int(x["d_mm"]), float(x["invert_depth_m"])): x for x in norms}

    def norm_cell(d, z):
        x = cell.get((d, z))
        return "-" if x is None else f"{i(x['budget_central'])} ({i(x['budget_low'])} to {i(x['budget_high'])})"

    ctx["norm_table"] = table(
        ["D (mm)"] + [f"{z:g} m" + (" (jacked)" if cell[(show[0], z)]["method"] == "pipe jacking" else "")
                      for z in depths],
        [[d] + [norm_cell(d, z) for z in depths] for d in show])
    ctx["bench_table"] = table(
        ["Public data point", "Value", "Length (m)", "S$ per m", "Source"],
        [[x["description"], f"{x['currency']} {x['value'] / 1e6:.2f} m ({x['year']})", i(x["length_m"]),
          i(x["sgd_per_m"]), x["basis"]] for x in c["benchmarks"]])
    ctx["oncost_table"] = table(
        ["Service", "Service award (S$)", "Construction awards it belongs to", "Construction (S$)", "Ratio"],
        [[x["kind"] + " " + x["service_tender"], i(x["service_amt"]), x["construction_tenders"],
          i(x["construction_amt"]), pct(x["ratio"], 2)] for x in onc])

    # ---- programme
    ctx["package_table"] = table(
        ["Package", "Serves first", "Needed by (assumed)", "Length (m)", "of which jacked (m)", "Largest D (mm)",
         "Budget, central (S$ m)", "Low to high (S$ m)"],
        [[x["package"], x["subzone"].title(), x["need_date"], i(x["length_m"]), i(x["jacking_m"]), x["max_d_mm"],
          m(x["budget_central"]), f"{m(x['budget_low'])} to {m(x['budget_high'])}"] for x in pk])
    ctx["schedule_table"] = table(
        ["Package", "Consultant tender starts", "Design starts", "Construction tender", "Construction",
         "Ready", "Needed ready by", "Float (months)"],
        [[x["package"], x["consultant_procurement_start"], x["design_start"], x["tender_start"],
          f"{x['construction_start']} ({x['construction_months']} months)", x["construction_end"], x["needed_by"],
          x["float_months"]] for x in sch])
    pk_ids = [x["package"] for x in pk]
    ctx["n_packages"] = str(len(pk))
    ctx["fy_table"] = table(
        ["Financial year"] + pk_ids + ["Total, constant prices", "Total, outturn"],
        [[x["fy"] + (" *" if int(x["fy"][2:]) in block else "")] + [m(x[k], 2) for k in pk_ids]
         + [m(x["total_constant_prices"], 2), m(x["total_outturn"], 2)] for x in fy])
    ctx["timing_table"] = table(
        ["Need dates shifted by (years)", "Spend in the 5-year block, constant (S$ m)", "Share of programme",
         "Block, outturn (S$ m)", "Peak year", "Peak-year spend (S$ m)", "Packages that cannot be ready in time",
         "Worst delay (months)"],
        [[f"{int(x['shift_years']):+d}" if int(x["shift_years"]) else "0 (base)", m(x["block_constant"]),
          pct(x["block_share"]), m(x["block_outturn"]), "FY" + x["peak_fy"], m(x["peak_fy_constant"]),
          x["packages_late"], x["max_late_months"]] for x in timing])
    t = {int(x["shift_years"]): x for x in timing}
    ctx.update({
        "fy_first": f"FY{block[0]}", "fy_last": f"FY{block[-1]}",
        "block_c": m(p["block_constant"]), "block_o": m(p["block_outturn"]), "block_share": pct(p["block_share"]),
        "total_o": m(p["total_outturn"]), "peak_fy": f"FY{p['peak_fy']}", "peak_fy_c": m(p["peak_fy_constant"]),
        "funding_months": str(p["funding_months"]), "planning_months": str(p["planning_months"]),
        "funding_route": p["funding_route"], "funding_approved": p["funding_approved"],
        "first_ready": p["first_sewer_ready"], "last_ready": p["last_sewer_ready"],
        "lead_min_months": str(p["min_lead_time_months"]), "lead_min_years": f"{p['min_lead_time_months'] / 12:.1f}",
        "min_float": str(p["min_float_months"]), "packages_late": str(p["packages_late"]),
        "programme_start": cfg["study"]["programme_start"],
        "block_m1": m(t[-1]["block_constant"]), "block_p1": m(t[1]["block_constant"]),
        "late_m1": t[-1]["packages_late"], "late_m1_months": t[-1]["max_late_months"],
        "block_m2": m(t[-2]["block_constant"]), "late_m2": t[-2]["packages_late"],
        "late_m2_months": t[-2]["max_late_months"],
        "escal": pct(pc["outturn_escalation_per_year"]["value"]),
        "retention": pct(pc["retention"]["value"]), "buildout_years": str(pc["buildout_years"]["value"]),
        "cp_m": str(pc["consultant_procurement_months"]["value"]), "dd_m": str(pc["detailed_design_months"]["value"]),
        "ct_m": str(pc["construction_tender_months"]["value"]), "dlp_m": str(pc["defects_liability_months"]["value"]),
        "buffer_m": str(pc["commissioning_buffer_months"]["value"]),
        "oc_rate": str(pc["construction"]["open_cut_m_per_month"]),
        "jk_rate": str(pc["construction"]["jacking_m_per_month"]),
        "f_lt100": str(pc["funding_approval_months"]["below_100m"]),
        "f_100": str(pc["funding_approval_months"]["from_100m"]),
        "f_500": str(pc["funding_approval_months"]["from_500m"]),
    })

    # ---- receiving sewer
    uses = sorted({float(x["existing_use_share"]) for x in trig})
    ds = sorted({int(x["d_mm"]) for x in trig})
    tc = {(int(x["d_mm"]), float(x["existing_use_share"])): x for x in trig}
    ctx["trigger_table"] = table(
        ["Receiving sewer D (mm)", "Capacity at the COPSSW depth limit (L/s)"]
        + [f"{pct(u)} already used" for u in uses],
        [[d, i(tc[(d, uses[0])]["capacity_ls"])]
         + [("no trigger" if tc[(d, u)]["trigger_fy"] == "none" else tc[(d, u)]["trigger_fy"]) for u in uses]
         for d in ds])
    sa = rs["smallest_adequate_d_mm"]
    ctx["recv_empty_d"] = str(sa["0.0"])
    ctx["recv_half_d"] = str(sa["0.5"]) if sa["0.5"] else "none in the range tested"
    ctx["recv_v"] = f"{cfg['receiving_sewer']['design_velocity_at_limit_depth']['value']:g}"
    ctx["flow_fy_table"] = table(["Financial year", "ADWF (m3/d)", "Peak flow (L/s)"],
                                 [[x["fy"], i(x["adwf_m3d"]), i(x["peak_ls"])] for x in flowfy
                                  if float(x["adwf_m3d"]) > 0])

    # ---- tests and mutation
    mp = results / "mutation_report.json"
    if mp.exists():
        mr = json.loads(mp.read_text(encoding="utf-8"))
        ctx["mutation_summary"] = (
            f"{mr['killed']} of {mr['total']} mutants killed by the full suite; "
            f"{mr['killed_without_snapshot']} of {mr['total']} killed with the snapshot test switched off "
            f"(run on {mr['date']}, {mr['tests_collected']} tests collected)"
            + "".join(f". Survivor {k}: {v}" for k, v in mr.get("equivalent", {}).items())
            + (f". Unexplained survivors: {', '.join(mr['survivors_not_explained'])}"
               if mr.get("survivors_not_explained") else ""))
        ctx["mutation_table"] = table(
            ["Mutant", "File", "Deliberate bug", "Killed", "Killed without the snapshot test"],
            [[x["id"], x["file"], x["what"], "yes" if x["killed"] else "NO",
              "yes" if x["killed_without_snapshot"] else "NO"] for x in mr["mutants"]])
        ctx["tests_collected"] = str(mr["tests_collected"])
    else:
        ctx["mutation_summary"] = "not run yet (python mutation/run_mutants.py)"
        ctx["mutation_table"] = ""
        ctx["tests_collected"] = "?"
    return {k: str(v) for k, v in ctx.items()}


def render(template: str, ctx: dict[str, str]) -> str:
    missing = sorted({k for k in re.findall(r"\{\{(\w+)\}\}", template) if k not in ctx})
    if missing:
        raise KeyError(f"template placeholders without a value: {missing}")
    return re.sub(r"\{\{(\w+)\}\}", lambda mo: ctx[mo.group(1)], template)


def build(results: Path | None = None) -> dict[str, str]:
    """Rendered text of README.md and docs/funding_brief.md."""
    results = results or REPO / "results"
    ctx = context(results, REPO / "config" / "study.json")
    return {
        "README.md": render((REPO / "docs" / "README.template.md").read_text(encoding="utf-8"), ctx),
        "docs/funding_brief.md": render((REPO / "docs" / "funding_brief.template.md").read_text(encoding="utf-8"),
                                        ctx),
    }
