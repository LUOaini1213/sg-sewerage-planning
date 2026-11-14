"""What the receiving (existing) sewer would have to be for the town not to trigger an expansion.

Nothing about the real receiving sewer is public, so this is a what-if table: for an assumed diameter
and an assumed share of its capacity already in use, in which financial year does the town's peak flow
use up the rest?
"""
from __future__ import annotations

from . import hydraulics as hy


def capacity_at_limit(d_mm: float, hp: dict, v_design: float) -> float:
    """Flow (m3/s) at the COPSSW depth limit for a sewer laid to run at v_design at that depth."""
    d = d_mm / 1000.0
    return v_design * hy.area(d, hy.depth_limit(d, hp))


def trigger_table(flow_rows: list[dict], rc: dict, hp: dict) -> list[dict]:
    v = rc["design_velocity_at_limit_depth"]["value"]
    out = []
    for d_mm in rc["diameters_mm"]:
        cap = capacity_at_limit(d_mm, hp, v)
        for used in rc["existing_use_share"]:
            spare = cap * (1.0 - used)
            trig = next((r["fy"] for r in flow_rows if r["peak_ls"] / 1000.0 > spare + 1e-12), None)
            out.append({"d_mm": d_mm, "existing_use_share": used, "capacity_ls": cap * 1000.0,
                        "spare_ls": spare * 1000.0, "trigger_fy": trig})
    return out


def smallest_adequate(table: list[dict], used: float) -> int | None:
    ok = [r["d_mm"] for r in table if abs(r["existing_use_share"] - used) < 1e-9 and r["trigger_fy"] is None]
    return min(ok) if ok else None
