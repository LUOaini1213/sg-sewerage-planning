# sg-sewerage-planning

**Screening-level planning study of a used-water (sewerage) network for one Singapore planning area, Tengah: flow projection from Master Plan land use, a gravity sewer network sized to PUB's Code of Practice, a cost-norm table, and a programme rolled into a 5-year block budget.**

> **Read this first.** This is a personal desk study, not a PUB plan. The land use and the roads are real public data. The sewer layout, the outlet, the ground level, most unit rates, every programme duration and every need date are SYNTHETIC or ASSUMED, and are labelled so wherever they appear. Parts of Tengah are already built and sewered; this study ignores the real network (it is not public) and plans the town from a clean sheet to exercise the method. Nothing here is a design, a cost estimate fit for funding, or professional engineering advice. PUB's Code of Practice is referenced, not redistributed ([DATA_SOURCES.md](DATA_SOURCES.md)).

<!-- README.md is generated from docs/README.template.md by scripts/run_all.py. Do not edit README.md by hand. -->

## What it does

1. **Flows by land use.** {{parcels_with_flow}} flow-generating parcels of the URA Master Plan 2019 in the Tengah planning area. Housing uses the per-capita flows, persons per dwelling and peak factor of PUB's Code of Practice on Sewerage and Sanitary Works (COPSSW, 3rd Edition, March 2025); non-residential land uses proxy rates that are labelled as assumptions.
2. **Network sizing.** A SYNTHETIC tree of gravity sewers along real roads (OpenStreetMap) to one assumed outlet: {{reaches}} reaches, {{length_km}} km. Manning's equation for part-full pipes, with the COPSSW depth-of-flow limits, velocity limits, minimum size, minimum depth and manhole spacing.
3. **Cost norms.** A S$ per metre table by diameter and depth with low, central and high values, built up from the few unit rates that are public and from stated assumptions for the rest.
4. **Programme and budget.** Packages, lead times including funding approval, monthly cashflow, financial-year phasing, a 5-year block budget ({{fy_first}} to {{fy_last}}), and how the block moves when development comes earlier or later.
5. **Receiving-sewer check.** A what-if table: how large and how empty the existing downstream sewer would have to be for the town not to trigger an expansion.
6. **A two-page funding-paper-style brief:** [docs/funding_brief.md](docs/funding_brief.md) ([PDF](docs/funding_brief.pdf)).

## Headline numbers

All values below are generated from files in [`results/`](results/) by `scripts/run_all.py`. Prices are {{price_base}}.

| | | Source file |
|---|---|---|
| Design population and flow | {{homes}} homes x {{ppd}} persons = {{population}} people; average dry-weather flow {{adwf_mld}} ML/d ({{nonres_share}} non-residential); design peak {{peak_ls}} L/s | `results/summary.json`, `flows_by_parcel.csv` |
| Network (synthetic) | {{length_km}} km in {{reaches}} reaches, {{d_min}} to {{d_max}} mm, {{manholes}} manholes; {{trunk_km}} km is 600 mm or larger | `results/network_design.csv` |
| COPSSW checks | depth of flow within the limit in every reach: {{depth_all_ok}}. Peak velocity {{v_min_cop}} to {{v_max_cop}} m/s met in {{reaches}} less {{gov_flag}} reaches; {{gov_flag}} head reaches ({{flag_km}} km) carry too little flow to be self-cleansing at 1 in {{max_slope_one_in}} and are flagged | `results/network_design.csv` |
| Depth | mean invert depth {{mean_depth}} m, deepest {{max_depth}} m (flat ground assumed); {{jacking_km}} km ({{jacking_share_len}} of length) is deeper than {{open_cut_limit}} m and costed as pipe jacking | `results/summary.json` |
| Programme budget | S$ {{budget_c}} million central, S$ {{budget_l}} to {{budget_h}} million low to high ({{range_low}} / {{range_high}}); S$ {{per_m_c}} per metre on average | `results/packages.csv`, `summary.json` |
| Lead time | {{lead_min_months}} months ({{lead_min_years}} years) from programme start to the first usable sewer on the assumed durations | `results/schedule.csv` |
| 5-year block {{fy_first}} to {{fy_last}} | S$ {{block_c}} million at constant prices ({{block_share}} of the programme), S$ {{block_o}} million outturn; peak year {{peak_fy}} at S$ {{peak_fy_c}} million | `results/cashflow_fy.csv` |
| Development one year earlier | block rises to S$ {{block_m1}} million and {{late_m1}} package(s) cannot be ready in time (worst {{late_m1_months}} months late) | `results/timing_sensitivity.csv` |
| Development one year later | block falls to S$ {{block_p1}} million | `results/timing_sensitivity.csv` |
| Receiving sewer | an empty {{recv_empty_d}} mm sewer is the smallest that takes the ultimate peak; if half its capacity is already used: {{recv_half_d}} mm | `results/capacity_trigger.csv` |

