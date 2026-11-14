"""Cost norms: S$ per metre of sewer by diameter and depth, and S$ per manhole or shaft.

Bottom-up build-ups from a handful of public unit rates plus assumed rates (config/study.json says
which is which). Three levels, 'low', 'central' and 'high', take every rate and allowance at its low,
central or high value together, so the low-high band is the envelope of the assumptions, not a
confidence interval.
"""
from __future__ import annotations

LEVELS = ("low", "central", "high")


def escalation(cc: dict) -> float:
    """Factor from the handbook price date to the study price base, by the BCA Tender Price Index."""
    e = cc["escalation"]
    return e["tpi_now"] / e["tpi_base"]


def rates(cc: dict, level: str) -> dict:
    """All unit rates at the study price base for one level."""
    esc = escalation(cc)
    out = {k: v[level] * esc for k, v in cc["rates_4q2021"].items()}
    out.update({k: v[level] for k, v in cc["assumed_rates_1q2026"].items()})
    out["disposal_share"] = cc["geometry"]["disposal_share"][level]
    out["lining_per_m2"] = cc["geometry"]["manhole"]["lining_per_m2"][level]
    return out


def _band(value: float, table: list) -> float:
    for limit, v in table:
        if value <= limit:
            return v
    return table[-1][1]


def trench_width(d_mm: float, geo: dict) -> float:
    od = d_mm / 1000.0 * geo["outer_diameter_factor"]["value"]
    return max(od + 2.0 * geo["trench_side_clearance_m"]["value"], geo["trench_min_width_m"]["value"])


def open_cut_per_m(d_mm: float, invert_depth: float, cc: dict, level: str) -> dict:
    """Direct cost per metre of pipe laid in open trench, by component."""
    geo, rt = cc["geometry"], rates(cc, level)
    od = d_mm / 1000.0 * geo["outer_diameter_factor"]["value"]
    wall = (od - d_mm / 1000.0) / 2.0
    w = trench_width(d_mm, geo)
    h = invert_depth + wall + geo["bedding_under_pipe_m"]["value"]
    v_exc = w * h
    bands, factors = geo["excavation_depth_factor"]["bands_m"], geo["excavation_depth_factor"]["factors"]
    f_depth = factors[0] if h <= bands[0] else factors[1] if h <= bands[1] else factors[2]
    pipe_vol = 3.141592653589793 * od * od / 4.0
    bed_h = geo["bedding_under_pipe_m"]["value"] + geo["bedding_haunch_fraction_of_od"]["value"] * od
    # bedding fills the trench width up to the haunch level, less the part of the pipe below that level
    # (taken as haunch fraction x pipe volume: a simple approximation)
    v_bed = w * bed_h - geo["bedding_haunch_fraction_of_od"]["value"] * pipe_vol
    v_backfill = v_exc - pipe_vol - v_bed
    if h > geo["shoring_from_depth_m"]["value"]:
        deep = 2.0 if h > geo["deep_shoring_from_depth_m"]["value"] else 1.0
        shoring = 2.0 * h * rt["shoring_per_m2_face"] * deep
    else:
        shoring = 0.0
    c = {
        "excavation": v_exc * rt["excavation_per_m3"] * f_depth,
        "disposal": v_exc * rt["disposal_share"] * rt["disposal_per_m3"],
        "shoring": shoring,
        "bedding": v_bed * rt["bedding_concrete_per_m3"],
        "pipe": rt["pipe_k"] * d_mm * (1.0 + d_mm / 1000.0),
        "backfill": v_backfill * rt["backfill_per_m3"],
        "reinstatement": (w + geo["reinstatement_extra_width_m"]["value"]) * rt["reinstatement_per_m2"],
    }
    c["direct"] = sum(c.values())
    return c


def jacking_per_m(d_mm: float, cc: dict, level: str) -> dict:
    rt = rates(cc, level)
    c = {"jacking": rt["jack_base_per_m"] + rt["jack_per_mm"] * d_mm}
    c["direct"] = c["jacking"]
    return c


