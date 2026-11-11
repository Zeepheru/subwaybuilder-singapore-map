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
| `special_demand/nonworkforce/` | Airport passenger destinations and future non-workforce preparation outputs. |

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
words: `AIR_SIN_Terminal_1` through `AIR_SIN_Terminal_4`, and `AIR_XSP_Terminal`.

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

Airport allocation runs after workforce allocation, without changing workforce
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

Each terminal's daily total is rounded to 50-person units, split between the two
origin pools using largest remainders, and allocated with population weighting
and exponential distance decay (default 10 km). Groups use sizes 50 and 200.
The final JSON's `residents` and `jobs` represent total modeled demand across
workforce and airport passengers. Airport allocations, origin weights,
source-to-point membership, and rounding diagnostics are exported as companion
Parquet files alongside the JSON. Origins outside planning boundaries are
reported and excluded; an out-of-boundary terminal is an error.

Set `INCLUDE_AIRPORT_DEMAND = False` in notebook 4 to run the original workforce
pipeline without requiring the new residential or airport exports. Healthcare
visitation, university, and tourism demand are not implemented yet.
