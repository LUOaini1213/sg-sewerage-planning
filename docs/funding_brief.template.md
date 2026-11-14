# Paper for funding approval (format exercise): used-water sewers to serve Tengah

*Personal desk study, not a PUB paper or a PUB plan. The sewer layout is synthetic and most rates and durations are assumed; see the README. Generated from `results/` by `scripts/run_all.py`. Prices: {{price_base}}.*

## 1. Aim

To seek approval in principle for a programme of gravity sewers to serve the Tengah planning area, at an estimated S$ {{budget_c0}} million (range S$ {{budget_l0}} to {{budget_h0}} million), and to note the expenditure of S$ {{block_c}} million falling in the 5-year block {{fy_first}} to {{fy_last}}.

## 2. Background

Tengah is planned for about {{homes}} homes (HDB). At the design basis of PUB's Code of Practice on Sewerage and Sanitary Works ({{ppd}} persons per dwelling, {{lpcd_public}} and {{lpcd_private}} litres per capita per day for public and private housing, peak factor {{peak_factor}}), and with proxy rates for non-residential land, the town generates an average flow of {{adwf_mld}} ML/d and a design peak of {{peak_ls}} L/s. Flows were built up parcel by parcel from the URA Master Plan 2019.

## 3. Proposal

A network of {{length_km}} km of gravity sewers, {{d_min}} to {{d_max}} mm, along the town's roads to one outlet, in {{n_packages}} packages matched to the order in which the subzones are occupied. Every reach meets the Code's depth-of-flow limit; {{gov_flag}} short head reaches do not reach the minimum velocity and need a layout change at design stage. On flat ground the network reaches {{max_depth}} m deep, so {{jacking_km}} km is assumed pipe-jacked.

{{package_table}}

## 4. Cost

| S$ million | Central |
|---|---|
| Direct works | {{direct_c}} |
| Preliminaries ({{prelim_pct}}) | {{prelim_c}} |
| Contingency ({{contingency_pct}}) | {{contingency_c}} |
| Engineering services ({{pes_pct}}) | {{pes_c}} |
| Accredited checker and monitoring ({{acm_pct}}) | {{acm_c}} |
| **Total** | **{{budget_c}}** |

The estimate uses a cost norm by diameter and depth (S$ {{per_m_c}} per metre on average). Only a handful of its unit rates are public; the rest are assumptions with low and high values, which give the range of {{range_low}} / {{range_high}}. Pipe jacking is {{jacking_share_cost}} of the direct cost, so depth is the main cost risk.

## 5. Programme and expenditure phasing

The scheme is {{funding_route}}. Allowing {{planning_months}} months for planning and agency consultation and {{funding_months}} months for funding approval, the first sewer can be ready in {{first_ready}}, {{lead_min_months}} months after programme start; the last in {{last_ready}}.

{{fy_table}}

5-year block {{fy_first}} to {{fy_last}} (*): S$ {{block_c}} million at constant prices, S$ {{block_o}} million outturn at {{escal}} a year. Peak year: {{peak_fy}}, S$ {{peak_fy_c}} million.

## 6. Risks

- **Development timing.** If occupation comes one year earlier, the block needs S$ {{block_m1}} million and {{late_m1}} package(s) cannot be ready in time; one year later, S$ {{block_p1}} million. The block should be reviewed whenever HDB's programme moves.
- **Downstream capacity.** The ultimate peak needs at least an empty {{recv_empty_d}} mm receiving sewer ({{recv_half_d}} mm if half its capacity is in use). A smaller or fuller sewer adds a downstream expansion that is not in this estimate.
- **Depth and ground.** The flat-ground assumption sets the depth; real levels could cut or add to the jacked length.
- **Industrial flows.** The industrial estate's flow is a placeholder.

## 7. Recommendation

Start scheme planning and agency consultation now: they cost little, they are on the critical path, and with the assumed lead times the first package has only {{min_float}} months of float. Seek approval in principle for the programme, and return with a firm estimate once the points below are settled.

## 8. What a real study would need before this paper could go forward

PUB's network model and the actual connection point and downstream capacity; the existing sewers already serving the town; ground and platform levels, utilities and soil information; the development programme by parcel from HDB and URA; design flows for the industrial estate; PUB's own cost norms from tendered rates; and the actual approval calendar.
