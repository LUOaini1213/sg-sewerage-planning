"""Hydraulics against values worked by hand. The arithmetic is written out in the comments and in the
expected values; none of it calls the module under test."""
import math

import pytest

from sgsewer import hydraulics as hy

N = 0.013


def test_half_bore_geometry_by_hand():
    # D = 0.6 m, half full: A = pi D^2 / 8 = pi * 0.36 / 8 = 0.1413717 m2
    #                       P = pi D / 2 = 0.9424778 m;  R = A / P = D / 4 = 0.15 m
    assert hy.area(0.6, 0.5) == pytest.approx(0.1413717, rel=1e-6)
    assert hy.wetted_perimeter(0.6, 0.5) == pytest.approx(0.9424778, rel=1e-6)
    assert hy.hydraulic_radius(0.6, 0.5) == pytest.approx(0.15, rel=1e-9)


def test_full_bore_geometry():
    assert hy.area(0.9, 1.0) == pytest.approx(math.pi * 0.81 / 4, rel=1e-12)
    assert hy.hydraulic_radius(0.9, 1.0) == pytest.approx(0.225, rel=1e-12)


def test_two_thirds_bore_geometry_by_hand():
    # r = 2/3: theta = 2 acos(1 - 4/3) = 2 acos(-1/3) = 2 x 1.9106332 = 3.8212665 rad
    # sin(theta) = 2 sin(theta/2) cos(theta/2) = 2 * 0.9428090 * (-1/3) = -0.6285394
    # A = D^2 / 8 * (3.8212665 + 0.6285394) = 0.5562257 D^2 ;  D = 1.2 -> 0.8009651 m2
    # P = D * theta / 2 = 1.2 * 1.9106332 = 2.2927599 m ;  R = 0.3493454 m
    assert hy.theta(2 / 3) == pytest.approx(3.8212665, rel=1e-7)
    assert hy.area(1.2, 2 / 3) == pytest.approx(0.8009651, rel=1e-6)
    assert hy.wetted_perimeter(1.2, 2 / 3) == pytest.approx(2.2927599, rel=1e-6)
    assert hy.hydraulic_radius(1.2, 2 / 3) == pytest.approx(0.3493454, rel=1e-6)


def test_manning_half_bore_by_hand():
    # D = 0.6, half full, S = 1/300, n = 0.013
    # R^(2/3) = 0.15^(2/3) = 0.2823108 ; sqrt(S) = 0.0577350
    # V = 0.2823108 * 0.0577350 / 0.013 = 1.253788 m/s ;  Q = V * 0.1413717 = 0.177250 m3/s
    assert hy.velocity(0.6, 0.5, 1 / 300, N) == pytest.approx(1.253788, rel=1e-5)
    assert hy.flow(0.6, 0.5, 1 / 300, N) == pytest.approx(0.177250, rel=1e-5)


def test_velocity_scales_with_root_slope_and_inverse_n():
    v = hy.velocity(0.45, 0.4, 0.004, N)
    assert hy.velocity(0.45, 0.4, 0.016, N) == pytest.approx(2 * v, rel=1e-12)
    assert hy.velocity(0.45, 0.4, 0.004, 2 * N) == pytest.approx(v / 2, rel=1e-12)


def test_slope_for_flow_at_ratio_by_hand():
    # Q = 0.100 m3/s in 525 mm at half bore: A = pi * 0.275625 / 8 = 0.1082376 ; R = 0.13125
    # R^(2/3) = 0.2582655 ; S = (0.1 * 0.013 / (0.1082376 * 0.2582655))^2 = 0.0465048^2 = 0.00216270
    s = hy.slope_for_flow_at_ratio(0.100, 0.525, 0.5, N)
    assert s == pytest.approx(0.0021627, rel=2e-4)
    assert hy.flow(0.525, 0.5, s, N) == pytest.approx(0.100, rel=1e-9)


def test_inverse_functions_are_consistent():
    s = 0.003
    q = hy.flow(0.75, 0.37, s, N)
    assert hy.ratio_for_flow(q, 0.75, s, N) == pytest.approx(0.37, abs=1e-8)
    assert hy.ratio_for_area(hy.area(0.75, 0.37), 0.75) == pytest.approx(0.37, abs=1e-8)
    slope, r = hy.slope_for_velocity(0.020, 0.3, 0.9, N)
    assert hy.area(0.3, r) * 0.9 == pytest.approx(0.020, rel=1e-8)
    assert hy.velocity(0.3, r, slope, N) == pytest.approx(0.9, rel=1e-8)
    assert hy.ratio_for_flow(10.0, 0.3, 0.001, N) is None  # more than the pipe can carry


def test_depth_limit_switches_above_one_metre(raw_cfg):
    hp = raw_cfg["hydraulics"]
    assert hy.depth_limit(0.9, hp) == 0.5
    assert hy.depth_limit(1.0, hp) == 0.5  # "pipes up to 1.0m diameter"
    assert hy.depth_limit(1.05, hp) == pytest.approx(2 / 3)


