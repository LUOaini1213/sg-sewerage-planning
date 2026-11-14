"""Part-full circular pipe hydraulics (Manning) and the single-reach sizing rule.

Geometry of a circular pipe of diameter D flowing at depth y (ratio r = y / D), with theta the angle
subtended at the centre by the water surface:

    theta = 2 acos(1 - 2 r)
    A = D^2 / 8 * (theta - sin theta)        flow area
    P = D * theta / 2                        wetted perimeter
    R = A / P                                hydraulic radius
    V = R^(2/3) * S^(1/2) / n                Manning
    Q = V * A
"""
from __future__ import annotations

import math

R_MAX_MONOTONIC = 0.93  # Q rises with depth up to about 0.938 D; searches stay below that


def theta(r: float) -> float:
    if not 0.0 < r <= 1.0:
        raise ValueError(f"depth ratio must be in (0, 1], got {r}")
    return 2.0 * math.acos(1.0 - 2.0 * r)


def area(d: float, r: float) -> float:
    t = theta(r)
    return d * d / 8.0 * (t - math.sin(t))


def wetted_perimeter(d: float, r: float) -> float:
    return d * theta(r) / 2.0


def hydraulic_radius(d: float, r: float) -> float:
    return area(d, r) / wetted_perimeter(d, r)


def velocity(d: float, r: float, slope: float, n: float) -> float:
    return hydraulic_radius(d, r) ** (2.0 / 3.0) * math.sqrt(slope) / n


def flow(d: float, r: float, slope: float, n: float) -> float:
    return velocity(d, r, slope, n) * area(d, r)


def slope_for_flow_at_ratio(q: float, d: float, r: float, n: float) -> float:
    """Slope at which the pipe carries q at exactly depth ratio r."""
    a = area(d, r)
    return (q * n / (a * hydraulic_radius(d, r) ** (2.0 / 3.0))) ** 2


def _bisect(f, lo: float, hi: float, tol: float = 1e-12) -> float:
    flo = f(lo)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def ratio_for_area(a: float, d: float) -> float:
    """Depth ratio at which the flow area equals a."""
    full = math.pi * d * d / 4.0
    if not 0.0 < a < full:
        raise ValueError("area outside the pipe")
    return _bisect(lambda r: area(d, r) - a, 1e-9, 1.0 - 1e-12)


def ratio_for_flow(q: float, d: float, slope: float, n: float) -> float | None:
    """Depth ratio at which the pipe carries q on this slope; None when q exceeds what it can carry
    below R_MAX_MONOTONIC."""
    if q <= 0:
        return 0.0
    if flow(d, R_MAX_MONOTONIC, slope, n) < q:
        return None
    return _bisect(lambda r: flow(d, r, slope, n) - q, 1e-9, R_MAX_MONOTONIC)


def slope_for_velocity(q: float, d: float, v: float, n: float) -> tuple[float, float]:
    """(slope, depth ratio) at which flow q moves at velocity v."""
    r = ratio_for_area(q / v, d)
    return (v * n / hydraulic_radius(d, r) ** (2.0 / 3.0)) ** 2, r


def depth_limit(d: float, hp: dict) -> float:
    """COPSSW cl. 3.2.1(c): half bore up to 1.0 m diameter, two-thirds bore above."""
    if d <= hp["large_pipe_above_m"]["value"]:
        return hp["depth_ratio_small"]["value"]
    return hp["depth_ratio_large"]["value"]


def size_reach(q_peak: float, d_min_mm: int, hp: dict, n: float | None = None,
               v_ceiling: float | None = None) -> dict:
    """Smallest diameter (not below d_min_mm) and the flattest slope that meet the COPSSW rules.

    For a given diameter the flattest slope that keeps the depth within the limit puts the peak flow
    exactly at the limit depth, where the velocity is q / A_limit whatever the slope. So:
      1. take the smallest diameter whose velocity at the limit depth is not above v_ceiling;
      2. if that velocity is at least v_min, lay the pipe at the slope that gives the limit depth;
      3. otherwise (minimum size, or a diameter carried down from upstream) steepen the pipe until
         the peak flow moves at v_min; the depth is then below the limit;
      4. no pipe is laid steeper than max_slope: if step 2 would need more, go up a diameter; if
         step 3 would need more, lay the pipe at max_slope and flag it (the flow is too small to be
         self-cleansing at a practical grade).
    """
    n = hp["manning_n"]["value"] if n is None else n
    v_min, v_max = hp["v_min"]["value"], hp["v_max"]["value"]
    v_ceiling = hp["v_design_ceiling"]["value"] if v_ceiling is None else v_ceiling
    s_max = hp["max_slope"]["value"]
    for d_mm in hp["diameters_mm"]:
        if d_mm < d_min_mm:
            continue
        d = d_mm / 1000.0
        lim = depth_limit(d, hp)
        v_lim = q_peak / area(d, lim)
        if v_lim > v_ceiling:
            continue
        if v_lim >= v_min:
            slope, r, governs = slope_for_flow_at_ratio(q_peak, d, lim, n), lim, "depth limit"
            if slope > s_max:
                continue  # too steep at the depth limit: a larger pipe runs flatter
        else:
            slope, r = slope_for_velocity(q_peak, d, v_min, n)
            governs = "self-cleansing velocity"
            if slope > s_max:
                slope, governs = s_max, "maximum grade (not self-cleansing)"
                r = ratio_for_flow(q_peak, d, slope, n)
        v = velocity(d, r, slope, n)
        return {"d_mm": d_mm, "slope": slope, "depth_ratio": r, "depth_limit": lim, "velocity": v,
                "governs": governs, "q_capacity_at_limit": flow(d, lim, slope, n),
                "depth_ok": bool(r <= lim + 1e-9), "velocity_ok": bool(v_min - 1e-9 <= v <= v_max + 1e-9),
                "ok": bool(r <= lim + 1e-9 and v_min - 1e-9 <= v <= v_max + 1e-9)}
    raise ValueError(f"no diameter in the series carries {q_peak:.3f} m3/s within the rules")
