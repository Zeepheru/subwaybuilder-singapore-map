# Building classification & floorspace estimation

## Overview

This notebook (`notebooks/demand/2_bldg-classif_floorspace-est.ipynb`) turns raw building
footprints into the demand-grade building layer consumed by downstream notebooks. It runs in
two stages:

1. **Classification** — filter the raw building set, then assign every surviving building a
   `demand_type` (`res_low` / `res_med` / `res_high` / `office` / `commercial` / `ind_low` /
   `ind_med` / `ind_high` / `hotel`) using Singapore Masterplan zoning and Overture building
   tags.
2. **Floorspace estimation** — estimate each building's gross floor area (`floorspace`) so that
   demand is distributed by floor area rather than footprint alone.

The final output is `b_pt_gdf`, a point layer (one centroid per building) carrying
`demand_type`, `floorspace`, and the MP plot binding used by notebook 3.

## 1. Data sources

- **Overture Buildings + Building Parts** (`OVERTURE_BUILDING`, `OVERTURE_BUILDING_PART`,
  `singapore_building*20261021.parquet`): footprints with `subtype`, `class`, `height`,
  `min_height`, `num_floors`, `num_floors_underground`, `min_floor`, `has_parts`. Each is run
  through `process_loaded_building_df`.
- **Masterplan land use** (`MP2025LandUse.geojson`): the zoning polygons carrying `landuse`,
  `gpr` (gross plot ratio), `white_q_max`, `gpr_b_min`, `is_landed`, `is_sdp`. Joined by
  building centroid.
- **OSM land use** (`SG_landuse_20260915.geojson`): used for two light conditions (construction
  detection, low-density bungalow false-positive guard).
- **Government workforce** (`GOVERNMENT_WORKFORCE`): point layer used both to re-add buildings
  and (later) to remove the same buildings.

## 2. Building removal

`preprocess_remove_buildings` tags every building with a `removal_reason` (via `np.select`,
which applies rules in order), then a boolean `is_removed`. Building **parts** inherit their
parent's flag through `map_values_b_to_bp`. Ten removal rules apply:

- `Landuse-OSM` — OSM landuse `construction`, or industrial/port near Keppel Harbour.
- `Buildingtype-Overture` — Overture subtypes `transportation`, `outbuilding`; classes
  `roof`, `pavilion`, `hut`, `shed`, `carport`, `bridge_structure`, `parking`.
- `Size-OSM` / `Size-Google` / `Size-Microsoft` — footprint below a per-source threshold
  (OSM 60 m²; Google/Microsoft 400 m², higher because ML-derived).
- `Landuse-MP` — non-demand Masterplan zonings (`HEALTH & MEDICAL CARE`, `EDUCATIONAL
INSTITUTION`, `PLACE OF WORSHIP`, `PARK`, `ROAD`, `MASS RAPID TRANSIT`, `CEMETERY`,
  `PORT / AIRPORT`, `SPECIAL USE`, etc.). `RESERVE SITE` / `OPEN SPACE` are kept.
- `Landuse-MP_coverage` — buildings in a plot where building footprints cover less than
  `mp_zone_coverage_threshold` (default 0.06, ~0.08 hard cap) of the plot. Guarded so OSM
  `residential` bungalows are never removed.
- `Bbox-removed-areas` — hand-defined bounding boxes (southern islands, Turf City, Marina
  South, Marina Bay MRT) for land with credible non-demand buildings not yet redeveloped.
- `Non-OSM_MP-res` — ML-derived (non-OSM) buildings on residential plots (usually false
  positives from construction/temporary builds).
- `Building_ID` — an explicit list of specific building IDs to drop.

With defaults this removes ~54.7% of the ~236k buildings and ~23.3% of building parts.

## 3. Re-adding buildings

Because the removal pass is aggressive, targeted buildings are brought back and re-tagged
`READDED` so they flow into the ambiguous-plot handling in step C:

- `re_add_specified_buildings` — an explicit list of named landmarks (Changi Jewel, PSA
  Horizons, DSTA Towers A/B, CMPB, ICA buildings, SIA training sites, Changi cargo areas).
  Matched by centroid `contains`.
- `re_add_class_buildings` — buildings of a given `class` (`retail`, `supermarket`) that were
  removed but sit in otherwise-demand-producing zonings (educational, worship, civic, park,
  sports, beach).

## 4. Extra removals (exact-demand buildings)

Buildings matched by an exact special-demand point set are removed (`remove_buildings_set_of_points`).
At this stage only government buildings are removed, since their worker counts are handled
directly in the special-demand path (see `3_population-distribution.md` step 5).

The result is formally filtered to `is_removed == False`.

## 5. Demand-type classification

Classification happens in two passes, writing into an empty-schema `b_dmdtype_gdf` with extra
adjustment columns (`floorcount_adj`, `floorspace_coeff`) and a reverse-estimated `net_floors`.

### A. Merge building parts

`merge_building_parts_into_buildings` (in `src/utils/building_tools.py`) fills `num_floors` for
buildings that have parts but no floor count, accounting for `min_floor`. Buildings with existing
floor counts are left as-is.

### B. Future residential zone verification

Plots already zoned for future residential (`RES`, `RES1C`, `COMRES` with GPR ≥ 2.0) that
currently hold low-intensity or wrong use are reclassified. Per-plot:

- Keep as residential if any building is already residential-tagged, or the tallest is ≥ 5
  floors (an untagged apartment block).
