"""Run the whole study from data/inputs/ and config/study.json. compute() returns everything; write()
puts it under results/."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import statistics
from pathlib import Path

from . import capacity, cost, flows, network, programme
from . import hydraulics as hy

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / "data" / "inputs"
RESULTS = REPO / "results"
NORM_DEPTHS = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]


def load_config(path: Path | None = None) -> dict:
    return json.loads((path or REPO / "config" / "study.json").read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def gebiz_oncosts(awards: list[dict], pairs: list[dict]) -> dict:
    """Ratios of accredited-checker and monitoring awards to the construction awards they belong to."""
    amt: dict[str, float] = {}
    for a in awards:
        amt[a["tender_no"]] = amt.get(a["tender_no"], 0.0) + float(a["awarded_amt"])
    rows = []
    for p in pairs:
        base = sum(amt[t] for t in p["construction"])
        rows.append({"kind": p["kind"], "service_tender": p["service"], "service_amt": amt[p["service"]],
                     "construction_tenders": " + ".join(p["construction"]), "construction_amt": base,
                     "ratio": amt[p["service"]] / base})
    ac = [r["ratio"] for r in rows if r["kind"] == "accredited checker"]
    mon = [r["ratio"] for r in rows if r["kind"] == "instrumentation and monitoring"]
    m = statistics.mean(mon)
    return {"rows": rows, "low": min(ac) + m, "central": statistics.mean(ac) + m, "high": max(ac) + m,
            "ac_min": min(ac), "ac_max": max(ac), "monitoring": m}


def gebiz_package_stats(awards: list[dict]) -> dict:
    vals = sorted(float(a["awarded_amt"]) for a in awards
                  if a["tender_description"].startswith("Proposed Sewers")
                  and a["tender_detail_status"] == "Awarded to Suppliers" and float(a["awarded_amt"]) > 0)
    years = sorted(int(a["award_date"].split("/")[-1]) for a in awards)
    return {"count": len(vals), "min": vals[0], "median": statistics.median(vals), "max": vals[-1],
            "total": sum(vals), "first_year": years[0], "last_year": years[-1]}


def one_design(cfg: dict, parcels: list[dict], graph: dict, *, n: float | None = None,
               persons: float | None = None, industrial_factor: float = 1.0,
               v_ceiling: float | None = None) -> dict:
    fc, hp, cc = cfg["flows"], cfg["hydraulics"], cfg["cost"]
    fl = flows.project(parcels, fc, persons, industrial_factor)
    outlet = network.pick_outlet(graph, cfg["network"]["outlet_rule"])
    tree = network.build_tree(graph, fl, outlet)
    rows = network.design(tree, hp, fc["peak_factor"]["value"], n, v_ceiling)
    costs = {lv: {r["id"]: cost.reach_cost(r, cc, lv) for r in rows} for lv in cost.LEVELS}
    budget = {lv: cost.gross_up(sum(c["direct"] for c in costs[lv].values()), cc, lv) for lv in cost.LEVELS}
    last = [r for r in rows if r["down_id"] == "OUTLET"]
    adwf_out = sum(r["adwf_m3d"] for r in last) + tree["outlet_own_adwf"]
    jack = sum(r["length_m"] for r in rows if costs["central"][r["id"]]["method"] == "pipe jacking")
    stats = {
        "reaches": len(rows), "length_m": sum(r["length_m"] for r in rows),
        "manholes": sum(r["manholes"] for r in rows) + 1,
        "adwf_outlet_m3d": adwf_out,
        "peak_outlet_ls": fc["peak_factor"]["value"] * adwf_out * 1000.0 / 86400.0,
        "outlet_d_mm": max(r["d_mm"] for r in last),
        "max_invert_depth_m": max(r["invert_down_m"] for r in rows),
        "jacking_m": jack, "open_cut_m": sum(r["length_m"] for r in rows) - jack,
        "all_depth_ok": all(r["depth_ok"] for r in rows),
        "reaches_not_self_cleansing": sum(1 for r in rows if not r["velocity_ok"]),
        "length_not_self_cleansing_m": sum(r["length_m"] for r in rows if not r["velocity_ok"]),
        "mean_invert_depth_m": sum(r["mean_invert_depth_m"] * r["length_m"] for r in rows)
        / sum(r["length_m"] for r in rows),
        "budget_central": budget["central"]["budget"],
    }
    return {"flows": fl, "tree": tree, "rows": rows, "costs": costs, "budget": budget, "stats": stats}


def compute(cfg: dict | None = None) -> dict:
    cfg = copy.deepcopy(cfg or load_config())
    fc, hp, cc, pc = cfg["flows"], cfg["hydraulics"], cfg["cost"], cfg["programme"]
    st = cfg["study"]
    parcels = flows.read_parcels(INPUTS / "parcels.csv")
    graph = network.read_graph(INPUTS / "road_graph.json")
    awards = read_csv(INPUTS / "gebiz_pub_sewer_awards.csv")
    hh = read_csv(INPUTS / "singstat_household_size.csv")

    onc = gebiz_oncosts(awards, cfg["gebiz_oncost_pairs"])
    cc["oncosts"]["ac_and_monitoring"].update({k: onc[k] for k in cost.LEVELS})

    base = one_design(cfg, parcels, graph)
    fl, tree, rows = base["flows"], base["tree"], base["rows"]
    ftot = flows.totals(fl, fc)
    for r in rows:
        src = next(t for t in tree["reaches"] if t["id"] == r["id"])
        r["road"] = network.reach_road(tree, src)
        r["path"] = src["path"]
        r["class"] = "trunk" if r["d_mm"] >= cfg["network"]["trunk_from_diameter_mm"]["value"] else "branch"

    # main trunk: from the outlet upstream, always following the larger flow
    by_id = {r["id"]: r for r in rows}
    cur = max((r for r in rows if r["down_id"] == "OUTLET"), key=lambda r: r["adwf_m3d"])
    main = [cur["id"]]
    while cur["upstream_ids"]:
        cur = max((by_id[i] for i in cur["upstream_ids"]), key=lambda r: r["adwf_m3d"])
        main.append(cur["id"])
    main.reverse()

    norms = cost.norm_table(cc, hp, NORM_DEPTHS)
    packages = programme.make_packages(rows, base["costs"]["central"], pc["need_dates"], cc)
    pk_low = programme.make_packages(rows, base["costs"]["low"], pc["need_dates"], cc, "low")
    pk_high = programme.make_packages(rows, base["costs"]["high"], pc["need_dates"], cc, "high")
    for p, lo, hi in zip(packages, pk_low, pk_high):
        p["budget_low"], p["budget_high"] = lo["budget"], hi["budget"]
    start, first_fy, nblock = st["programme_start"], st["block_budget_first_fy"], st["block_budget_years"]
    sched = programme.schedule(packages, pc, start)
    bud = programme.budget(packages, sched, pc, start, first_fy, nblock)

    timing = []
    for k in pc["timing_shifts_years"]:
        s = programme.schedule(packages, pc, start, k)
        b = programme.budget(packages, s, pc, start, first_fy, nblock)
        timing.append({"shift_years": k, "block_constant": b["block_constant"], "block_outturn": b["block_outturn"],
                       "block_share": b["block_share"], "total_outturn": b["total_outturn"],
                       "peak_fy": b["peak_fy"], "peak_fy_constant": b["peak_fy_constant"],
                       "packages_late": sum(1 for x in s["packages"] if x["late_months"] > 0),
                       "max_late_months": max(x["late_months"] for x in s["packages"]),
                       "min_float_months": min(x["float_months"] for x in s["packages"]),
                       "fy_constant": b["fy_constant"]})

    adwf_sub = {s: v["adwf_m3d"] for s, v in ftot["by_subzone"].items()}
    fy_flow = programme.flow_by_fy(adwf_sub, pc["need_dates"], pc, start, first_fy, fc["peak_factor"]["value"])
    trig = capacity.trigger_table(fy_flow, cfg["receiving_sewer"], hp)

    # sensitivities of the design
    sc = cfg["sensitivity"]
    obs = next(float(r["avg_household_size_persons"]) for r in hh
               if r["year"] == sc["persons_per_dwelling_observed"]["year"]
               and r["dwelling_type"] == sc["persons_per_dwelling_observed"]["dwelling_type"])
    cases = [("base", {})]
    cases += [(f"Manning n = {n}", {"n": n}) for n in sc["manning_n"]]
    cases += [(f"{obs} persons per dwelling (SingStat {sc['persons_per_dwelling_observed']['year']})",
               {"persons": obs}),
              (f"industrial flow x {sc['industrial_intensity_factor']:g}",
               {"industrial_factor": sc["industrial_intensity_factor"]})]
    sens = []
    for name, kw in cases:
        d = base if not kw else one_design(cfg, parcels, graph, **kw)
        sens.append({"case": name, **d["stats"]})

    tradeoff = []
    for c in hp["v_design_ceiling_alternatives"]:
        d = base if abs(c - hp["v_design_ceiling"]["value"]) < 1e-9 else one_design(cfg, parcels, graph, v_ceiling=c)
        tradeoff.append({"v_ceiling": c, **d["stats"],
                         "v_mean": sum(r["velocity"] * r["length_m"] for r in d["rows"]) / d["stats"]["length_m"]})

    # public benchmarks against the norm
    bench = []
    fx = cfg["eur_to_sgd_2015"]["value"]
    for b in cfg["benchmarks"]:
        sgd = b["value"] * (fx if b["currency"] == "EUR" else 1.0)
        bench.append({**b, "sgd": sgd, "sgd_per_m": sgd / b["length_m"]})
    jack_norm = [r for r in norms if r["method"] == "pipe jacking" and r["invert_depth_m"] == 8.0]
    contract_factor = {lv: 1.0 + cc["oncosts"]["preliminaries"][lv] for lv in cost.LEVELS}
    jack_range = {"low": min(r["direct_low"] for r in jack_norm) * contract_factor["low"],
                  "high": max(r["direct_high"] for r in jack_norm) * contract_factor["high"],
                  "central_d750": next(r["direct_central"] for r in jack_norm if r["d_mm"] == 750)
                  * contract_factor["central"]}

    snaps = sorted(s["snap_m"] for s in tree["snaps"])
    gov: dict[str, int] = {}
    for r in rows:
        gov[r["governs"]] = gov.get(r["governs"], 0) + 1
    stats = base["stats"]
    length = stats["length_m"]
    summary = {
        "study": st,
        "flows": {k: v for k, v in ftot.items()},
        "household_size_observed": obs,
        "network": {
            **stats,
            "trunk_m": sum(r["length_m"] for r in rows if r["class"] == "trunk"),
            "branch_m": sum(r["length_m"] for r in rows if r["class"] == "branch"),
            "d_min_mm": min(r["d_mm"] for r in rows), "d_max_mm": max(r["d_mm"] for r in rows),
            "v_min": min(r["velocity"] for r in rows), "v_max": max(r["velocity"] for r in rows),
            "v_adwf_min": min(r["velocity_at_adwf"] for r in rows),
            "v_at_cop_target_m": sum(r["length_m"] for r in rows if r["velocity"] >= 0.9 * hp["v_target_cop"]["value"]),
            "slope_steepest_one_in": min(r["one_in"] for r in rows),
            "slope_flattest_one_in": max(r["one_in"] for r in rows),
            "governs": gov,
            "snap_median_m": statistics.median(snaps), "snap_max_m": snaps[-1],
            "snap_over_200m": sum(1 for s in snaps if s > 200),
            "road_graph_m": graph["length_kept_m"], "road_graph_all_m": graph["length_all_m"],
            "road_components": graph["components_found"], "osm_timestamp": graph["osm_timestamp"],
            "outlet_xy": graph["nodes"][tree["outlet"]],
            "outlet_own_adwf_m3d": tree["outlet_own_adwf"],
            "parcels_at_outlet": sum(1 for x in tree["snaps"] if x["node"] == tree["outlet"]),
            "main_trunk": main, "main_trunk_m": sum(by_id[i]["length_m"] for i in main),
            "length_by_d_mm": {str(d): sum(r["length_m"] for r in rows if r["d_mm"] == d)
                               for d in sorted({r["d_mm"] for r in rows})},
        },
        "cost": {
            "escalation": cost.escalation(cc),
            "oncosts_gebiz": {k: onc[k] for k in ("low", "central", "high", "ac_min", "ac_max", "monitoring")},
            "budget": base["budget"],
            "budget_per_m": {lv: base["budget"][lv]["budget"] / length for lv in cost.LEVELS},
            "range_low_pct": base["budget"]["low"]["budget"] / base["budget"]["central"]["budget"] - 1.0,
            "range_high_pct": base["budget"]["high"]["budget"] / base["budget"]["central"]["budget"] - 1.0,
            "jacking_share_of_direct": sum(c["direct"] for c in base["costs"]["central"].values()
                                           if c["method"] == "pipe jacking")
            / base["budget"]["central"]["direct"],
            "benchmarks": bench, "jacking_norm_contract_per_m": jack_range,
            "gebiz_packages": gebiz_package_stats(awards),
        },
        "programme": {
            "planning_months": sched["planning_months"], "funding_months": sched["funding_months"],
            "funding_route": sched["funding_route"], "funding_approved": programme.month_label(
                sched["funding_approved_month"], start),
            "first_sewer_ready": programme.month_label(min(s["construction_end"] for s in sched["packages"]), start),
            "last_sewer_ready": programme.month_label(max(s["construction_end"] for s in sched["packages"]), start),
            "min_lead_time_months": sched["funding_approved_month"] + min(s["lead_time_months"]
                                                                          for s in sched["packages"]),
            "packages_late": sum(1 for s in sched["packages"] if s["late_months"] > 0),
            "min_float_months": min(s["float_months"] for s in sched["packages"]),
            **{k: bud[k] for k in ("fy_constant", "fy_outturn", "block_years", "block_constant", "block_outturn",
                                   "total_constant", "total_outturn", "block_share", "peak_fy",
                                   "peak_fy_constant")},
        },
        "receiving_sewer": {
            "ultimate_peak_ls": fy_flow[-1]["peak_ls"],
            "smallest_adequate_d_mm": {str(u): capacity.smallest_adequate(trig, u)
                                       for u in cfg["receiving_sewer"]["existing_use_share"]},
        },
    }
    return {"cfg": cfg, "summary": summary, "flows": fl, "rows": rows, "tree": tree, "graph": graph,
            "norms": norms, "packages": packages, "schedule": sched, "budget": bud, "timing": timing,
            "fy_flow": fy_flow, "trigger": trig, "sensitivity": sens, "tradeoff": tradeoff, "oncosts": onc, "costs": base["costs"]}


# ------------------------------------------------------------------------------------------- output
def _w(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _round(o, nd=6):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v, nd) for v in o]
    return o


def write(res: dict, out: Path = RESULTS) -> None:
    cfg, start = res["cfg"], res["cfg"]["study"]["programme_start"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(_round(res["summary"]), indent=1) + "\n", encoding="utf-8")
    _w(out / "flows_by_parcel.csv",
       ["parcel", "land_use", "subzone", "area_m2", "plot_ratio", "plot_ratio_assumed", "res_gfa_m2",
        "nonres_gfa_m2", "nonres_class", "homes", "population", "adwf_res_m3d", "adwf_nonres_m3d", "peak_ls"],
       [[f["id"], f["lu_desc"], f["subzone"], f["area_m2"], f["plot_ratio"], int(f["plot_ratio_assumed"]),
         round(f["res_gfa_m2"], 1), round(f["nonres_gfa_m2"], 1), f["nonres_class"] or "", round(f["homes"], 1),
         round(f["population"], 1), round(f["adwf_res_m3d"], 2), round(f["adwf_nonres_m3d"], 2),
         round(f["peak_ls"], 3)] for f in res["flows"]])
    cen = res["costs"]["central"]
    _w(out / "network_design.csv",
       ["reach", "to", "class", "road", "length_m", "adwf_m3d", "q_peak_ls", "d_mm", "slope_one_in", "depth_ratio",
        "depth_limit", "velocity_ms", "velocity_at_adwf_ms", "governs", "invert_up_m", "invert_down_m",
        "manholes", "method", "direct_cost_central", "depth_ok", "velocity_ok"],
       [[r["id"], r["down_id"], r["class"], r["road"], round(r["length_m"], 1), round(r["adwf_m3d"], 1),
         round(r["q_peak_ls"], 2), r["d_mm"], round(r["one_in"], 1), round(r["depth_ratio"], 4),
         round(r["depth_limit"], 4), round(r["velocity"], 3), round(r["velocity_at_adwf"], 3), r["governs"],
         round(r["invert_up_m"], 3), round(r["invert_down_m"], 3), r["manholes"], cen[r["id"]]["method"],
         round(cen[r["id"]]["direct"]), int(r["depth_ok"]), int(r["velocity_ok"])] for r in res["rows"]])
    _w(out / "cost_norms.csv",
       ["d_mm", "invert_depth_m", "method", "pipeline_direct_central", "chamber_each_central", "direct_low",
        "direct_central", "direct_high", "budget_low", "budget_central", "budget_high"],
       [[n["d_mm"], n["invert_depth_m"], n["method"], round(n["pipeline_direct_central"]),
         round(n["chamber_each_central"]), round(n["direct_low"]), round(n["direct_central"]),
         round(n["direct_high"]), round(n["budget_low"]), round(n["budget_central"]), round(n["budget_high"])]
        for n in res["norms"]])
    comp_rows = []
    for d_mm, depth in ((300, 3.0), (600, 4.0), (1200, 5.0)):
        for lv in cost.LEVELS:
            c = cost.open_cut_per_m(d_mm, depth, cfg["cost"], lv)
            for k, v in c.items():
                comp_rows.append(["open cut, per m", d_mm, depth, lv, k, round(v, 2)])
            c = cost.manhole_cost(d_mm, depth, cfg["cost"], lv)
            for k, v in c.items():
                comp_rows.append(["manhole, each", d_mm, depth, lv, k, round(v, 2)])
    _w(out / "cost_norm_buildups.csv", ["item", "d_mm", "invert_depth_m", "level", "component", "sgd"], comp_rows)
    _w(out / "gebiz_oncost_ratios.csv",
       ["kind", "service_tender", "service_amt", "construction_tenders", "construction_amt", "ratio"],
       [[r["kind"], r["service_tender"], r["service_amt"], r["construction_tenders"], r["construction_amt"],
         round(r["ratio"], 5)] for r in res["oncosts"]["rows"]])
    sb = {s["id"]: s for s in res["schedule"]["packages"]}
    _w(out / "packages.csv",
       ["package", "subzone", "need_date", "reaches", "length_m", "open_cut_m", "jacking_m", "manholes",
        "max_d_mm", "direct", "contract", "contingency", "pes_fee", "ac_and_monitoring", "budget_central",
        "budget_low", "budget_high"],
       [[p["id"], p["subzone"], p["need_date"], len(p["reaches"]), round(p["length_m"], 1),
         round(p["open_cut_m"], 1), round(p["jacking_m"], 1), p["manholes"], p["max_d_mm"], round(p["direct"]),
         round(p["contract"]), round(p["contingency"]), round(p["pes_fee"]), round(p["ac_and_monitoring"]),
         round(p["budget"]), round(p["budget_low"]), round(p["budget_high"])] for p in res["packages"]])
    ml = lambda m: programme.month_label(m, start)  # noqa: E731
    _w(out / "schedule.csv",
       ["package", "subzone", "consultant_procurement_start", "design_start", "tender_start",
        "construction_start", "construction_months", "construction_end", "dlp_end", "needed_by",
        "float_months", "late_months"],
       [[s["id"], s["subzone"], ml(s["consultant_start"]), ml(s["design_start"]), ml(s["tender_start"]),
         ml(s["construction_start"]), s["construction_months"], ml(s["construction_end"]), ml(s["dlp_end"]),
         ml(s["finish_by_month"]), s["float_months"], s["late_months"]] for s in res["schedule"]["packages"]])
    b = res["budget"]
    pk_ids = [p["id"] for p in res["packages"]]
    _w(out / "cashflow_fy.csv", ["fy", *pk_ids, "total_constant_prices", "total_outturn"],
       [[f"FY{f}", *[round(b["fy_by_package"].get(i, {}).get(f, 0.0)) for i in pk_ids],
         round(b["fy_constant"][f]), round(b["fy_outturn"][f])] for f in sorted(b["fy_constant"])])
    _w(out / "cashflow_monthly.csv", ["month", "constant_prices"],
       [[ml(m), round(v, 2)] for m, v in sorted(b["monthly_constant"].items())])
    _w(out / "timing_sensitivity.csv",
       ["shift_years", "block_constant", "block_outturn", "block_share", "total_outturn", "peak_fy",
        "peak_fy_constant", "packages_late", "max_late_months", "min_float_months"],
       [[t["shift_years"], round(t["block_constant"]), round(t["block_outturn"]), round(t["block_share"], 4),
         round(t["total_outturn"]), t["peak_fy"], round(t["peak_fy_constant"]), t["packages_late"],
         t["max_late_months"], t["min_float_months"]] for t in res["timing"]])
    _w(out / "flow_by_fy.csv", ["fy", "adwf_m3d", "peak_ls"],
       [[f"FY{r['fy']}", round(r["adwf_m3d"], 1), round(r["peak_ls"], 2)] for r in res["fy_flow"]])
    _w(out / "capacity_trigger.csv", ["d_mm", "existing_use_share", "capacity_ls", "spare_ls", "trigger_fy"],
       [[t["d_mm"], t["existing_use_share"], round(t["capacity_ls"], 1), round(t["spare_ls"], 1),
         f"FY{t['trigger_fy']}" if t["trigger_fy"] else "none"] for t in res["trigger"]])
    _w(out / "sensitivity_design.csv",
       ["case", "peak_outlet_ls", "outlet_d_mm", "length_m", "max_invert_depth_m", "jacking_m", "budget_central",
        "reaches_not_self_cleansing", "all_depth_checks_ok"],
       [[s["case"], round(s["peak_outlet_ls"], 1), s["outlet_d_mm"], round(s["length_m"]),
         round(s["max_invert_depth_m"], 2), round(s["jacking_m"]), round(s["budget_central"]), s["reaches_not_self_cleansing"],
         int(s["all_depth_ok"])] for s in res["sensitivity"]])
    _w(out / "velocity_tradeoff.csv",
       ["v_ceiling_ms", "length_weighted_velocity_ms", "outlet_d_mm", "mean_invert_depth_m", "max_invert_depth_m",
        "open_cut_m", "jacking_m", "budget_central"],
       [[t["v_ceiling"], round(t["v_mean"], 3), t["outlet_d_mm"], round(t["mean_invert_depth_m"], 2),
         round(t["max_invert_depth_m"], 2), round(t["open_cut_m"]), round(t["jacking_m"]),
         round(t["budget_central"])] for t in res["tradeoff"]])
    used = {"config_sha256": hashlib.sha256((REPO / "config" / "study.json").read_bytes()).hexdigest(),
            "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(INPUTS.iterdir())}}
    (out / "inputs_used.json").write_text(json.dumps(used, indent=1) + "\n", encoding="utf-8")
