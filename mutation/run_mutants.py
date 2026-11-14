"""Mutation test of the test suite.

Each mutant is one deliberate bug: a single exact-string replacement in the source. For every mutant the
files the tests need are copied to a scratch directory, the bug is applied, and the full pytest suite runs.
A mutant is *killed* when the suite fails. The unmodified suite runs first and must pass.

The two snapshot tests in tests/test_pipeline.py (names start with test_snapshot_) compare a fresh run with
the committed results and README, so they fail on almost any change. To show that the suite catches the
bugs through the hand-calculated checks and the invariants, each mutant is also scored with those two
tests switched off ("killed without the snapshot").

    python mutation/run_mutants.py [--workers 4]

Writes results/mutation_report.json. Run scripts/run_all.py afterwards to put the result in README.md.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COPY = ["sgsewer", "tests", "config", "data/inputs", "results", "docs", "README.md", "pytest.ini"]

# (id, file, original snippet, mutated snippet, what the bug means)
MUTANTS = [
    ("M01", "sgsewer/hydraulics.py", "return d * d / 8.0 * (t - math.sin(t))", "return d * d / 8.0 * (t + math.sin(t))",
     "flow area: plus instead of minus sin(theta)"),
    ("M02", "sgsewer/hydraulics.py", "return d * theta(r) / 2.0", "return d * theta(r)",
     "wetted perimeter doubled"),
    ("M03", "sgsewer/hydraulics.py", "** (2.0 / 3.0) * math.sqrt(slope) / n", "** (1.0 / 2.0) * math.sqrt(slope) / n",
     "Manning: R^(1/2) instead of R^(2/3)"),
    ("M04", "sgsewer/hydraulics.py", 'if d <= hp["large_pipe_above_m"]["value"]:',
     'if d < hp["large_pipe_above_m"]["value"]:', "a 1.0 m pipe gets the two-thirds-bore limit"),
    ("M05", "sgsewer/hydraulics.py", "if v_lim > v_ceiling:", "if v_lim > v_max:",
     "diameter chosen against 2.4 m/s instead of the design ceiling"),
    ("M06", "sgsewer/hydraulics.py", "if v_lim >= v_min:", "if v_lim >= 0.0:",
     "self-cleansing velocity never enforced"),
    ("M07", "sgsewer/hydraulics.py", "return (q * n / (a * hydraulic_radius(d, r) ** (2.0 / 3.0))) ** 2",
     "return (q * n / (a * hydraulic_radius(d, r) ** (2.0 / 3.0)))", "slope for a given depth: square forgotten"),
    ("M08", "sgsewer/flows.py", 'return (pub * fc["lpcd_public"]["value"] + prv * fc["lpcd_private"]["value"]) / (pub + prv)',
     'return (pub * fc["lpcd_private"]["value"] + prv * fc["lpcd_public"]["value"]) / (pub + prv)',
     "public and private per-capita flows swapped"),
    ("M09", "sgsewer/flows.py", "return water_m3_per_m2_year * 1000.0 / 365.0 * return_factor",
     "return water_m3_per_m2_year * 1000.0 / 365.0", "return factor dropped from non-residential flow"),
    ("M10", "sgsewer/flows.py", 'nonres_gfa = p["area_m2"] * pr * (1.0 - share)', 'nonres_gfa = p["area_m2"] * pr * share',
     "commercial share of mixed parcels taken as the residential share"),
    ("M11", "sgsewer/flows.py", 'r["peak_ls"] = fc["peak_factor"]["value"] * r["adwf_m3d"] * 1000.0 / DAY_S',
     'r["peak_ls"] = r["adwf_m3d"] * 1000.0 / DAY_S', "peak factor dropped from parcel peak flow"),
    ("M12", "sgsewer/network.py", 'dn["adwf_by_subzone"][s] = dn["adwf_by_subzone"].get(s, 0.0) + v',
     'dn["adwf_by_subzone"][s] = v', "upstream flow overwrites instead of adding"),
    ("M13", "sgsewer/network.py", 'soffit_up = max([cover] + [u["soffit_down_m"] for u in ups])',
     'soffit_up = min([cover] + [u["soffit_down_m"] for u in ups])', "outgoing sewer set above the incoming ones"),
    ("M14", "sgsewer/network.py", '"manholes": max(1, math.ceil(r["length_m"] / spacing - 1e-9)),',
     '"manholes": max(1, math.floor(r["length_m"] / spacing)),', "manhole count rounded down: spacing over 120 m"),
    ("M15", "sgsewer/network.py", 'd_min = max([u["d_mm"] for u in ups], default=0)', "d_min = 0",
     "diameter allowed to shrink downstream"),
    ("M16", "sgsewer/cost.py", 'return e["tpi_now"] / e["tpi_base"]', 'return e["tpi_base"] / e["tpi_now"]',
     "price escalation inverted"),
    ("M17", "sgsewer/cost.py", 'shoring = 2.0 * h * rt["shoring_per_m2_face"] * deep',
     'shoring = h * rt["shoring_per_m2_face"] * deep', "trench support on one face only"),
    ("M18", "sgsewer/cost.py", 'contingency = contract * oc["contingency"][level]',
     'contingency = direct * oc["contingency"][level]', "contingency taken on direct works, not on the contract"),
    ("M19", "sgsewer/cost.py",
     'return "pipe jacking" if mean_invert_depth > cc["geometry"]["max_open_cut_invert_depth_m"]["value"] else "open cut"',
     'return "pipe jacking" if mean_invert_depth >= cc["geometry"]["max_open_cut_invert_depth_m"]["value"] else "open cut"',
     "a reach exactly at the open-cut limit costed as jacking"),
    ("M20", "sgsewer/cost.py", "v_backfill = v_exc - pipe_vol - v_bed", "v_backfill = v_exc",
     "backfill volume ignores the pipe and bedding"),
    ("M21", "sgsewer/programme.py", "return 3.0 * t * t - 2.0 * t ** 3", "return t",
     "S-curve replaced by a straight line"),
    ("M22", "sgsewer/programme.py", 'add(s["dlp_end"], works * ret / 2.0)', 'add(s["construction_end"], works * ret / 2.0)',
     "all retention released at completion"),
    ("M23", "sgsewer/programme.py", "return first_fy + m // 12", "return first_fy + (m + 3) // 12",
     "financial year boundary moved to January"),
    ("M24", "sgsewer/programme.py", "begin = max(latest_start, approved)", "begin = latest_start",
     "packages allowed to start before funding approval"),
    ("M25", "sgsewer/programme.py", "if scheme_budget >= 100e6:", "if scheme_budget >= 200e6:",
     "S$100 million approval threshold moved to S$200 million"),
    ("M26", "sgsewer/programme.py", "return (1.0 + rate) ** (months / 12.0)", "return 1.0 + rate * months / 12.0",
     "outturn escalation simple instead of compound"),
    ("M27", "sgsewer/programme.py", "add(m, certified * (1.0 - ret))", "add(m, certified)",
     "retention not deducted from monthly payments"),
    ("M28", "sgsewer/programme.py", "return min(max((fy - need_fy + 1) / years, 0.0), 1.0)",
     "return min(max((fy - need_fy) / years, 0.0), 1.0)", "build-out starts a year late"),
    ("M29", "sgsewer/capacity.py", "spare = cap * (1.0 - used)", "spare = cap",
     "existing use of the receiving sewer ignored"),
    ("M30", "sgsewer/pipeline.py", '"central": statistics.mean(ac) + m,', '"central": max(ac) + m,',
     "on-cost ratio: largest accredited-checker ratio instead of the mean"),
]


# Mutants that cannot change behaviour on any reachable input, with the reason. Shown as survivors, not hidden.
EQUIVALENT = {
    "M15": "equivalent on a gravity tree: flow only accumulates downstream and size_reach never picks a smaller "
           "pipe for more flow (tests/test_hydraulics.py::test_size_reach_never_picks_a_smaller_pipe_for_more_flow), "
           "so the carry-down guard never binds",
}


def run_pytest(cwd: Path, extra: list[str]) -> tuple[bool, str]:
    p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *extra],
                       cwd=cwd, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.strip().splitlines() if ln.strip()][-1:] or [p.stderr.strip()[-200:]]
    return p.returncode == 0, tail[0]


def make_copy(dst: Path) -> None:
    for rel in COPY:
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / rel)


def one(m: tuple) -> dict:
    mid, rel, old, new, what = m
    with tempfile.TemporaryDirectory(prefix=f"mut_{mid}_") as tmp:
        work = Path(tmp)
        make_copy(work)
        f = work / rel
        text = f.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"{mid}: snippet found {text.count(old)} times in {rel}, expected exactly once")
        f.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        ok_all, tail_all = run_pytest(work, [])
        ok_ns, tail_ns = run_pytest(work, ["-k", "not test_snapshot_"])
    return {"id": mid, "file": rel, "what": what, "original": old, "mutated": new,
            "killed": not ok_all, "killed_without_snapshot": not ok_ns,
            "pytest_full": tail_all, "pytest_without_snapshot": tail_ns}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="mut_base_") as tmp:
        make_copy(Path(tmp))
        ok, tail = run_pytest(Path(tmp), [])
        if not ok:
            raise SystemExit(f"the unmodified suite fails in a clean copy: {tail}")
        ok_ns, tail_ns = run_pytest(Path(tmp), ["-k", "not test_snapshot_"])
        if not ok_ns:
            raise SystemExit(f"the unmodified suite without snapshots fails: {tail_ns}")
        c = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                           cwd=tmp, capture_output=True, text=True).stdout
        mo = re.search(r"(\d+) tests? collected", c)
        # with -q twice pytest prints "file: count" lines instead of the summary
        collected = int(mo.group(1)) if mo else sum(int(n) for n in re.findall(r"^\S+\.py: (\d+)$", c, re.M))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(one, MUTANTS))
    report = {
        "date": datetime.date.today().isoformat(),
        "baseline": tail, "baseline_without_snapshot": tail_ns, "tests_collected": collected,
        "total": len(results), "killed": sum(r["killed"] for r in results),
        "killed_without_snapshot": sum(r["killed_without_snapshot"] for r in results),
        "survivors": [r["id"] for r in results if not r["killed"]],
        "survivors_without_snapshot": [r["id"] for r in results if not r["killed_without_snapshot"]],
        "equivalent": {k: v for k, v in EQUIVALENT.items() if k in {r["id"] for r in results if not r["killed"]}},
        "survivors_not_explained": [r["id"] for r in results if not r["killed"] and r["id"] not in EQUIVALENT],
        "mutants": results,
    }
    (REPO / "results" / "mutation_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for r in results:
        print(r["id"], "killed" if r["killed"] else "SURVIVED",
              "| without snapshot:", "killed" if r["killed_without_snapshot"] else "SURVIVED", "|", r["what"])
    print(f"{report['killed']}/{report['total']} killed; "
          f"{report['killed_without_snapshot']}/{report['total']} without the snapshot tests")


if __name__ == "__main__":
    main()
