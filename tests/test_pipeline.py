"""Invariants of the full run, guards on the sentences in the README, and snapshot checks."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from sgsewer import cost, flows, pipeline, programme, readme
from sgsewer import hydraulics as hy

REPO = Path(__file__).resolve().parents[1]


def test_inputs_match_manifest():
    with (pipeline.INPUTS / "manifest.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 5
    for r in rows:
        assert hashlib.sha256((pipeline.INPUTS / r["file"]).read_bytes()).hexdigest() == r["sha256"], r["file"]


def test_design_basis_is_the_code_of_practice(raw_cfg):
    fc, hp = raw_cfg["flows"], raw_cfg["hydraulics"]
    assert (fc["lpcd_public"]["value"], fc["lpcd_private"]["value"]) == (230, 250)
    assert fc["peak_factor"]["value"] == 3.0 and fc["persons_per_dwelling"]["value"] == 3.5
    assert (hp["v_min"]["value"], hp["v_max"]["value"], hp["v_target_cop"]["value"]) == (0.9, 2.4, 1.5)
    assert hp["diameters_mm"][0] == 200 and hp["manhole_max_spacing_m"]["value"] == 120
    assert hp["min_cover_to_soffit_m"]["value"] == 1.5
    assert hp["v_min"]["value"] < hp["v_design_ceiling"]["value"] <= hp["v_target_cop"]["value"]


def test_town_flow_by_hand(res):
    f = res["summary"]["flows"]
    # 42,000 homes x 3.5 = 147,000 people x 235.7143 L = 34,650 m3/d residential
    assert f["homes"] == pytest.approx(42000.0)
    assert f["population"] == pytest.approx(147000.0)
    assert f["adwf_res_m3d"] == pytest.approx(34650.0)
    assert f["peak_ls"] == pytest.approx(3.0 * f["adwf_m3d"] / 86.4)
    assert sum(v["adwf_m3d"] for v in f["by_subzone"].values()) == pytest.approx(f["adwf_m3d"])
    assert sum(f["by_class_m3d"].values()) == pytest.approx(f["adwf_m3d"])


def test_flow_is_conserved_from_parcels_to_outlet(res):
    total = sum(r["adwf_m3d"] for r in res["flows"])
    assert res["summary"]["network"]["adwf_outlet_m3d"] == pytest.approx(total, rel=1e-12)
    assert res["summary"]["receiving_sewer"]["ultimate_peak_ls"] == pytest.approx(3.0 * total / 86.4)
    by = {r["id"]: r for r in res["rows"]}
    own = {t["id"]: sum(t["own_adwf"].values()) for t in res["tree"]["reaches"]}
    for r in res["rows"]:
        assert r["adwf_m3d"] == pytest.approx(own[r["id"]] + sum(by[u]["adwf_m3d"] for u in r["upstream_ids"]))
        assert r["q_peak_ls"] == pytest.approx(3.0 * r["adwf_m3d"] / 86.4)


def test_every_reach_obeys_the_rules(res):
    hp = res["cfg"]["hydraulics"]
    by = {r["id"]: r for r in res["rows"]}
    flagged = 0
    for r in res["rows"]:
        assert r["depth_ratio"] <= r["depth_limit"] + 1e-9
        assert r["d_mm"] >= hp["diameters_mm"][0]
        assert r["slope"] <= hp["max_slope"]["value"] + 1e-12
        if r["velocity_ok"]:
            assert hp["v_min"]["value"] - 1e-9 <= r["velocity"] <= hp["v_design_ceiling"]["value"] + 1e-9
        else:
            flagged += 1
            assert r["slope"] == hp["max_slope"]["value"] and r["d_mm"] == 200
        ups = [by[u] for u in r["upstream_ids"]]
        assert all(r["d_mm"] >= u["d_mm"] for u in ups)
        assert r["soffit_up_m"] == pytest.approx(max([hp["min_cover_to_soffit_m"]["value"]]
                                                     + [u["soffit_down_m"] for u in ups]))
        assert r["invert_down_m"] == pytest.approx(r["soffit_up_m"] + r["slope"] * r["length_m"] + r["d_mm"] / 1000)
        assert r["length_m"] / r["manholes"] <= hp["manhole_max_spacing_m"]["value"] + 1e-9
    n = res["summary"]["network"]
    assert flagged == n["reaches_not_self_cleansing"] == n["governs"]["maximum grade (not self-cleansing)"]
    assert sum(n["governs"].values()) == n["reaches"] == len(res["rows"])
    assert n["open_cut_m"] + n["jacking_m"] == pytest.approx(n["length_m"])
    assert n["trunk_m"] + n["branch_m"] == pytest.approx(n["length_m"])


def test_budget_adds_up(res):
    s = res["summary"]
    cc = res["cfg"]["cost"]
    direct = sum(c["direct"] for c in res["costs"]["central"].values())
    assert s["cost"]["budget"]["central"]["direct"] == pytest.approx(direct)
    assert s["cost"]["budget"]["central"]["budget"] == pytest.approx(cost.gross_up(direct, cc, "central")["budget"])
    assert sum(p["budget"] for p in res["packages"]) == pytest.approx(s["cost"]["budget"]["central"]["budget"])
    assert sum(p["budget_low"] for p in res["packages"]) == pytest.approx(s["cost"]["budget"]["low"]["budget"])
    assert sum(len(p["reaches"]) for p in res["packages"]) == len(res["rows"])
    assert s["cost"]["budget"]["low"]["budget"] < s["cost"]["budget"]["central"]["budget"] \
        < s["cost"]["budget"]["high"]["budget"]
    assert cc["oncosts"]["ac_and_monitoring"]["central"] == pytest.approx(s["cost"]["oncosts_gebiz"]["central"])


def test_cashflow_adds_up_to_the_budget(res):
    b, s = res["budget"], res["summary"]
    total = s["cost"]["budget"]["central"]["budget"]
    assert sum(b["monthly_constant"].values()) == pytest.approx(total)
    assert sum(b["fy_constant"].values()) == pytest.approx(total)
    assert b["block_constant"] == pytest.approx(sum(b["fy_constant"][f] for f in range(2027, 2032)))
    for p in res["packages"]:
        assert sum(b["fy_by_package"][p["id"]].values()) == pytest.approx(p["budget"])
    for t in res["timing"]:
        assert sum(t["fy_constant"].values()) == pytest.approx(total)   # timing moves money, it does not make any
    base = next(t for t in res["timing"] if t["shift_years"] == 0)
    assert base["block_constant"] == pytest.approx(b["block_constant"])


def test_schedule_is_consistent(res):
    pc = res["cfg"]["programme"]
    sched = res["schedule"]
    assert sched["funding_approved_month"] == sched["planning_months"] + sched["funding_months"]
    assert sched["funding_months"] == programme.funding_months(sched["scheme_budget"], pc)[0]
    for x in sched["packages"]:
        assert x["consultant_start"] >= sched["funding_approved_month"]
        assert x["construction_end"] - x["consultant_start"] == x["lead_time_months"]
        assert x["late_months"] == max(0, -x["float_months"])
        assert x["dlp_end"] == x["construction_end"] + pc["defects_liability_months"]["value"]


def test_sentences_in_the_readme_still_hold(res):
    """The README template states these in words; if a change of inputs breaks one, rewrite the text."""
    s, hp = res["summary"], res["cfg"]["hydraulics"]
    n = s["network"]
    assert n["all_depth_ok"]
    assert n["v_max"] < hp["v_target_cop"]["value"]                       # "no reach reaches the target"
    t = {x["shift_years"]: x for x in res["timing"]}
    assert t[-1]["block_constant"] > t[0]["block_constant"] > t[1]["block_constant"]
    up = t[-1]["block_constant"] / t[0]["block_constant"] - 1
    down = 1 - t[1]["block_constant"] / t[0]["block_constant"]
    assert up > s["cost"]["range_high_pct"] and down > -s["cost"]["range_low_pct"]   # timing beats the cost range
    assert t[-1]["packages_late"] >= 1 and t[0]["packages_late"] == 0
    assert s["cost"]["jacking_share_of_direct"] > n["jacking_m"] / n["length_m"] > 0.25
    tr = {x["v_ceiling"]: x for x in res["tradeoff"]}
    budgets = [x["budget_central"] for x in tr.values()]
    assert (max(budgets) - min(budgets)) / s["cost"]["budget"]["central"]["budget"] < 0.05   # "barely moves"
    assert tr[1.5]["v_mean"] < 1.2 < hp["v_target_cop"]["value"]          # target not reached even then
    assert tr[1.0]["mean_invert_depth_m"] < tr[1.2]["mean_invert_depth_m"] < tr[1.5]["mean_invert_depth_m"]
    sens = {x["case"]: x for x in res["sensitivity"]}
    fewer = next(v for k, v in sens.items() if "persons per dwelling" in k)
    assert fewer["peak_outlet_ls"] < sens["base"]["peak_outlet_ls"]
    assert fewer["budget_central"] > sens["base"]["budget_central"]      # "a lower flow is not cheaper here"
    assert fewer["jacking_m"] > sens["base"]["jacking_m"]
    j = s["cost"]["jacking_norm_contract_per_m"]
    for b in s["cost"]["benchmarks"]:
        assert j["low"] < b["sgd_per_m"] < j["high"]
    g = s["cost"]["gebiz_packages"]
    assert all(g["min"] < p["budget"] < g["max"] for p in res["packages"])
    assert s["programme"]["fy_constant"][2027] == 0.0                     # "the first years are empty"
    snaps = {x["id"]: x for x in res["tree"]["snaps"]}
    assert n["parcels_at_outlet"] == sum(1 for x in snaps.values() if x["node"] == res["tree"]["outlet"]) > 0
    assert len(res["packages"]) == 5


def test_sensitivities_move_the_right_way(res):
    sens = {x["case"]: x for x in res["sensitivity"]}
    # rougher pipes need steeper slopes: more of the network ends up below the open-cut limit.
    # (The deepest point is not monotonic in n, because the slope cap moves reaches between diameters.)
    assert sens["Manning n = 0.011"]["jacking_m"] < sens["base"]["jacking_m"] < sens["Manning n = 0.015"]["jacking_m"]
    assert hy.slope_for_flow_at_ratio(0.1, 0.525, 0.5, 0.015) == pytest.approx(
        hy.slope_for_flow_at_ratio(0.1, 0.525, 0.5, 0.011) * (0.015 / 0.011) ** 2)
    ind = next(v for k, v in sens.items() if k.startswith("industrial"))
    extra = 2 * res["summary"]["flows"]["by_class_m3d"]["industrial_b2"]
    assert ind["adwf_outlet_m3d"] == pytest.approx(sens["base"]["adwf_outlet_m3d"] + extra)
    obs = res["summary"]["household_size_observed"]
    fewer = next(v for k, v in sens.items() if "persons per dwelling" in k)
    f = res["summary"]["flows"]
    assert fewer["adwf_outlet_m3d"] == pytest.approx(f["adwf_res_m3d"] * obs / 3.5 + f["adwf_nonres_m3d"])


def test_parcels_file_is_what_the_flows_use():
    parcels = flows.read_parcels(pipeline.INPUTS / "parcels.csv")
    assert len(parcels) == 205
    # the planning area is 736 ha in the URA boundary file; the clipped parcels cover it
    assert sum(p["area_m2"] for p in parcels) / 1e4 == pytest.approx(736.3, abs=0.5)


# ----------------------------------------------------------------------------------------- snapshots
def _same(a, b, path=""):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            _same(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-7, abs=1e-6), path
    else:
        assert a == b, path


def _cells(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        out = []
        for row in csv.reader(fh):
            cells = []
            for c in row:
                try:
                    cells.append(float(c))
                except ValueError:
                    cells.append(c)
            out.append(cells)
        return out


def test_snapshot_committed_results_are_current(res, tmp_path):
    pipeline.write(res, tmp_path)
    fresh = sorted(p.name for p in tmp_path.iterdir())
    committed = sorted(p.name for p in pipeline.RESULTS.iterdir() if p.is_file() and p.name != "mutation_report.json")
    assert fresh == committed
    for name in fresh:
        if name.endswith(".json"):
            _same(json.loads((tmp_path / name).read_text(encoding="utf-8")),
                  json.loads((pipeline.RESULTS / name).read_text(encoding="utf-8")), name)
        else:
            a, b = _cells(tmp_path / name), _cells(pipeline.RESULTS / name)
            assert len(a) == len(b), name
            for i, (ra, rb) in enumerate(zip(a, b)):
                assert len(ra) == len(rb), f"{name} row {i}"
                for x, y in zip(ra, rb):
                    if isinstance(x, float) and isinstance(y, float):
                        assert x == pytest.approx(y, rel=1e-6, abs=0.011), f"{name} row {i}"
                    else:
                        assert x == y, f"{name} row {i}"


def test_snapshot_readme_and_brief_are_generated_from_results():
    for rel, text in readme.build().items():
        assert (REPO / rel).read_text(encoding="utf-8") == text, f"{rel} is stale: run scripts/run_all.py"
        assert "{{" not in text


def test_readme_says_what_it_is():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "personal desk study, not a PUB plan" in text
    assert "SYNTHETIC" in text and "ASSUMPTION" in text
    brief = (REPO / "docs" / "funding_brief.md").read_text(encoding="utf-8")
    assert "not a PUB paper or a PUB plan" in brief


def test_template_placeholder_without_value_is_an_error():
    with pytest.raises(KeyError):
        readme.render("a {{nope}} b", {"x": "1"})
    assert readme.render("a {{x}} b", {"x": "1"}) == "a 1 b"
