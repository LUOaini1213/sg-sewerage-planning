"""Cost build-ups and cashflow arithmetic against hand calculations."""
import pytest

from sgsewer import cost, pipeline, programme

ESC = 140.2 / 117.1  # BCA TPI 1Q2026 / 2021 = 1.197267


def test_escalation_factor(cfg):
    assert cost.escalation(cfg["cost"]) == pytest.approx(1.197267, rel=1e-6)
    r = cost.rates(cfg["cost"], "central")
    assert r["excavation_per_m3"] == pytest.approx(26 * ESC)          # handbook rate, escalated
    assert r["backfill_per_m3"] == 15                                # assumed rate, already at the price base
    assert cost.rates(cfg["cost"], "high")["disposal_per_m3"] == pytest.approx(26 * ESC)


def test_open_cut_per_metre_by_hand(cfg):
    # 600 mm, invert 4.0 m deep, central.
    # outside diameter 0.72 m, wall 0.06 m; trench width = 0.72 + 2 x 0.3 = 1.32 m
    # trench depth = 4.0 + 0.06 + 0.15 = 4.21 m; excavation = 1.32 x 4.21 = 5.5572 m3 per m
    exc = 5.5572 * 26 * ESC * 2.0                 # deeper than 4 m: factor 2.0            = 345.98
    disp = 5.5572 * 0.4 * 23 * ESC                # 40% carted away                        =  61.21
    shore = 2 * 4.21 * 100 * 2.0                  # both faces, deep factor 2              = 1684.00
    pipe_vol = 3.141592653589793 * 0.72 ** 2 / 4  # 0.407150 m3 per m
    bed_vol = 1.32 * (0.15 + 0.25 * 0.72) - 0.25 * pipe_vol   # 0.4356 - 0.101788 = 0.333812
    bed = bed_vol * 241.5 * ESC                   #                                        =  96.52
    pipe = 0.55 * 600 * (1 + 0.6)                 #                                        = 528.00
    back = (5.5572 - pipe_vol - bed_vol) * 15     # 4.816238 m3                            =  72.24
    reinst = (1.32 + 1.0) * 120                   #                                        = 278.40
    c = cost.open_cut_per_m(600, 4.0, cfg["cost"], "central")
    assert c["excavation"] == pytest.approx(exc) and exc == pytest.approx(345.98, abs=0.01)
    assert c["disposal"] == pytest.approx(disp) and disp == pytest.approx(61.21, abs=0.01)
    assert c["shoring"] == pytest.approx(shore)
    assert c["bedding"] == pytest.approx(bed) and bed == pytest.approx(96.52, abs=0.01)
    assert c["pipe"] == pytest.approx(pipe)
    assert c["backfill"] == pytest.approx(back) and back == pytest.approx(72.24, abs=0.01)
    assert c["reinstatement"] == pytest.approx(reinst)
    assert c["direct"] == pytest.approx(3066.35, abs=0.02)


def test_open_cut_shallow_trench_has_no_shoring_and_minimum_width(cfg):
    # 200 mm at 1.2 m invert: trench depth 1.2 + 0.02 + 0.15 = 1.37 m, not above 1.5 m -> no shoring
    # width = max(0.24 + 0.6, 0.9) = 0.9 m ; excavation factor 1.0
    assert cost.trench_width(200, cfg["cost"]["geometry"]) == pytest.approx(0.9)
    c = cost.open_cut_per_m(200, 1.2, cfg["cost"], "central")
    assert c["shoring"] == 0.0
    assert c["excavation"] == pytest.approx(0.9 * 1.37 * 26 * ESC)
    # between 2 m and 4 m the excavation factor is 1.5 and the shoring is not doubled
    c3 = cost.open_cut_per_m(300, 3.0, cfg["cost"], "central")    # trench 0.96 m wide, 3.18 m deep
    assert c3["excavation"] == pytest.approx(0.96 * 3.18 * 26 * ESC * 1.5)
    assert c3["shoring"] == pytest.approx(2 * 3.18 * 100)


