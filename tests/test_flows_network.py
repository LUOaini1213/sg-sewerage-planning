"""Flow projection and the tree builder on tiny hand-made cases."""
import math

import pytest

from sgsewer import capacity, flows, network


def test_blended_per_capita_flow_by_hand(raw_cfg):
    # (30,000 x 230 + 12,000 x 250) / 42,000 = (6,900,000 + 3,000,000) / 42,000 = 235.7143
    assert flows.blended_lpcd(raw_cfg["flows"]) == pytest.approx(235.7143, rel=1e-6)


def test_nonres_rate_by_hand():
    # 1.1 m3/m2/year = 1100 L / 365 d = 3.013699 L/m2/d ; x 0.9 return factor = 2.712329
    assert flows.nonres_lpd_per_m2(1.1, 0.9) == pytest.approx(2.712329, rel=1e-6)


def test_projection_on_three_parcels_by_hand(raw_cfg):
    fc = raw_cfg["flows"]
    parcels = [
        {"id": "A", "lu_desc": "RESIDENTIAL", "gpr": "2.0", "area_m2": 10000.0, "x": 0, "y": 0, "subzone": "S1"},
        {"id": "B", "lu_desc": "COMMERCIAL & RESIDENTIAL", "gpr": "3.0", "area_m2": 10000.0, "x": 0, "y": 0,
         "subzone": "S1"},
        {"id": "C", "lu_desc": "BUSINESS 2", "gpr": "SDP", "area_m2": 5000.0, "x": 0, "y": 0, "subzone": "S2"},
        {"id": "D", "lu_desc": "PARK", "gpr": "EVA", "area_m2": 9000.0, "x": 0, "y": 0, "subzone": "S2"},
    ]
    out = {r["id"]: r for r in flows.project(parcels, fc)}
    assert set(out) == {"A", "B", "C"}  # parks generate nothing
    # residential GFA: A = 10,000 x 2.0 = 20,000 ; B = 10,000 x 3.0 x 0.6 = 18,000 ; total 38,000
    # homes: A = 42,000 x 20/38 = 22,105.263 ; B = 42,000 x 18/38 = 19,894.737
    assert out["A"]["homes"] == pytest.approx(22105.263, rel=1e-7)
    assert out["B"]["homes"] == pytest.approx(19894.737, rel=1e-7)
    # A: 22,105.263 homes x 3.5 = 77,368.42 people x 235.7143 L = 18,236.84 m3/d
    assert out["A"]["population"] == pytest.approx(77368.42, rel=1e-7)
    assert out["A"]["adwf_m3d"] == pytest.approx(18236.84, rel=1e-6)
    # B commercial part: 10,000 x 3.0 x 0.4 = 12,000 m2 x 2.712329 L = 32.548 m3/d
    assert out["B"]["nonres_gfa_m2"] == pytest.approx(12000.0)
    assert out["B"]["adwf_nonres_m3d"] == pytest.approx(32.548, rel=1e-4)
    # C: plot ratio assumed 1.0 -> 5,000 m2 x (1.0 x 1000 / 365 x 0.9 = 2.465753 L) = 12.3288 m3/d
    assert out["C"]["plot_ratio_assumed"] is True
    assert out["C"]["adwf_m3d"] == pytest.approx(12.3288, rel=1e-5)
    # peak = 3 x ADWF: C -> 3 x 12.3288 m3/d = 36.9863 m3/d = 0.42808 L/s
    assert out["C"]["peak_ls"] == pytest.approx(0.42808, rel=1e-4)
    # industrial factor multiplies only the B2 parcel
    out3 = {r["id"]: r for r in flows.project(parcels, fc, industrial_factor=3.0)}
    assert out3["C"]["adwf_m3d"] == pytest.approx(3 * 12.3288, rel=1e-5)
    assert out3["B"]["adwf_m3d"] == pytest.approx(out["B"]["adwf_m3d"])
    # persons per dwelling scales the residential flow only
    out2 = {r["id"]: r for r in flows.project(parcels, fc, persons_per_dwelling=1.75)}
    assert out2["A"]["adwf_m3d"] == pytest.approx(out["A"]["adwf_m3d"] / 2)
    t = flows.totals(list(out.values()), fc)
    assert t["homes"] == pytest.approx(42000.0)
    assert t["by_subzone"]["S2"]["adwf_m3d"] == pytest.approx(12.3288, rel=1e-5)
    assert t["peak_ls"] == pytest.approx(3 * t["adwf_m3d"] / 86.4, rel=1e-12)


def test_unknown_land_use_is_an_error(raw_cfg):
    with pytest.raises(KeyError):
        flows.project([{"id": "X", "lu_desc": "SPACEPORT", "gpr": "1", "area_m2": 1.0, "x": 0, "y": 0,
                        "subzone": "S"}], raw_cfg["flows"])


def tiny_graph():
    #   3
    #   |
    #   1 --- 2        node 0 is the westmost: the outlet
    #   |
    #   0 at x = -1
    nodes = [[-1.0, 0.0], [100.0, 0.0], [200.0, 0.0], [100.0, 100.0], [100.0, 300.0]]
    edges = [[0, 1, 101.0, "residential", "open", "Main Road"], [1, 2, 100.0, "residential", "open", "East Road"],
             [1, 3, 100.0, "residential", "open", "North Road"], [3, 4, 200.0, "residential", "open", "North Road"]]
    adj = {i: [] for i in range(len(nodes))}
    for k, (a, b, length, *_x) in enumerate(edges):
        adj[a].append((b, length, k))
        adj[b].append((a, length, k))
    return {"nodes": nodes, "edges": edges, "adj": adj}


