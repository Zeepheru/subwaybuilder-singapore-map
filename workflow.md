# Notebook workflow

Notebooks live under `notebooks/`; reusable Python modules remain under `src/`.

| Directory | Purpose |
| --- | --- |
| `notebooks/data_preparation/` | Boundary exploration, Overpass download/processing, and manual data corrections (`0_*`). |
| `notebooks/exploration/` | Building exploration (`1_buildings_explore.ipynb`) and demand JSON inspection. |
| `notebooks/special_demand/` | Healthcare, military, government, and other special demand (`SD1`–`SD4`). |
| `notebooks/demand/` | Building classification/floorspace estimation (`2_*`), population aggregation (`3_*`), and distance-decay commuter allocation (`4_*`). |
| `notebooks/map_processing/` | Visual building processing and export (`M1_map_buildings.ipynb`). |
| `notebooks/testing/` | Interactive map visualization checks (`mapper_tester.ipynb`). |

Use `.venv` on Windows or `.venv-linux` on Linux as the notebook kernel.
Open the repository root as the VS Code workspace. The existing workspace
setting in `.vscode/settings.json` starts notebook kernels at that root:

```json
{
  "jupyter.notebookFileRoot": "${workspaceFolder}"
}
```

The notebooks use that working directory directly, with no import setup cells.
If using another notebook editor, configure its kernel working directory to
the repository root before running cells. Restart existing kernels after
changing the working directory setting.

Existing `src.*` imports and paths to `SG-Singapore_DATA/`,
`src/data_intermediate/`, `examples/`, and `out/` resolve from that root.
Data dependencies still apply: special-demand notebooks export workforce data
used by the demand notebooks, and `2_*` produces building data used by `3_*`.

Intermediate exports are grouped by pipeline stage under `src/data_intermediate/`:

| Directory | Contents |
| --- | --- |
| `buildings/` | Classified building points (`buildings_v2.parquet`); `buildings_v1.parquet` is retained for reference. |
| `population/` | Aggregated demand points, workplace/residence OD data, all-resident origins, and population coverage. |
| `special_demand/workforce/` | Healthcare, military, and government workforce points. |
| `special_demand/nonworkforce/` | Airport passenger and higher-education destinations. |

`src/data_filepaths.py` defines the file paths used by both producers and
consumers. Export cells create their destination directories as needed. Existing
Parquet files have been moved into these directories without changing their
contents; the former flat paths are no longer used. Restart existing notebook
kernels to reload the path constants after this reorganization.

Run `3_population_distribution.ipynb` through **Export inputs for distance-decay
distribution** to write `demand_points.parquet`, `workplace_residence_od.parquet`,
`residential_population_origins.parquet`, and `residential_population_coverage.parquet`
under `src/data_intermediate/population/`. The residential origin export uses all-resident
subzone populations independently of workforce capacity and preserves the original
aggregation membership. The coverage report explicitly records population in
subzones without usable residential buildings; those weights are not relocated.
Its original OD section remains available for
comparison and is not needed for the new pipeline.

Run the airport section of `special_demand/SD4_nonworkforce_demand.ipynb` to
export `special_demand/nonworkforce/airport_demand.parquet` under the intermediate
data directory. It uses the existing manual annual passenger
totals divided by 365, with capacity-weighted terminal demand. The provisional
hotel-origin share is **0.6 for Changi (SIN)**, approximated from international
visitor arrival count data, and remains **0.5 for Seletar (XSP)**. Change
`HOTEL_SHARES` there and rerun the export to revise it. No return-trip multiplier
is applied.

Airport destination IDs follow `AIR_<terminal-name>`, with underscores between
words: `AIR_SIN_T1` through `AIR_SIN_T4`, and `AIR_XSP`.

Run SD4's higher-education section to export
`special_demand/nonworkforce/university_demand.parquet`. It reads `EDU_HIGHER_ED`
from `src/data_manual/education_higher.py`, including universities, arts
institutions, polytechnics, and ITE campuses. Campus point IDs follow
`UNI_<campus.name_short>`, with spaces replaced by underscores. Each source
student count is treated as one modeled daily commute per student, with no
annual conversion or return-trip multiplier. Fractional faculty splits are
retained until each campus budget is rounded to 50-person units.

All university demand is allocated from the existing all-resident origin pool.
On-campus housing data is unavailable: no housing points, resident estimates,
hotel allocation, or residential/campus split are added. Campus institution and
notes are retained in the intermediate export for later housing integration.