def test_manhole_by_hand(cfg):
    # 600 mm pipe, invert 4.0 m: chamber 1.2 m square inside, walls 0.25 m, depth 4.3 m, outside 1.7 m
    concrete = (1.7 ** 2 - 1.2 ** 2) * 4.3 + 1.7 ** 2 * 0.55          # 6.235 + 1.5895 = 7.8245 m3
    c = cost.manhole_cost(600, 4.0, cfg["cost"], "central")
    assert concrete == pytest.approx(7.8245)
    assert c["concrete"] == pytest.approx(7.8245 * 162 * ESC)          # 1517.61
    assert c["rebar"] == pytest.approx(7.8245 * 120 * 2.0 * ESC)       # 2248.32
    assert c["formwork"] == pytest.approx(4 * 2.9 * 4.3 * 51 * ESC)    # 49.88 m2 -> 3045.70
    assert c["lining"] == pytest.approx(4 * 1.2 * 4.3 * 100)           # 2064
    assert c["excavation_and_support"] == pytest.approx(2.7 ** 2 * 4.6 * (26 + 23) * ESC + 4 * 2.7 * 4.3 * 100)
    assert c["fitout"] == pytest.approx(2500)
    assert c["direct"] == pytest.approx(17986.9, abs=0.2)
    assert cost.manhole_cost(900, 4.0, cfg["cost"], "central")["fitout"] == pytest.approx(2500 * 1.8 / 1.2)


def test_jacking_shaft_and_method_switch(cfg):
    cc = cfg["cost"]
    assert cost.jacking_per_m(600, cc, "central")["direct"] == pytest.approx(3000 + 6.0 * 600)
    assert cost.jacking_per_m(600, cc, "high")["direct"] == pytest.approx(4200 + 8.4 * 600)
    assert cost.shaft_cost(600, 8.0, cc, "central")["direct"] == pytest.approx(40000 + 12000 * 8)
    assert cost.shaft_cost(1200, 8.0, cc, "central")["direct"] == pytest.approx((40000 + 12000 * 8) * 1.6)
    assert cost.method_for(6.0, cc) == "open cut"
    assert cost.method_for(6.01, cc) == "pipe jacking"


def test_gross_up_by_hand(cfg):
    # direct 1000: preliminaries 15% = 150 -> contract 1150
    # contingency 20% of 1150 = 230 ; engineering 8% = 92 ; checker and monitoring 2% = 23 ; budget 1495
    g = cost.gross_up(1000.0, cfg["cost"], "central")
    assert (g["preliminaries"], g["contract"]) == pytest.approx((150.0, 1150.0))
    assert g["contingency"] == pytest.approx(230.0)
    assert g["pes_fee"] == pytest.approx(92.0)
    assert g["ac_and_monitoring"] == pytest.approx(23.0)
    assert g["budget"] == pytest.approx(1495.0)
    # low: 1000 x 1.10 = 1100 ; x (1 + 0.10 + 0.05 + 0.02) = 1287
    assert cost.gross_up(1000.0, cfg["cost"], "low")["budget"] == pytest.approx(1287.0)


def test_reach_cost_and_norm_table(cfg):
    cc, hp = cfg["cost"], cfg["hydraulics"]
    row = {"d_mm": 600, "mean_invert_depth_m": 4.0, "length_m": 250.0, "manholes": 3}
    c = cost.reach_cost(row, cc, "central")
    assert c["method"] == "open cut"
    assert c["direct"] == pytest.approx(250 * 3066.35 + 3 * 17986.9, rel=1e-5)
    deep = cost.reach_cost({**row, "mean_invert_depth_m": 8.0}, cc, "central")
    assert deep["method"] == "pipe jacking"
    assert deep["direct"] == pytest.approx(250 * 6600 + 3 * 136000)
    norms = {(n["d_mm"], n["invert_depth_m"]): n for n in cost.norm_table(cc, hp, [2.0, 4.0, 8.0])}
    n = norms[(600, 4.0)]
    # norm = (pipeline + one manhole per 120 m) grossed up: (3066.35 + 17986.9 / 120) x 1.15 x 1.30 = 4808.3
    assert n["direct_central"] == pytest.approx(3066.35 + 17986.9 / 120, rel=1e-5)
    assert n["budget_central"] == pytest.approx((3066.35 + 17986.9 / 120) * 1.15 * 1.30, rel=1e-5)
    assert n["budget_low"] < n["budget_central"] < n["budget_high"]
    assert (1200, 2.0) not in norms          # 1.5 m cover + 1.2 m pipe does not fit in 2.0 m
    assert norms[(600, 8.0)]["method"] == "pipe jacking"