def test_tree_accumulates_flow_and_orders_reaches():
    g = tiny_graph()
    assert network.pick_outlet(g, "westmost node of the road graph") == 0
    dist, nxt = network.dijkstra(g["adj"], 0)
    assert dist[4] == pytest.approx(401.0) and nxt[4] == 3 and nxt[2] == 1
    loads = [{"id": "a", "x": 205.0, "y": 2.0, "subzone": "S1", "adwf_m3d": 864.0},
             {"id": "b", "x": 101.0, "y": 99.0, "subzone": "S2", "adwf_m3d": 1728.0},
             {"id": "c", "x": 190.0, "y": -5.0, "subzone": "S2", "adwf_m3d": 100.0}]
    t = network.build_tree(g, loads, 0)
    r = {(x["up"], x["down"]): x for x in t["reaches"]}
    assert set(r) == {(2, 1), (3, 1), (1, 0)}  # node 4 carries no load: no sewer there
    assert r[(2, 1)]["adwf_m3d"] == pytest.approx(964.0)
    assert r[(3, 1)]["adwf_m3d"] == pytest.approx(1728.0)
    assert r[(1, 0)]["adwf_m3d"] == pytest.approx(2692.0)
    assert r[(1, 0)]["adwf_by_subzone"] == pytest.approx({"S1": 864.0, "S2": 1828.0})
    assert r[(1, 0)]["length_m"] == pytest.approx(101.0)
    assert r[(1, 0)]["down_id"] == "OUTLET" and sorted(r[(1, 0)]["upstream_ids"]) == ["R001", "R002"]
    assert [x["id"] for x in t["reaches"]][-1] == r[(1, 0)]["id"]  # upstream reaches come first
    snap = {s["id"]: s for s in t["snaps"]}
    assert snap["a"]["node"] == 2 and snap["a"]["snap_m"] == pytest.approx(math.hypot(5, 2))
    assert network.reach_road(t, r[(3, 1)]) == "North Road"


def test_levels_match_soffits_and_diameters_do_not_shrink(raw_cfg):
    hp = raw_cfg["hydraulics"]
    g = tiny_graph()
    loads = [{"id": "a", "x": 200.0, "y": 0.0, "subzone": "S1", "adwf_m3d": 864.0},      # 30 L/s peak
             {"id": "b", "x": 100.0, "y": 300.0, "subzone": "S2", "adwf_m3d": 1728.0}]   # 60 L/s peak
    rows = {r["id"]: r for r in network.design(network.build_tree(g, loads, 0), hp, 3.0)}
    assert len(rows) == 3
    last = next(r for r in rows.values() if r["down_id"] == "OUTLET")
    ups = [rows[i] for i in last["upstream_ids"]]
    assert len(ups) == 2
    assert last["q_peak_ls"] == pytest.approx(90.0)
    assert last["d_mm"] >= max(u["d_mm"] for u in ups)
    for u in ups:
        # head reaches start at the minimum cover; fall = slope x length
        assert u["soffit_up_m"] == pytest.approx(1.5)
        assert u["soffit_down_m"] == pytest.approx(1.5 + u["slope"] * u["length_m"])
        assert u["invert_up_m"] == pytest.approx(1.5 + u["d_mm"] / 1000)
    # the outgoing soffit sits at the lowest incoming soffit
    assert last["soffit_up_m"] == pytest.approx(max(u["soffit_down_m"] for u in ups))
    assert last["mean_invert_depth_m"] == pytest.approx((last["invert_up_m"] + last["invert_down_m"]) / 2)
    # manholes: one per started 120 m. Lengths here are 100, 300 and 101 m
    assert sorted(r["manholes"] for r in rows.values()) == [1, 1, 3]


def test_receiving_sewer_capacity_and_trigger_by_hand(raw_cfg):
    hp = raw_cfg["hydraulics"]
    # 900 mm, half bore, 1.5 m/s: 1.5 x pi x 0.81 / 8 = 0.4771294 m3/s
    assert capacity.capacity_at_limit(900, hp, 1.5) == pytest.approx(0.4771294, rel=1e-6)
    # 1500 mm, two-thirds bore: 1.5 x 0.5562257 x 2.25 = 1.8772617 m3/s
    assert capacity.capacity_at_limit(1500, hp, 1.5) == pytest.approx(1.8772617, rel=1e-6)
    rc = {"diameters_mm": [900, 1500], "existing_use_share": [0.0, 0.5],
          "design_velocity_at_limit_depth": {"value": 1.5}}
    series = [{"fy": 2030, "peak_ls": 200.0}, {"fy": 2031, "peak_ls": 400.0}, {"fy": 2032, "peak_ls": 500.0}]
    t = {(r["d_mm"], r["existing_use_share"]): r for r in capacity.trigger_table(series, rc, hp)}
    assert t[(900, 0.0)]["trigger_fy"] == 2032      # 477 L/s spare: 500 exceeds it
    assert t[(900, 0.5)]["trigger_fy"] == 2031      # 238.6 L/s spare: 400 exceeds it
    assert t[(900, 0.5)]["spare_ls"] == pytest.approx(238.5647, rel=1e-6)
    assert t[(1500, 0.5)]["trigger_fy"] is None     # 938.6 L/s spare
    assert capacity.smallest_adequate(list(t.values()), 0.0) == 1500
