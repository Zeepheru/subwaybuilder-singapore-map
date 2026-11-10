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

Run `3_population_distribution.ipynb` through **Export inputs for distance-decay
distribution** to write `demand_points.parquet` and `workplace_residence_od.parquet`
under `src/data_intermediate/`. Its original OD section remains available for
comparison and is not needed for the new pipeline.

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
`out/demand_data/demand_data.json` with `jobs`, `residents`, and both endpoints'
`popIds` derived from assigned commuters. Driving distance and time are
straight-line estimates in metres and seconds at a configurable 40 km/h.