def test_gebiz_oncost_ratios_by_hand(raw_cfg):
    awards = pipeline.read_csv(pipeline.INPUTS / "gebiz_pub_sewer_awards.csv")
    o = pipeline.gebiz_oncosts(awards, raw_cfg["gebiz_oncost_pairs"])
    r = {x["service_tender"]: x["ratio"] for x in o["rows"]}
    assert r["PUB000ETT24000060"] == pytest.approx(168000 / (12870000 + 34811800))        # 0.352%
    assert r["PUB000ETT25000037"] == pytest.approx(345000 / (52606250 + 116920038))       # 0.204%
    assert r["PUB000ETT25000062"] == pytest.approx(185000 / 35330000)                     # 0.524%
    assert r["PUB000ETT23000196"] == pytest.approx(885445 / 47681800)                     # 1.857%
    mean_ac = (0.0035234 + 0.0020351 + 0.0052363) / 3
    assert o["central"] == pytest.approx(mean_ac + 0.0185699, rel=1e-4)
    assert o["low"] == pytest.approx(0.0020351 + 0.0185699, rel=1e-4)
    assert o["high"] == pytest.approx(0.0052363 + 0.0185699, rel=1e-4)


# ------------------------------------------------------------------------------------------ programme
def test_calendar_helpers():
    assert programme.month_index("2033-04", "2027-04") == 72
    assert programme.month_index("2028-01", "2027-04") == 9
    assert programme.month_label(9, "2027-04") == "2028-01"
    assert programme.month_label(0, "2027-04") == "2027-04"
    # financial year runs April to March: month 11 is March 2028, still FY2027
    assert [programme.fy_of_month(m, 2027) for m in (0, 11, 12, 23, 24)] == [2027, 2027, 2028, 2028, 2029]


def test_s_curve_values():
    assert programme.s_curve(0.0) == 0.0 and programme.s_curve(1.0) == 1.0
    assert programme.s_curve(0.5) == pytest.approx(0.5)
    assert programme.s_curve(0.25) == pytest.approx(3 / 16 - 2 / 64)      # 0.15625
    assert programme.s_curve(1.7) == 1.0


def test_funding_route_thresholds(raw_cfg):
    pc = raw_cfg["programme"]
    assert programme.funding_months(99e6, pc)[0] == pc["funding_approval_months"]["below_100m"]
    assert programme.funding_months(150e6, pc)[0] == pc["funding_approval_months"]["from_100m"]
    assert programme.funding_months(500e6, pc)[0] == pc["funding_approval_months"]["from_500m"]


def test_construction_duration(raw_cfg):
    pc = raw_cfg["programme"]
    # 300 m/month open cut and 150 m/month jacked: 1000/300 + 300/150 = 5.33 -> 6, but never under 12
    assert programme.construction_months(1000, 300, pc) == 12
    # 6000/300 + 1500/150 = 20 + 10 = 30
    assert programme.construction_months(6000, 1500, pc) == 30
    assert programme.construction_months(6001, 1500, pc) == 31


PKG = {"id": "P", "subzone": "S", "need_date": "2033-04", "open_cut_m": 3000.0, "jacking_m": 0.0,
       "contract": 1000.0, "contingency": 200.0, "pes_fee": 80.0, "ac_and_monitoring": 24.0, "budget": 1304.0}
SCHED = {"id": "P", "design_start": 0, "tender_start": 12, "construction_start": 18, "construction_months": 12,
         "construction_end": 30, "dlp_end": 42}


def test_package_cashflow_by_hand(raw_cfg):
    cf = programme.package_cashflow(PKG, SCHED, raw_cfg["programme"])
    # design: 40% of the 80 fee over 12 months = 2.6667 a month ; tender: 10% over 6 months = 1.3333
    assert cf[0] == pytest.approx(80 * 0.4 / 12) and cf[11] == pytest.approx(80 * 0.4 / 12)
    assert cf[12] == pytest.approx(80 * 0.1 / 6)
    # first construction month: works value 1200 x S(1/12) = 1200 x (3/144 - 2/1728) = 23.6111 certified,
    # 95% paid = 22.4306 ; plus fee 80 x 0.5 / 12 = 3.3333 ; plus checker and monitoring 24 / 12 = 2
    assert cf[18] == pytest.approx(22.4306 + 3.3333 + 2.0, abs=1e-3)
    # retention 5% of 1200 = 60: 30 at completion (month 30), 30 at the end of defects liability (month 42)
    assert cf[30] == pytest.approx(30.0) and cf[42] == pytest.approx(30.0)
    assert sum(cf.values()) == pytest.approx(1304.0)