def manhole_cost(d_mm: float, invert_depth: float, cc: dict, level: str) -> dict:
    """Square reinforced-concrete manhole on an open-cut sewer, built up from quantities."""
    geo, rt = cc["geometry"], rates(cc, level)
    mh = geo["manhole"]
    s = _band(d_mm, mh["internal_size_m"])
    t = mh["wall_m"]
    depth = invert_depth + 0.3
    outer = s + 2.0 * t
    concrete = (outer * outer - s * s) * depth + outer * outer * (0.3 + 0.25)  # walls + base and cover slabs
    form = 4.0 * (s + outer) * depth
    lining = 4.0 * s * depth
    excav = (outer + 1.0) ** 2 * (depth + 0.3)
    c = {
        "concrete": concrete * rt["structural_concrete_per_m3"],
        "rebar": concrete * mh["rebar_kg_per_m3"] * rt["rebar_per_kg"],
        "formwork": form * rt["formwork_per_m2"],
        "lining": lining * rt["lining_per_m2"],
        "excavation_and_support": excav * (rt["excavation_per_m3"] + rt["disposal_per_m3"])
        + 4.0 * (outer + 1.0) * depth * rt["shoring_per_m2_face"],
        "fitout": mh["fitout_base"] * (s / 1.2),
    }
    c["direct"] = sum(c.values())
    return c


def shaft_cost(d_mm: float, invert_depth: float, cc: dict, level: str) -> dict:
    rt = rates(cc, level)
    f = _band(d_mm, cc["geometry"]["shaft_size_factor"])
    c = {"shaft": (rt["shaft_base"] + rt["shaft_per_m_depth"] * invert_depth) * f}
    c["direct"] = c["shaft"]
    return c


def method_for(mean_invert_depth: float, cc: dict) -> str:
    return "pipe jacking" if mean_invert_depth > cc["geometry"]["max_open_cut_invert_depth_m"]["value"] else "open cut"


def gross_up(direct: float, cc: dict, level: str) -> dict:
    """Direct works -> construction contract -> budget.

    contract = direct x (1 + preliminaries)
    budget   = contract x (1 + contingency) + contract x (PES fee + accredited checker and monitoring)
    """
    oc = cc["oncosts"]
    prelim = direct * oc["preliminaries"][level]
    contract = direct + prelim
    contingency = contract * oc["contingency"][level]
    pes = contract * oc["pes_fee"][level]
    acm = contract * oc["ac_and_monitoring"][level]
    return {"direct": direct, "preliminaries": prelim, "contract": contract, "contingency": contingency,
            "pes_fee": pes, "ac_and_monitoring": acm, "budget": contract + contingency + pes + acm}


def reach_cost(row: dict, cc: dict, level: str) -> dict:
    """Direct cost of one designed reach: pipeline plus its manholes or shafts."""
    method = method_for(row["mean_invert_depth_m"], cc)
    if method == "open cut":
        per_m = open_cut_per_m(row["d_mm"], row["mean_invert_depth_m"], cc, level)["direct"]
        each = manhole_cost(row["d_mm"], row["mean_invert_depth_m"], cc, level)["direct"]
    else:
        per_m = jacking_per_m(row["d_mm"], cc, level)["direct"]
        each = shaft_cost(row["d_mm"], row["mean_invert_depth_m"], cc, level)["direct"]
    pipeline = per_m * row["length_m"]
    chambers = each * row["manholes"]
    return {"method": method, "per_m": per_m, "per_chamber": each, "pipeline": pipeline, "chambers": chambers,
            "direct": pipeline + chambers}


def norm_table(cc: dict, hp: dict, depths_m: list[float]) -> list[dict]:
    """All-in budget norm, S$ per metre, by diameter and invert depth; chambers at the maximum
    manhole spacing are spread over the length."""
    spacing = hp["manhole_max_spacing_m"]["value"]
    rows = []
    for d_mm in hp["diameters_mm"]:
        for depth in depths_m:
            if depth < hp["min_cover_to_soffit_m"]["value"] + d_mm / 1000.0 - 1e-9:
                continue
            method = method_for(depth, cc)
            rec = {"d_mm": d_mm, "invert_depth_m": depth, "method": method}
            for lv in LEVELS:
                if method == "open cut":
                    line = open_cut_per_m(d_mm, depth, cc, lv)["direct"]
                    chamber = manhole_cost(d_mm, depth, cc, lv)["direct"]
                else:
                    line = jacking_per_m(d_mm, cc, lv)["direct"]
                    chamber = shaft_cost(d_mm, depth, cc, lv)["direct"]
                direct = line + chamber / spacing
                g = gross_up(direct, cc, lv)
                rec[f"direct_{lv}"] = direct
                rec[f"budget_{lv}"] = g["budget"]
                if lv == "central":
                    rec["pipeline_direct_central"] = line
                    rec["chamber_each_central"] = chamber
            rows.append(rec)
    return rows
