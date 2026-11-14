"""Packages, implementation schedule, monthly cashflow and the financial-year budget.

Months are counted from the programme start (month 0 = April of the first financial year), so the
Singapore government financial year (April to March) of month m is first_fy + m // 12.
"""
from __future__ import annotations

import math

from . import cost as costmod

PRICE_BASE_MONTH = "2026-02"  # middle of 1Q2026


def month_index(ym: str, start: str) -> int:
    y, m = (int(v) for v in ym.split("-"))
    y0, m0 = (int(v) for v in start.split("-"))
    return (y - y0) * 12 + (m - m0)


def fy_of_month(m: int, first_fy: int) -> int:
    return first_fy + m // 12


def month_label(m: int, start: str) -> str:
    y0, m0 = (int(v) for v in start.split("-"))
    t = y0 * 12 + (m0 - 1) + m
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def s_curve(t: float) -> float:
    """Cumulative share of construction value certified at share t of the construction period."""
    t = min(max(t, 0.0), 1.0)
    return 3.0 * t * t - 2.0 * t ** 3


def funding_months(scheme_budget: float, pc: dict) -> tuple[int, str]:
    f = pc["funding_approval_months"]
    if scheme_budget >= 500e6:
        return f["from_500m"], "above S$500 million: Gateway Process with the Development Projects Advisory Panel"
    if scheme_budget >= 100e6:
        return f["from_100m"], "above S$100 million: Development Planning Committee approval"
    return f["below_100m"], "below S$100 million"


def construction_months(open_cut_m: float, jacking_m: float, pc: dict) -> int:
    c = pc["construction"]
    return max(c["min_months"], math.ceil(open_cut_m / c["open_cut_m_per_month"]
                                          + jacking_m / c["jacking_m_per_month"] - 1e-9))


def make_packages(design_rows: list[dict], reach_costs: dict[str, dict], need_dates: dict[str, str],
                  cc: dict, level: str = "central") -> list[dict]:
    """One package per subzone: each reach goes to the earliest-needed subzone whose flow it carries."""
    order = sorted((k for k in need_dates if not k.startswith("_")), key=lambda k: (need_dates[k], k))
    pk: dict[str, dict] = {}
    for r in design_rows:
        subs = [s for s, v in r["adwf_by_subzone"].items() if v > 0]
        owner = min(subs, key=order.index)
        c = reach_costs[r["id"]]
        p = pk.setdefault(owner, {"subzone": owner, "reaches": [], "open_cut_m": 0.0, "jacking_m": 0.0,
                                  "manholes": 0, "direct": 0.0, "max_d_mm": 0})
        p["reaches"].append(r["id"])
        p["open_cut_m" if c["method"] == "open cut" else "jacking_m"] += r["length_m"]
        p["manholes"] += r["manholes"]
        p["direct"] += c["direct"]
        p["max_d_mm"] = max(p["max_d_mm"], r["d_mm"])
    out = []
    for i, s in enumerate([s for s in order if s in pk], 1):
        p = pk[s]
        p["id"] = f"PKG{i}"
        p["need_date"] = need_dates[s]
        p["length_m"] = p["open_cut_m"] + p["jacking_m"]
        p.update({k: v for k, v in costmod.gross_up(p["direct"], cc, level).items() if k != "direct"})
        out.append(p)
    return out


def schedule(packages: list[dict], pc: dict, start: str, shift_years: int = 0) -> dict:
    """Scheme-level planning and funding approval once, then each package as late as its need date
    allows, but never before funding approval."""
    scheme_budget = sum(p["budget"] for p in packages)
    plan = pc["planning_and_consultation_months"]["value"]
    fund, route = funding_months(scheme_budget, pc)
    approved = plan + fund
    cp, dd, ct = (pc["consultant_procurement_months"]["value"], pc["detailed_design_months"]["value"],
                  pc["construction_tender_months"]["value"])
    rows = []
    for p in packages:
        con = construction_months(p["open_cut_m"], p["jacking_m"], pc)
        need = month_index(p["need_date"], start) + 12 * shift_years
        finish_by = need - pc["commissioning_buffer_months"]["value"]
        latest_start = finish_by - con - ct - dd - cp
        begin = max(latest_start, approved)
        t_dd, t_ct, t_con = begin + cp, begin + cp + dd, begin + cp + dd + ct
        end = t_con + con
        rows.append({"id": p["id"], "subzone": p["subzone"], "need_month": need, "finish_by_month": finish_by,
                     "consultant_start": begin, "design_start": t_dd, "tender_start": t_ct,
                     "construction_start": t_con, "construction_months": con, "construction_end": end,
                     "dlp_end": end + pc["defects_liability_months"]["value"],
                     "float_months": latest_start - approved, "late_months": max(0, end - finish_by),
                     "lead_time_months": cp + dd + ct + con})
    return {"planning_months": plan, "funding_months": fund, "funding_route": route,
            "funding_approved_month": approved, "scheme_budget": scheme_budget, "packages": rows}


