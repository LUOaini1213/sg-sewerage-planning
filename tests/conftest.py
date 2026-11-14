import copy
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def raw_cfg():
    return json.loads((REPO / "config" / "study.json").read_text(encoding="utf-8"))


@pytest.fixture()
def cfg(raw_cfg):
    """Config with the run-time on-cost (normally computed from GeBIZ) fixed at 2% for hand checks."""
    c = copy.deepcopy(raw_cfg)
    c["cost"]["oncosts"]["ac_and_monitoring"].update({"low": 0.02, "central": 0.02, "high": 0.02})
    return c


@pytest.fixture(scope="session")
def res():
    from sgsewer import pipeline
    return pipeline.compute()