def test_size_reach_depth_limit_governs(raw_cfg):
    # Q = 0.100 m3/s, ceiling 1.2 m/s.
    # 450 mm: A_half = pi * 0.2025 / 8 = 0.0795216 -> V = 1.2575 > 1.2, rejected
    # 525 mm: A_half = 0.1082376 -> V = 0.92389, between 0.9 and 1.2 -> accepted at the half-bore slope
    s = hy.size_reach(0.100, 0, raw_cfg["hydraulics"])
    assert s["d_mm"] == 525
    assert s["governs"] == "depth limit"
    assert s["depth_ratio"] == 0.5
    assert s["velocity"] == pytest.approx(0.92389, rel=1e-4)
    assert s["slope"] == pytest.approx(0.0021627, rel=2e-4)
    assert s["ok"]


def test_size_reach_two_thirds_bore_for_large_pipe(raw_cfg):
    # Q = 1.2 m3/s. Area at two-thirds bore = 0.5562257 D^2:
    # 1200 mm: 0.8009651 -> V = 1.4982 > 1.2, rejected ; 1350 mm: 1.0137214 -> V = 1.18376 -> accepted
    s = hy.size_reach(1.2, 0, raw_cfg["hydraulics"])
    assert s["d_mm"] == 1350
    assert s["depth_ratio"] == pytest.approx(2 / 3)
    assert s["velocity"] == pytest.approx(1.18376, rel=1e-4)


def test_size_reach_self_cleansing_governs(raw_cfg):
    # Q = 0.020 m3/s in a pipe held at 300 mm by the reach upstream:
    # A_half = pi * 0.09 / 8 = 0.0353429 -> V = 0.566 < 0.9, so steepen until V = 0.9 at A = 0.0222222
    s = hy.size_reach(0.020, 300, raw_cfg["hydraulics"])
    assert s["d_mm"] == 300 and s["governs"] == "self-cleansing velocity"
    assert s["velocity"] == pytest.approx(0.9, rel=1e-7)
    assert s["depth_ratio"] < 0.5
    assert hy.area(0.3, s["depth_ratio"]) == pytest.approx(0.0222222, rel=1e-6)
    assert s["ok"]


def test_size_reach_flags_flow_too_small_to_self_cleanse(raw_cfg):
    hp = raw_cfg["hydraulics"]
    s = hy.size_reach(0.001, 0, hp)
    assert s["d_mm"] == 200
    assert s["slope"] == hp["max_slope"]["value"]
    assert s["velocity"] < hp["v_min"]["value"]
    assert s["depth_ok"] and not s["velocity_ok"] and not s["ok"]
    assert hy.flow(0.2, s["depth_ratio"], s["slope"], N) == pytest.approx(0.001, rel=1e-7)


def test_size_reach_respects_ceiling_argument_and_minimum_diameter(raw_cfg):
    hp = raw_cfg["hydraulics"]
    # with the COPSSW target of 1.5 m/s as ceiling the 450 mm pipe (V = 1.2575) is accepted
    assert hy.size_reach(0.100, 0, hp, v_ceiling=1.5)["d_mm"] == 450
    assert hy.size_reach(0.100, 750, hp)["d_mm"] == 750
    with pytest.raises(ValueError):
        hy.size_reach(50.0, 0, hp)


def test_size_reach_goes_up_a_diameter_rather_than_exceed_the_maximum_grade(raw_cfg):
    # Q = 0.0226 m3/s: 225 mm at half bore gives V = 0.0226 / (pi * 0.050625 / 8) = 1.1368 m/s, inside the
    # limits, but needs S = (0.0226 * 0.013 / (0.0198804 * 0.05625^(2/3)))^2 = (0.000293800 / 0.0029186)^2
    # = 0.010133, steeper than 1 in 100. So 300 mm: V at half bore = 0.6395 < 0.9 -> steepened to 0.9 m/s.
    hp = raw_cfg["hydraulics"]
    assert hy.slope_for_flow_at_ratio(0.0226, 0.225, 0.5, N) == pytest.approx(0.010133, rel=1e-3)
    s = hy.size_reach(0.0226, 0, hp)
    assert s["d_mm"] == 300 and s["governs"] == "self-cleansing velocity"
    assert s["slope"] <= hp["max_slope"]["value"] and s["ok"]


def test_size_reach_never_picks_a_smaller_pipe_for_more_flow(raw_cfg):
    # Property behind mutant M15 in mutation/run_mutants.py: with d_min = 0 the chosen diameter is
    # non-decreasing in the peak flow (both acceptance tests, V at the limit depth <= ceiling and slope at the
    # limit depth <= max grade, only get harder as Q grows). Since flow only accumulates downstream, the
    # "carry the upstream diameter down" guard in network.design never binds on a gravity tree.
    hp = raw_cfg["hydraulics"]
    for v_ceiling in (1.0, 1.2, 1.5):
        prev = 0
        q = 0.0005
        while q < 2.0:
            d = hy.size_reach(q, 0, hp, v_ceiling=v_ceiling)["d_mm"]
            assert d >= prev, (q, d, prev, v_ceiling)
            prev = d
            q += 0.0025