def package_cashflow(p: dict, s: dict, pc: dict) -> dict[int, float]:
    """Monthly payments for one package at constant prices; they add up to the package budget."""
    cash: dict[int, float] = {}

    def add(m: int, v: float) -> None:
        cash[m] = cash.get(m, 0.0) + v

    split = pc["pes_fee_split"]
    dd = s["tender_start"] - s["design_start"]
    ct = s["construction_start"] - s["tender_start"]
    con = s["construction_months"]
    for k in range(dd):
        add(s["design_start"] + k, p["pes_fee"] * split["design"] / dd)
    for k in range(ct):
        add(s["tender_start"] + k, p["pes_fee"] * split["tender"] / ct)
    works = p["contract"] + p["contingency"]
    ret = pc["retention"]["value"]
    for k in range(con):
        m = s["construction_start"] + k
        certified = works * (s_curve((k + 1) / con) - s_curve(k / con))
        add(m, certified * (1.0 - ret))
        add(m, p["pes_fee"] * split["construction"] / con)
        add(m, p["ac_and_monitoring"] / con)
    add(s["construction_end"], works * ret / 2.0)
    add(s["dlp_end"], works * ret / 2.0)
    return cash


def outturn_factor(m: int, start: str, rate: float) -> float:
    """Escalation from the price base to month m of the programme."""
    months = month_index(start, PRICE_BASE_MONTH) + m
    return (1.0 + rate) ** (months / 12.0)


def budget(packages: list[dict], sched: dict, pc: dict, start: str, first_fy: int, block_years: int) -> dict:
    by_id = {s["id"]: s for s in sched["packages"]}
    rate = pc["outturn_escalation_per_year"]["value"]
    monthly: dict[int, float] = {}
    monthly_out: dict[int, float] = {}
    fy_pkg: dict[str, dict[int, float]] = {}
    for p in packages:
        cf = package_cashflow(p, by_id[p["id"]], pc)
        for m, v in cf.items():
            monthly[m] = monthly.get(m, 0.0) + v
            monthly_out[m] = monthly_out.get(m, 0.0) + v * outturn_factor(m, start, rate)
            f = fy_of_month(m, first_fy)
            fy_pkg.setdefault(p["id"], {})[f] = fy_pkg.setdefault(p["id"], {}).get(f, 0.0) + v
    fys = sorted({fy_of_month(m, first_fy) for m in monthly} | set(range(first_fy, first_fy + block_years)))
    fy_const = {f: 0.0 for f in fys}
    fy_out = {f: 0.0 for f in fys}
    for m, v in monthly.items():
        fy_const[fy_of_month(m, first_fy)] += v
        fy_out[fy_of_month(m, first_fy)] += monthly_out[m]
    block = list(range(first_fy, first_fy + block_years))
    total = sum(fy_const.values())
    peak_fy = max(fy_const, key=lambda f: (fy_const[f], -f))
    return {"fy_constant": fy_const, "fy_outturn": fy_out, "fy_by_package": fy_pkg,
            "block_years": block,
            "block_constant": sum(fy_const[f] for f in block), "block_outturn": sum(fy_out[f] for f in block),
            "total_constant": total, "total_outturn": sum(fy_out.values()),
            "block_share": sum(fy_const[f] for f in block) / total,
            "peak_fy": peak_fy, "peak_fy_constant": fy_const[peak_fy],
            "monthly_constant": monthly}


def buildout_share(fy: int, need_fy: int, years: int) -> float:
    """Share of a subzone's ultimate flow present in financial year fy: equal yearly steps from the
    need year, complete after `years` years."""
    return min(max((fy - need_fy + 1) / years, 0.0), 1.0)


def flow_by_fy(adwf_by_subzone: dict[str, float], need_dates: dict[str, str], pc: dict, start: str,
               first_fy: int, peak_factor: float, shift_years: int = 0) -> list[dict]:
    years = pc["buildout_years"]["value"]
    need_fy = {s: fy_of_month(month_index(need_dates[s], start), first_fy) + shift_years
               for s in adwf_by_subzone}
    last = max(need_fy.values()) + years
    rows = []
    for fy in range(first_fy, last + 1):
        adwf = sum(v * buildout_share(fy, need_fy[s], years) for s, v in adwf_by_subzone.items())
        rows.append({"fy": fy, "adwf_m3d": adwf, "peak_ls": peak_factor * adwf * 1000.0 / 86400.0})
    return rows