Then run `4_population_distance_decay.ipynb`. It labels aggregate points by their
planning area/region, reports and excludes points outside either boundary, and
balances residents and jobs in multiples of the small population unit (default
50). The larger total is proportionally reduced to the smaller total. OD quotas
retain the workplace-area/residence-region distribution as closely as those
balanced margins permit. Within those quotas, workplaces are sampled using
remaining job population times exponential distance decay (default scale 10 km).

Dense endpoint pairs use large groups (default 200); smaller points and residual
capacities use small groups. The large size must be a larger integer multiple of
the small size. The random seed is configurable. The notebook writes
`out/demand_data/demand_data_v2.json` with `jobs`, `residents`, and both endpoints'
`popIds` derived from assigned commuters. Driving distance and time are
straight-line estimates in metres and seconds at a configurable 40 km/h.

Special-demand allocation runs after workforce allocation, without changing workforce
groups, capacities, or OD quotas. It uses all-resident weights and a separate
hotel pool loaded from `data_filepaths.HOTELS`
(`SG-Singapore_DATA/special_demand/tourism/Hotels_2025-07.geojson`), as explored in
`notebooks/exploration/SD_hotels_explore.ipynb`. Hotel weights use `TOTALROOMS`,
including comma-formatted counts, and source IDs use `hotel:<OBJECTID>`.
Room counts must be finite, nonnegative integers; missing/invalid counts or
duplicate hotel IDs are errors. A common occupancy/guests-per-room factor
cancels in these relative weights; they are not estimates of absolute guest
numbers. Nearby hotel origins attach
to existing residential points within 200 metres; remaining origins are clustered
using weighted inhibition seeds. Existing point coordinates remain fixed.
Small isolated origin clusters are retained because origin weights are not
commute-group sizes. Airport destinations remain separate terminal points.

Each destination's daily total is rounded to 50-person units. Airport budgets
are split between the two origin pools using largest remainders; universities
use only existing residences. Allocation uses population weighting and
exponential distance decay. In notebook 4, configure each class independently:

```python
SPECIAL_DEMAND_DISTANCE_SCALES = {
    "airport": 10_000,
    "university": 10_000,
}
```

Scales are in metres and must be finite and positive. Every enabled demand class
must have a scale; missing entries are errors. These settings are independent
of the workforce `DISTANCE_SCALE`. Groups use sizes 50 and 200.

Special demand defaults to sampling 200-person groups first, then 50-person
groups only for each destination/origin-pool remainder. This minimizes small
groups while preserving each rounded budget and the airport residential/hotel
split: at most three 50-person groups per destination/pool with the default
sizes. Both group sizes use the same population-times-distance-decay origin
probabilities. Flows become more concentrated at fewer origins; weights are
relative probabilities, not origin capacity limits. Workforce sampling is unchanged.

Configure the policy independently for each class in notebook 4:

```python
SPECIAL_DEMAND_GROUP_ALLOCATION_MODES = {
    "airport": "large_first",
    "university": "large_first",
}
```

`small_first` restores the former approach: sample 50-person units, then combine
them into 200-person groups where enough share the same endpoint pair.
The shared allocator accepts this mapping as `group_allocation_modes`; omitting
it selects `large_first` for all classes. When supplied, every enabled class
needs a valid mode. Notebook 4 prints group counts by class and size.
The final JSON's `residents` and `jobs` represent total modeled demand across
workforce, airport passengers, and higher-education students. Per-class
`airport_allocations.parquet` / `university_allocations.parquet` and
`airport_demand_report.parquet` / `university_demand_report.parquet` are written
alongside the JSON. Reports include the class, requested and rounded demand,
origin pool, configured distance scale, and group allocation mode. Shared origin weights and membership
are written to `special_demand_origin_weights.parquet` and
`special_demand_origin_membership.parquet`. Origins outside planning boundaries
are reported and excluded; an out-of-boundary destination is an error.

Enable or disable each class with `INCLUDE_AIRPORT_DEMAND` and
`INCLUDE_UNIVERSITY_DEMAND` in notebook 4. University-only runs do not load hotel
or airport data. Set both flags to `False` for the original workforce pipeline,
without requiring any special-demand or all-resident exports. Healthcare
visitation, campus housing, and tourism demand remain unimplemented.
