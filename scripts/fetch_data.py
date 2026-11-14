"""Download the raw public data into data/raw/ (git-ignored). Needs requests. No keys are needed.

    python scripts/fetch_data.py
    python scripts/prepare_inputs.py
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = {"User-Agent": "sewer-desk-study/0.1"}
DATA_GOV = {
    "mp19_landuse.geojson": "d_90d86daa5bfaa371668b84fa5f01424f",
    "pa.geojson": "d_4765db0e87b9c86336792efe8a1f7a66",
    "subzone.geojson": "d_8594ae9ff96d0c708bc2af633048edfb",
    "gebiz.csv": "d_acde1106003906a75c3fa052592f2fcb",
}
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = '[out:json][timeout:60];way["highway"](1.3455,103.7055,1.3795,103.7490);out geom tags;'
SINGSTAT = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/17863?limit=300"


def data_gov(dataset: str) -> bytes:
    for _ in range(10):
        r = requests.get(f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset}/poll-download",
                         headers=UA, timeout=60).json()
        url = (r.get("data") or {}).get("url")
        if url:
            return requests.get(url, timeout=600).content
        time.sleep(3)
    raise RuntimeError(f"no download link for {dataset}")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, ds in DATA_GOV.items():
        (RAW / name).write_bytes(data_gov(ds))
        print(name)
    (RAW / "osm_roads.json").write_bytes(requests.post(OVERPASS, data={"data": QUERY}, headers=UA,
                                                       timeout=180).content)
    (RAW / "singstat_17863.json").write_bytes(requests.get(SINGSTAT, headers={"User-Agent": "Mozilla/5.0"},
                                                           timeout=60).content)
    print("done")


if __name__ == "__main__":
    main()