Three things the numbers say:

- **The block budget is driven by timing, not by the estimate.** Moving every need date by one year changes the 5-year block from S$ {{block_c}} million to S$ {{block_m1}} million or S$ {{block_p1}} million. The whole low-to-high cost range moves it less than that in proportion.
- **Depth, not diameter, is the cost.** On flat ground a gravity network {{main_trunk_km}} km long along its main trunk ends {{max_depth}} m down. Pipe jacking is {{jacking_share_len}} of the length and {{jacking_share_cost}} of the direct cost.
- **The "approximately {{v_target_cop}} m/s" of COPSSW clause 3.2.1(e)(i) is out of reach on flat ground.** With no reach steeper than 1 in {{max_slope_one_in}}, choosing diameters for up to 1.0, 1.2 or {{v_target_cop}} m/s moves the budget by only S$ {{tradeoff_spread}} million, and even the {{v_target_cop}} m/s choice averages {{tradeoff_15_vmean}} m/s ([trade-off table](#velocity-against-depth)). Depth comes from the length of the layout, not from the velocity target.

![Plan](results/figures/plan.png)

## How to run

Python 3.11.

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_all.py       # flows, network, costs, programme, figures, README, brief
pytest                          # tests (offline)
python mutation/run_mutants.py  # optional: mutation test of the test suite
```

`scripts/run_all.py` rewrites everything under `results/` and regenerates this README and the brief from the templates in `docs/`. The committed inputs in `data/inputs/` were made from the raw public downloads by `scripts/fetch_data.py` and `scripts/prepare_inputs.py` (`pip install -r requirements-tools.txt`); the pipeline and the tests never go online.

## 1. Flows

**Method.** HDB's published figure for the town ({{homes}} homes) is spread over the Master Plan parcels in proportion to their residential gross floor area (site area x gross plot ratio; {{cr_share}} of the floor area of "Commercial & Residential" parcels is taken as housing: assumption). The parcels give {{res_gfa_ha}} ha of residential floor area, so the allocation implies {{gfa_per_home}} m2 of gross floor area per home, which is the plausibility check on combining the two sources.

| Parameter | Value | Basis |
|---|---|---|
| Persons per dwelling | {{ppd}} | COPSSW cl. 3.2.1(a) |
| Average domestic daily flow | {{lpcd_public}} L per capita per day public housing, {{lpcd_private}} private | COPSSW cl. 3.2.1(a), Table 4 |
| Housing mix | {{homes_public}} public, {{homes_private}} private, so {{lpcd_blend}} L per capita per day town-wide | press reports of HDB's 2016 announcement (secondary source) |
| Peak factor | {{peak_factor}} | COPSSW Table 4; applied to non-residential flow too (assumption) |
| Non-residential | water-use benchmark x floor area x {{return_factor}} return factor | COPSSW cl. 3.2.1(b) gives no rates: PUB's published retail (1.1 m3/m2/year) and office (1.0 m3/m2/year) medians are used as proxies, and plot ratios are assumed where the Master Plan shows "EVA" or "SDP". All of this is assumption; see `config/study.json` |
| Infiltration | none | not in the COPSSW design basis; a real study would take PUB's view |

{{flow_table}}

{{class_table}}

The industrial estate (Business 2, plot ratio "subject to detailed planning") is the least certain flow: {{b2_m3d}} m3/d here, with a factor-of-three sensitivity below. SingStat's average resident household size in 2025 was {{hh_observed}} persons, below the {{ppd}} of the COPSSW; that case is in the sensitivity table too.

## 2. Network sizing

**What is real and what is not.** Roads: OpenStreetMap, {{osm_date}}, primary to residential classes including roads mapped as under construction, {{road_km}} km in the largest connected piece ({{road_dropped_m}} m in {{road_components}} pieces minus one were dropped). Layout: SYNTHETIC. Each parcel is attached to its nearest road node (median distance {{snap_median}} m, largest {{snap_max}} m; {{snap_over_200}} parcels are more than 200 m from any mapped road), and the sewers are the shortest road paths from those nodes to one outlet. The outlet is the westmost road node: an assumption, chosen only because a DTSS Phase 2 link-sewer contract is named after Old Choa Chu Kang Road / Jalan Bahar, west of the town. Ground: one flat level. Sewers inside development parcels are not included. {{parcels_at_outlet}} parcels attach directly to the outlet node: their {{outlet_own_m3d}} m3/d ({{outlet_own_share}} of the town's flow) is counted in the outlet and receiving-sewer flows, but no sewer is laid or costed for them.

**Rules applied (COPSSW 3rd Edition).**

| Rule | Value | Clause |
|---|---|---|
| Depth of flow at design peak | not more than half bore up to 1.0 m diameter, two-thirds bore above | 3.2.1(c) |
| Minimum sewer size | 200 mm | 3.2.1(d)(i) |
| Minimum depth | {{min_cover}} m below ground, read here as depth to the soffit (assumption) | 3.2.1(d)(ii) |
| Velocity at design peak | not less than {{v_min_cop}} m/s, not more than {{v_max_cop}} m/s | 3.2.1(e)(ii) |
| Target velocity | "approximately {{v_target_cop}} m/s at design peak flow": not met, see below | 3.2.1(e)(i) |
| Manhole spacing | not more than {{mh_spacing}} m | 3.2.2(c) |
| Levels at manholes | outgoing soffit at the lowest incoming soffit | 3.2.2(e) |
| Roughness | Manning n = {{manning_n}} (assumption: the COPSSW gives none) | - |

**Sizing rule.** For a given diameter, the flattest slope that respects the depth limit puts the peak flow exactly at the limit depth, and the velocity there is Q / A whatever the slope. So each reach takes the smallest diameter whose velocity at the limit depth is not above {{v_ceiling}} m/s (a design choice of this study), laid at the slope that gives the limit depth; if that velocity would be under {{v_min_cop}} m/s the pipe is steepened until the peak flow moves at {{v_min_cop}} m/s; and if that needs more than 1 in {{max_slope_one_in}} (assumption) the reach is laid at 1 in {{max_slope_one_in}} and flagged. No reach is laid steeper than 1 in {{max_slope_one_in}}: a pipe that would need more at the depth limit goes up a diameter. Diameters never decrease downstream.

**Result.** {{gov_depth}} reaches are governed by the depth limit, {{gov_vel}} by self-cleansing velocity, and {{gov_flag}} are flagged as not self-cleansing at design peak ({{flag_km}} km of 200 mm head sewers serving single small parcels; peak velocity as low as {{v_low}} m/s). In a real layout those parcels would join a neighbour's sewer or be flushed; here they are reported, not hidden. Slopes run from 1 in {{slope_steep}} to 1 in {{slope_flat}}. No reach reaches the {{v_target_cop}} m/s target: the fastest is {{v_high}} m/s.

Main trunk, upstream to outlet (all {{reaches}} reaches are in [`results/network_design.csv`](results/network_design.csv)):

{{trunk_table}}

![Long section](results/figures/long_section_main_trunk.png)

{{diameter_table}}

### Velocity against depth

The same network sized with three ceilings on the velocity used to choose a diameter ([`results/velocity_tradeoff.csv`](results/velocity_tradeoff.csv)):

{{tradeoff_table}}

### Sensitivity of the design

{{sens_table}}

A lower flow does not make the network cheaper here: with fewer persons per dwelling the head reaches need steeper slopes to stay self-cleansing, and more of the network falls below the open-cut limit.

### Which existing-capacity assumptions trigger expansion

Nothing about the receiving sewer is public, so the question is turned round. The town's flow builds up as below (each subzone fills in {{buildout_years}} equal yearly steps from its assumed need date), and the table gives the first financial year in which the town's peak flow exceeds the spare capacity of a receiving sewer of a given size, assumed laid to run at {{recv_v}} m/s at the COPSSW depth limit, for a given share of its capacity already taken by others.

{{flow_fy_table}}

{{trigger_table}}

Reading: the ultimate peak of {{peak_ls}} L/s needs at least an empty {{recv_empty_d}} mm receiving sewer. Any assumption smaller or fuller than the "no trigger" cells means a downstream expansion has to be in the programme by the year shown, which is the first thing a real study would settle with PUB's network model.

## 3. Cost norms

**How the norm is built.** Per metre of open-cut sewer: trench excavation, disposal, trench support, concrete bedding, pipe supply and laying, backfill and road reinstatement, from the quantities of a trench whose width and depth follow the diameter and the invert depth. Manholes are built up from concrete, reinforcement, formwork and lining quantities. Reaches deeper than {{open_cut_limit}} m to invert are costed as pipe jacking with shafts. Then:

    contract = direct works x (1 + preliminaries {{prelim_pct}})
    budget   = contract x (1 + contingency {{contingency_pct}}) + contract x (engineering services {{pes_pct}} + accredited checker and monitoring {{acm_pct}})

**What is cited and what is assumed.**

| Item | Basis |
|---|---|
| Excavation, disposal, mass concrete, reinforced concrete, reinforcement, formwork | Arcadis Construction Cost Handbook Singapore 2022, "Major rates for selected Asian cities", 4Q2021 prices. Building-works rates used as proxies for trench works |
| Escalation to {{price_base}} | BCA Tender Price Index, {{tpi_base}} (2021) to {{tpi_now}} (1Q2026): factor {{escalation}}. A building-works index applied to civil works |
| Accredited checker and monitoring | ratios of GeBIZ awards, table below |
| Pipe supply and laying, trench support, backfill, reinstatement, pipe jacking, shafts, manhole lining and fittings, depth factors, preliminaries, contingency, engineering fee | ASSUMPTION. Placeholders with low and high values, listed one by one in [`config/study.json`](config/study.json). They are not market rates |

Budget norm, S$ per metre, central (low to high), manholes or shafts at {{mh_spacing}} m included ([`results/cost_norms.csv`](results/cost_norms.csv) has every diameter; [`results/cost_norm_buildups.csv`](results/cost_norm_buildups.csv) has the components):

{{norm_table}}

![Cost norms](results/figures/cost_norms.png)

**Uncertainty.** Low, central and high take every rate and allowance at its low, central or high value at once. The band is the envelope of the assumptions, not a confidence interval. For the whole programme it is {{range_low}} / {{range_high}} around the central S$ {{budget_c}} million.

**Checks against public figures.** The only public contract values found with a length attached are both mostly trenchless, and neither is a like-for-like gravity sewer:

{{bench_table}}

The norm's pipe-jacking contract rate (direct works plus preliminaries, 8 m deep) runs from S$ {{jack_low}} to S$ {{jack_high}} per metre across diameters and low to high; S$ {{jack_c750}} per metre central at 750 mm. The two data points sit inside that band, which shows the order of magnitude is not absurd and nothing more. (The euro figure is converted at an assumed {{fx}}.)

GeBIZ lists {{gebiz_n}} PUB construction awards titled "Proposed Sewers ..." from {{gebiz_years}}: S$ {{gebiz_min}} million to S$ {{gebiz_max}} million each, median S$ {{gebiz_median}} million, S$ {{gebiz_total}} million in total. The packages below are of that size. GeBIZ gives no lengths, so these awards cannot be turned into S$ per metre.

{{oncost_table}}

## 4. Programme and 5-year block budget

**Packages.** Each reach belongs to the earliest-needed subzone whose flow it carries, so the shared trunk is built with the first package and is sized for the ultimate flow.

{{package_table}}

**Lead times (all assumed, in `config/study.json`).** Scheme planning and in-principle no-objection from HDB, LTA and URA: {{planning_months}} months. Funding approval: {{f_lt100}} months below S$ 100 million, {{f_100}} from S$ 100 million, {{f_500}} from S$ 500 million; the thresholds are the Ministry of Finance's (Development Planning Committee approval above S$ 100 million, Gateway Process above S$ 500 million), the durations are not published. This scheme is {{funding_route}}, so {{funding_months}} months. Then per package: consultant procurement {{cp_m}}, detailed design {{dd_m}}, construction tender {{ct_m}}, construction at {{oc_rate}} m per month open cut and {{jk_rate}} m per month jacked (at least 12 months), defects liability {{dlp_m}}. Each package starts as late as its need date allows, less a {{buffer_m}}-month buffer, and never before funding approval ({{funding_approved}}).

{{schedule_table}}

The shortest path from programme start ({{programme_start}}) to a usable sewer is {{lead_min_months}} months. The tightest package has {{min_float}} months of float.

**Cashflow rules.** Engineering fee 40% over design, 10% over tender, 50% over construction. Construction value (contract plus contingency) is certified along an S-curve, 3t^2 - 2t^3; {{retention}} is retained, half released at completion and half at the end of the defects liability period. Outturn prices add {{escal}} a year from {{price_base}} (assumption). PUB's own staff time for planning is not costed, which is why the first years are empty.

Financial years run April to March; * marks the 5-year block. S$ million.

{{fy_table}}

**5-year block {{fy_first}} to {{fy_last}}: S$ {{block_c}} million at constant prices, S$ {{block_o}} million outturn.** That is {{block_share}} of the programme; the rest falls in the next block.

![Cashflow](results/figures/cashflow_fy.png)

### Sensitivity to development timing

Every need date moved together:

{{timing_table}}

With the assumed lead times, development two years earlier than the base case leaves {{late_m2}} packages late by up to {{late_m2_months}} months and puts S$ {{block_m2}} million into the block. The decision that matters most for the block budget is therefore when the first subzone is occupied, and the earliest useful action is to start planning and funding approval, which cost little and sit on the critical path.

## What a real study would need

- PUB's sewer network model and records: the actual connection point, the existing sewers already serving the town, and the spare capacity downstream.
- A ground model and the planned platform levels; utility and geotechnical information for the choice between open cut and trenchless.
- HDB's and URA's actual development programme by parcel, and PUB's design flows for the industrial estate.
- PUB's own cost norms from tendered rates, and the real approval calendar.

## Tests

{{tests_collected}} tests, offline. Hydraulics are checked against values worked by hand in the test file (half-bore and two-thirds-bore geometry, Manning velocity and flow, the slope for a given depth, the sizing rule); flows, the cost build-up, the S-curve, retention and the financial-year roll-up likewise. `tests/test_pipeline.py` checks the invariants of the full run (flow is conserved from parcels to outlet, the cashflow adds up to the budget, diameters never shrink downstream, levels match at manholes) and that the committed results, README and brief are what the code produces.

**Mutation check** ([`results/mutation_report.json`](results/mutation_report.json)): {{mutation_summary}}.

{{mutation_table}}

## Licence and data

Code: MIT ([LICENSE](LICENSE)). Data in `data/inputs/` is derived from URA and MOF datasets on data.gov.sg (Singapore Open Data Licence), SingStat, and OpenStreetMap (ODbL, (c) OpenStreetMap contributors). Full references, access dates and what was not redistributed are in [DATA_SOURCES.md](DATA_SOURCES.md).

Author: Wenjie Luo ([LUOaini1213](https://github.com/LUOaini1213)), MSc Civil Engineering (Transport), National University of Singapore. Personal project; no affiliation with PUB.
