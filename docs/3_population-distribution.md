# Population distribution

## Overview

This notebook (`notebooks/demand/3_population_distribution.ipynb`) maps Singapore's
population and workplaces onto building point geometries. It takes published
**statistical totals** (by subzone, planning area, and planning region) and distributes
them down to **per-building demand points** — residents per residential building and
workers per workplace building. The flow is bottom-up: a target total is set, then
broken down from coarse statistical zones → finer zones → individual buildings →
aggregated delivery points.

## 1. Setting the targets

The totals everything else must sum to are computed as explicit knobs first:

- **Residents / workforce based on residents** (`WORKFORCE_COUNT_BASE_RESIDENT`) =
  `2,379,300 − 81,200` = **2,298,100**. Starts from total employed residents by
  planning area (includes "other"), then drops the ~81k work-from-home.
- **Non-resident workforce** (`WORKFORCE_COUNT_NON_RESIDENT`) =
  `1,910,000 × (0.41 + 0.23 × 0.2) − 150,000` ≈ **750k**. That is 41% EP/SP + 20% of
  the 23% WP (CMP), minus ~150k daily land-border commuters (Malaysian crossing estimate).
- `RESIDENCE_TOTAL` and `WORKPLACE_TOTAL` are set from these two sums.

These are later **extrapolated** to include the non-residents kept in the model, so the
final aggregated result lands around ~3.0M residents and ~3.0M workers.

## 2. Basic data sources

- **Boundaries** (GeoDataFrames): `pln_region_gdf`, `pln_area_gdf`, `subzone_gdf` — the
  administrative hierarchy used to attribute buildings.
- **Classified buildings** (`CLASSIFIED_BUILDINGS` parquet): point geometries tagged with a
  `demand_type` (res_low / res_med / res_high / office / commercial / ind_low / ind_med /
  ind_high), floorspace, etc. Buildings are the unit that demand is allocated to. Hotels are
  removed.
- **Special demand** point layers: healthcare (`HEALTHCARE_WORKFORCE`), military
  (`MILITARY_WORKFORCE`), government (`GOVERNMENT_WORKFORCE`).
- **SGStat CSVs**:
  - `C020126-clean.csv` — resident population by **subzone** of residence.
  - `C020138-clean.csv` — employed residents by **planning area** of residence.
  - `2025GHS_WorkplacePlanningArea_ResidencePlanningRegion_ModeOfTransport-clean.csv` —
    employed workers by **planning area** of workplace, broken out by **planning region** of
    residence (the OD matrix).

## 3. Synthesis at statistical levels

Each CSV is cleaned (drop `Total` / `Others` rows, map names → IDs, replace `-` with 0):

- **Residence by subzone** (`data_res_subzone`): population per subzone.
- **Employed residence by planning area** (`data_employed_res_pln_area`): ~2.355M across
  ~29 of 55 planning areas. ~24k in an `Others` row are set aside for later distribution.
- **Workplace by planning area × residence region** (`data_employed_work_area_res_region`):
  the origin–destination matrix. Irregular rows are extracted:
  - "No Fixed Location for Work" (~200k) → redistributed by residence-region ratio.
  - "Other Planning Areas or Outside Singapore" (~23k) → kept separate (`df_work_other_pln_area`).
  - "Works from Home" (~81k) → removed.

These are then **extrapolated** to the model totals (add non-residents, subtract excluded
groups), giving per-planning-area worker counts that sum to `WORKPLACE_TOTAL`.

**Employed residence pushed to subzone level** (`extrapolate_employed_res_subzone`): each
planning area's employed-residence total is split among its subzones **proportionally to
resident population**. Subzones whose planning area has no data receive the set-aside
`Others` amount instead.

## 4. Building-level distribution

The core mechanism is **floorspace-weighted allocation within each statistical zone**, using
demand-type multipliers (`demandtype_coeffs`: res_med = 1, res_high = 1.1, office = 1.1,
commercial = 1, ind_low = 0.25, ind_med = 0.5, ind_high = 0.55).

### Residences (`calc_res`)

- **`res_low` (landed)**: pre-assigned household counts using a 600 m²/household rule — one
  household below 600 m², linear extrapolation above. The Ridout subzone (`TNSZ03`) is
  excluded here because GCBs sap the residential allocation for the few medium-density
  buildings; it is calculated with res_med/res_high instead.
- **`res_med` / `res_high`**: the subzone's remaining employed-residence total is split among
  residential buildings **proportionally to floorspace × coefficient**.

### Workplaces — three buckets

- **Main planning areas** (`calc_work`, excluding Western Catchment): each planning area's
  worker total split among non-residential buildings by floorspace × coefficient.
- **"Other" planning areas** (`calc_work_other_pln_area`): the ~13k set aside, split among the
  ~5 planning areas lacking workplace data by floorspace × coefficient.
- **Western Catchment** (`compute_western_catchment`): mostly military, so its non-military
  demand is estimated using a region-wide "workers per floorspace" ratio computed by demand
  type from the already-computed main workplaces.

## 5. Special demand integration

Healthcare, military, and government workers are loaded, joined to subzones, and added as
their own demand points (`sd_work_gdf`). Their totals are **subtracted** from the planning-area
building distribution so they are not double-counted — both in `df_employed_work_area_res_region`
for planning areas with exact data and in `df_work_other_pln_area` for the "other" areas.

## 6. Point aggregation

1. Combine residential and workplace building points; zero-fill residents/workers.
2. Compute a spatial `weight` per point — the sum of normalized square-root resident and
   worker counts.
3. **Weighted inhibition sampling** — seed-selection via a spatial-hash implementation, biased
   by weight, with a 200 m minimum spacing (~4,499 seeds).
4. Assign every building to its nearest seed (KDTree); aggregate residents/workers into each
   cluster and place the cluster point at its weight-centered centroid.
5. **Merge undersized points** (<50 residents OR workers) into their nearest larger point.

## 7. Export

Three artifacts are exported (guarded by `ALLOW_EXPORT`) for the downstream notebook:

- `AGGREGATED_DEMAND_POINTS` (`demand_gdf`) — the final demand points.
- `WORKPLACE_RESIDENCE_OD` (`df_ewarr_all`) — the planning-area OD matrix, with nearest-region
  ratio imputation (mean of adjacent planning areas) for the "other" areas.
- `RESIDENTIAL_POPULATION_ORIGINS` / `RESIDENTIAL_POPULATION_COVERAGE` — an all-resident origin
  layer used by the airport sub-model; subzones lacking usable building origins are recorded as
  unallocated.

Execution stops with `assert False, "Do not continue, use notebook 4"` — the actual
OD / distance-decay allocation happens in `4_population_distance_decay.ipynb`. A deprecated OD
section at the bottom is retained for comparison (random residence↔job allocation via MILP
integer allocation in `src/utils/point_dist.py`).

## Known approximations

Several handling choices are rough estimates rather than derived from authoritative datasets,
and the author notes the output can read as an overestimate in spots:

- The 600 m² landed-household rule and the `demandtype_coeffs`.
- Seletar/Sengkang workplace densities are high because there is little 1st-floor retail (RES1C)
  zoning in the Northeast; partly compensated by classing `commercial` subtype buildings in
  residential areas.
- Bukit Batok industrial parks tagged `commercial` (OSM) become unrealistically large demand
  points; partly dampened with a 67% floorspace modifier on B1/B2 commercial buildings.