def test_financial_year_roll_up_by_hand(raw_cfg):
    sched = {"packages": [SCHED]}
    b = programme.budget([PKG], sched, raw_cfg["programme"], "2027-04", 2027, 2)
    fy = b["fy_constant"]
    # FY2027 (months 0-11): design fee 32
    # FY2028 (12-23): tender fee 8 + first half of construction: 600 certified x 0.95 = 570, fee 20, checker 12 = 610
    # FY2029 (24-35): 570 + 20 + 12 + retention 30 = 632 ; FY2030: retention 30
    assert fy[2027] == pytest.approx(32.0)
    assert fy[2028] == pytest.approx(610.0)
    assert fy[2029] == pytest.approx(632.0)
    assert fy[2030] == pytest.approx(30.0)
    assert b["total_constant"] == pytest.approx(1304.0)
    assert b["block_years"] == [2027, 2028]
    assert b["block_constant"] == pytest.approx(642.0)
    assert b["block_share"] == pytest.approx(642.0 / 1304.0)
    assert b["peak_fy"] == 2029 and b["peak_fy_constant"] == pytest.approx(632.0)
    # outturn: month 0 is April 2027, 14 months after the price base (February 2026)
    assert programme.outturn_factor(0, "2027-04", 0.03) == pytest.approx(1.03 ** (14 / 12), rel=1e-12)
    assert programme.outturn_factor(10, "2027-04", 0.03) == pytest.approx(1.03 ** 2, rel=1e-12)
    assert b["fy_outturn"][2030] == pytest.approx(30.0 * 1.03 ** ((14 + 42) / 12))
    assert b["total_outturn"] > b["total_constant"]


def test_schedule_back_from_need_date_by_hand(raw_cfg):
    pc = raw_cfg["programme"]
    # scheme of S$ 50 m: planning 6 + funding 4 -> approved at month 10
    # need April 2033 = month 72; ready 3 months before = 69; construction 12 (3000 m / 300 = 10 -> minimum 12)
    # latest consultant start = 69 - 12 - 6 - 12 - 6 = 33 ; float = 33 - 10 = 23
    p = {**PKG, "budget": 50e6}
    s = programme.schedule([p], pc, "2027-04")
    x = s["packages"][0]
    assert s["funding_approved_month"] == 10
    assert (x["consultant_start"], x["design_start"], x["tender_start"], x["construction_start"]) == (33, 39, 51, 57)
    assert (x["construction_end"], x["dlp_end"]) == (69, 81)
    assert (x["float_months"], x["late_months"]) == (23, 0)
    # three years earlier: latest start would be month -3, before approval: start at 10, ready at 46, need 33
    y = programme.schedule([p], pc, "2027-04", shift_years=-3)["packages"][0]
    assert y["consultant_start"] == 10 and y["construction_end"] == 46
    assert (y["float_months"], y["late_months"]) == (-13, 13)


def test_buildout_and_flow_by_year(raw_cfg):
    assert programme.buildout_share(2032, 2033, 6) == 0.0
    assert programme.buildout_share(2033, 2033, 6) == pytest.approx(1 / 6)
    assert programme.buildout_share(2038, 2033, 6) == 1.0
    pc = raw_cfg["programme"]
    need = {"A": "2033-04", "B": "2034-04"}
    rows = {r["fy"]: r for r in programme.flow_by_fy({"A": 600.0, "B": 1200.0}, need, pc, "2027-04", 2027, 3.0)}
    # FY2034: A is in its second year (2/6 x 600 = 200), B in its first (1/6 x 1200 = 200) -> 400 m3/d
    assert rows[2034]["adwf_m3d"] == pytest.approx(400.0)
    assert rows[2034]["peak_ls"] == pytest.approx(3 * 400.0 / 86.4)
    assert rows[max(rows)]["adwf_m3d"] == pytest.approx(1800.0)


def test_packages_take_the_earliest_needed_subzone(cfg):
    rows = [{"id": "R1", "adwf_by_subzone": {"LATE": 5.0}, "length_m": 100.0, "manholes": 1, "d_mm": 200},
            {"id": "R2", "adwf_by_subzone": {"LATE": 5.0, "EARLY": 1.0}, "length_m": 50.0, "manholes": 1, "d_mm": 300}]
    costs = {"R1": {"method": "open cut", "direct": 1000.0}, "R2": {"method": "pipe jacking", "direct": 3000.0}}
    pk = programme.make_packages(rows, costs, {"EARLY": "2030-04", "LATE": "2035-04", "_note": "x"}, cfg["cost"])
    assert [(p["id"], p["subzone"], p["reaches"]) for p in pk] == [("PKG1", "EARLY", ["R2"]), ("PKG2", "LATE", ["R1"])]
    assert pk[0]["jacking_m"] == 50.0 and pk[0]["open_cut_m"] == 0.0 and pk[0]["max_d_mm"] == 300
    assert pk[0]["budget"] == pytest.approx(3 * 1495.0)   # gross-up of the hand check above
