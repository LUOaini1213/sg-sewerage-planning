# Data sources

Accessed 14 November 2026 unless a date is given. `data/inputs/manifest.csv` has the SHA-256 of every committed input.

## Redistributed here (derived extracts in `data/inputs/`)

| File | Made from | Publisher, licence |
|---|---|---|
| `parcels.csv`, `map_geometry.json` | Master Plan 2019 Land Use layer (dataset `d_90d86daa5bfaa371668b84fa5f01424f`), clipped to the Tengah planning area of Master Plan 2019 Planning Area Boundary (No Sea) (`d_4765db0e87b9c86336792efe8a1f7a66`); subzones from Master Plan 2019 Subzone Boundary (No Sea) (`d_8594ae9ff96d0c708bc2af633048edfb`). Coordinates converted to SVY21, outlines simplified to 2 m | Urban Redevelopment Authority, data.gov.sg, Singapore Open Data Licence v1.0 |
| `road_graph.json` | OpenStreetMap ways tagged highway = primary, secondary, tertiary, residential, unclassified and their links, including ways tagged as under construction, inside the planning area plus 30 m; Overpass API, data timestamp in the file | (c) OpenStreetMap contributors, Open Database Licence |
| `gebiz_pub_sewer_awards.csv` | Government Procurement via GeBIZ (`d_acde1106003906a75c3fa052592f2fcb`), rows where the agency is the Public Utilities Board and the description contains "sewer" | Ministry of Finance, data.gov.sg, Singapore Open Data Licence v1.0 |
| `singstat_household_size.csv` | SingStat Table Builder, table 17863, "Average Household Size Of Resident And Resident Employed Households By Type Of Dwelling, 2000 - 2025" (resident households) | Singapore Department of Statistics, Singapore Open Data Licence v1.0 |

The Master Plan 2019 layer is the plan as approved on 18 November 2019. Later amendments and the newer Master Plan were not checked.

## Referenced, not redistributed

| Source | Used for | Where |
|---|---|---|
| PUB, Code of Practice on Sewerage and Sanitary Works, 3rd Edition, March 2025 (PDF SHA-256 `a96e7f6d287306aa66197e6d6cf4243c2065b91b10b5a8b684d9b006a2160c82` as downloaded) | cl. 3.2.1(a) Table 4: 230 and 250 litres per capita per day, peak factor 3, 3.5 persons per dwelling; cl. 3.2.1(b) non-residential flows to be proposed to PUB; cl. 3.2.1(c) depth-of-flow limits; cl. 3.2.1(d) minimum size 200 mm, minimum depth 1.5 m; cl. 3.2.1(e) velocities 1.5, 0.9 and 2.4 m/s and the 1 in 50 grade for small developments; cl. 3.2.2(c) manhole spacing 120 m; cl. 3.2.2(e) soffit connection | https://www.pub.gov.sg/-/media/PUB/PDF/Code-of-Practice-on-Sewerage-and-Sanitary-Works-3rd-Edition--Mar-2025.pdf |
| PUB, Sectoral Water Efficiency Benchmark (published December 2025) | retail malls 1.1 m3/m2/year, office buildings 1.0 m3/m2/year (medians), used as proxies for non-residential flow | https://www.pub.gov.sg/Public/WaterLoop/Water-Conservation/Resources-on-Water-Efficiency-Measures/Sectoral-Water-Efficiency-Benchmark |
| HDB, "Smart and Sustainable Tengah", Annex B to a June 2024 news release | "about 42,000 new homes when fully developed", 700 hectares | https://www.hdb.gov.sg/-/media/hdb-pulse/news/2024/four-tengah-bto-projects-awarded-top-tier-active-beautiful-clean-waters-certification/Annex-B.pdf |
| Press reports of HDB's September 2016 announcement | 30,000 public and 12,000 private homes. Secondary source: the split was not found in an HDB document | - |
| Arcadis, Construction Cost Handbook Singapore 2022, "Major rates for selected Asian cities", Singapore column, 4th Quarter 2021 | excavation S$26/m3, removal off site S$20-26/m3, mass concrete grade 15 S$235-248/m3, reinforced concrete grade 30 S$159-165/m3, high tensile reinforcement S$1.95-2.05/kg, sawn formwork S$51/m2 | https://www.arcadis.com/en/insights/perspectives/asia/research-and-publications/construction-cost-handbook |
| BCA, free statistics sheet, Tender Price Index (2010=100), data as at 21 May 2026 | 2020: 102.8, 2021: 117.1, 2025: 139.1, 1Q2026: 140.2 | BCA website, "free_stats.pdf" |
| Ministry of Finance, parliamentary reply "Cost Management for Large-Scale Infrastructure Projects", 6 February 2018 | projects above S$100 million need approval from the Development Planning Committee; above S$500 million they go through the Gateway Process with the Development Projects Advisory Panel | https://www.mof.gov.sg/news-resources/newsroom/cost-management-for-large-scale-infrastructure-projects/ |
| HSL Constructor project page | lengths of the DN800 pumping main of Pulau Punggol Barat Contract 3: 690 m open cut, 770 m pipe bridge, 680 m pipe jacking | https://hsl.com.sg/?p=6566 |
| The Construction Index, 27 August 2015 | LTA sewer contract: EUR 85 million, 9.8 km pipe-jacked, 300 mm to 3.1 m, 112 shafts | https://www.theconstructionindex.co.uk/news/view/strabag-wins-andeuro85m-singapore-sewer-contract |

## Not public, and therefore assumed

PUB's sewer network and its capacities, the connection point, ground levels of the regraded town, PUB's cost norms and tendered rates, approval durations, and the development programme by parcel. Each stand-in is marked ASSUMPTION in `config/study.json`.
