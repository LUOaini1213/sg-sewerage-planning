"""Run the study and regenerate everything that is derived: results/, figures, README.md, the brief.

    python scripts/run_all.py [--no-figures]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from sgsewer import pipeline, readme  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    res = pipeline.compute()
    pipeline.write(res)
    if not args.no_figures:
        from sgsewer import plots
        plots.make_all(res, pipeline.INPUTS, pipeline.RESULTS / "figures")
    for rel, text in readme.build().items():
        (REPO / rel).write_text(text, encoding="utf-8", newline="\n")
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        import make_brief_pdf
        pages = make_brief_pdf.make(REPO / "docs" / "funding_brief.md", REPO / "docs" / "funding_brief.pdf")
        print(f"docs/funding_brief.pdf: {pages} pages")
    except ImportError:
        print("pymupdf not installed: docs/funding_brief.pdf not rebuilt (pip install -r requirements-tools.txt)")
    s = res["summary"]
    print(f"peak {s['flows']['peak_ls']:.0f} L/s; {s['network']['length_m'] / 1000:.1f} km; "
          f"budget S$ {s['cost']['budget']['central']['budget'] / 1e6:.1f} m; "
          f"block S$ {s['programme']['block_constant'] / 1e6:.1f} m")


if __name__ == "__main__":
    main()