- Otherwise reclassify the plot's buildings to `READDED` when the share of unwanted
  (`industrial` / `warehouse` / `manufacture`) subtypes ≥ 50%, or when area coverage falls
  below a GPR-scaled threshold (10% for GPR ≤ 2.4, 15% for ≤ 3.0, 20% above 3.0).

### C. Ambiguous plots

`handle_ambiguous_mp_plots` handles `RESERVE SITE`, `OPEN SPACE`, `READDED`, and `is_sdp`
buildings. It maps Overture `class` directly to `demand_type` (e.g. `residential`/`apartments`
→ `res_med`/`res_high`, `bungalow`/`terrace`/`detached` → `res_low`, `office`/`government` →
`office`, `commercial`/`retail`/`supermarket` → `commercial`, `industrial`/`manufacture` →
`ind_med`, `warehouse` → `ind_low`). Everything else (including bare OSM `building=yes`) is
dropped. Floor height comes from `FLOOR_HEIGHTS`, with a 2-floor default.

### D. Main zoned buildings

`handle_main_zoned_buildings` is the core pass (`RES` plus all demand zonings). For each building
it assigns `demand_type` and, where a plot blends uses, emits **multiple rows** split by
floorspace share:

- **Residential plots** — non-res Overture classes (commercial/retail/office/industrial) take
  precedence; landed flags → `res_low`; otherwise `res_med` (GPR ≤ 2) or `res_high`.
- **`RES1C`** — 1st-floor `commercial` (floors forced to 1) + `res_high` (floorcount_adj −1).
- **`COMRES`** — `commercial` 0.35 / `res_high` 0.65 split.
- **`COMMERCIAL`** — `office` for office class; `res_high` for residential/tower classes;
  otherwise `commercial`.
- **`HOTEL`** — `hotel` 0.7 / `commercial` 0.3 split.
- **`WHITE`** — by building class (commercial/office/residential/hotel), defaulting to
  `office` 0.6 / `commercial` 0.4.
- **`BUSINESS PARK`** — `office`, except `hotel` where present.
- **`BUSINESS PARK - WHITE` / `B1W` / `B2W`** — `office` vs `commercial`/`ind_med` split by
  `white_q_max` (default 0.3).
- **`B1` / `B2`** — commercial/office buildings get a 0.67 floorspace multiplier; otherwise
  industrial split by GPR (`ind_low` ≤ 1, `ind_med` ≤ 2, `ind_high` above).
- **`RESINST`**, **`COMINST`**, **`AGRI`**, **`UTILITY`** — single deterministic types.

`net_floors` resolution follows a priority order: an explicit override, the building's existing
`net_floors`, height divided by the class floor height (from `FLOOR_HEIGHTS`), else `None`.

## 6. Floorspace estimation

`calc_floorspace` (in the notebook, per-plot `process_groups`) produces `floorspace` — gross floor
area per building — in two principal ways, then bounds by plot GFA.

- **Ambiguous plots** (`READDED` / `RESERVE SITE` / `OPEN SPACE` / `is_sdp`) — only buildings
  with a known floor count are processed: `floorspace = net_floors × area`.
- **Standard plots**, per group:
  - Buildings **with** floor counts: `floorspace = net_floors × area × floorspace_coeff + area ×
floorcount_adj`.
  - Buildings **without** floor counts: the **remaining plot GFA** (plot area × GPR, minus
    already-calculated floorspace) is distributed proportionally by footprint × `floorspace_coeff`.
    If a plot has _no_ buildings with floors, a 0.9 safety coefficient is applied to max GFA.
- **Residential GPR cap** — residential-only buildings without floor counts are capped so their
  floor intensity (floorspace/area) does not exceed a GPR-scaled max (`RES_GPR_FLOORCOUNT_THRESHOLDS`,
  e.g. GPR ≤ 1.4 → 5 floors).
- **Plot GFA bounding** — if a plot's total floorspace exceeds max GFA, it is linearly scaled
  down by footprint area, unless the overage ratio exceeds `max_gpr_ratio_error_correction` (3),
  which is treated as a wrong-plot assignment and left alone.

`fs_calc` (optional, behind `debug_log_fs_calc`) records which path produced each building's
floorspace. The function is intentionally non-vectorized and takes several minutes on the full
set. Geometry is then replaced by centroid (`change_geometry_to_centroid`).

## 7. Output / Export

Guarded by `ALLOW_EXPORT` (disabled by default here). `export_b_pt_gdf` keeps only
`floorspace > 0`, selects
`[demand_type, geometry, area, floorspace, mp_OBJECTID, mp_landuse]`, and writes
`CLASSIFIED_BUILDINGS` (`path_intermediate_buildings/buildings_v2.parquet`) — the input loaded by
notebook 3.

## Known approximations

Several parameters and choices are rough estimates rather than measured values:

- Footprint size thresholds (OSM 60 m², ML datasets 400 m²) and the `mp_zone_coverage_threshold`
  (0.06) are tuned by eye against false positives.
- `FLOOR_HEIGHTS` are per-`class` constants; buildings without floor counts are inferred from
  height ÷ floor height, so a mis-tagged class skews floor count.
- The 0.67 B1/B2 commercial multiplier, the fixed 0.35/0.65 and 0.7/0.3 split ratios, and the
  0.3 default `white_q_max` share are all heuristic.
- The non-vectorized `calc_floorspace` makes the step slow (~3.5 min with floor logging).
- Residential floor counts in `RES1C` are forced to 1 for the commercial layer; `RES` residential
  plots with no floor data are capped by GPR thresholds.
