# Non-workforce special-demand architecture

## Summary

Keep workforce demand calculation intact. Prepare special destinations and new residential origins separately, merge new origins into the existing point set, then allocate additional commute groups after workforce allocation.

Separate three concepts throughout:

- **Physical points:** coordinates shared by multiple demand categories.
- **Origin weights:** resident, student, or hotel-guest populations used to distribute demand.
- **Demand budgets:** additional commutes to each destination.

Origin weights are reusable across categories. They do not consume workforce capacity or increase workforce OD quotas.

## Airport implementation status

Airport demand is implemented in `src/utils/special_demand.py`, with preparation
in SD4, all-resident origin and membership exports in notebook 3, and additive
allocation in notebook 4. See [the notebook workflow](../workflow.md) for run order.
Healthcare visitation, university, and tourism remain planned additions.

The hotel share is 0.6 for Changi (SIN), approximated from international visitor
arrival count data; Seletar (XSP) retains a provisional share of 0.5. Existing
manual annual passenger inputs divided by 365 produce 63,400 daily passengers
after terminal-level rounding, split using these airport-specific shares. Hotel
origins come from the explicit dataset at `data_filepaths.HOTELS`, explored in
`notebooks/exploration/SD_hotels_explore.ipynb`. Its `TOTALROOMS` counts provide
relative guest weights; a uniform occupancy/guests-per-room multiplier would
cancel in the normalized probabilities. Comma-formatted counts are parsed;
missing, nonfinite, negative, or fractional counts are errors.

Two populated subzones currently lack classified residential buildings:
People’s Park (290 residents) and Kampong Glam (20). Notebook 3 exports their
unallocated population in `residential_population_coverage.parquet`; this weight
is omitted rather than relocated. Represented subzones retain their population
totals. Positive terminal budgets without eligible origin weights remain errors.

Incremental origin aggregation retains small isolated clusters because hotel
room weights and commute group sizes are different measures. The 50-person
minimum applies to emitted commute groups. Existing aggregate membership is
preserved for all-resident origins; hotels attach within 200 metres or form new
clusters. Residential source IDs use namespaced building-export indices; hotel
source IDs use `hotel:<OBJECTID>` and remain stable when dataset rows are reordered.

## Pipeline and notebook changes

### 1. Export residential weights and aggregation membership from notebook 3

Retain the existing workforce calculations and point coordinates. Extend the aggregation code to preserve a source-building-to-final-point mapping through both initial clustering and undersized-point merging.

Create a separate `resident_population` measure using the existing all-resident subzone statistics:

- Within each subzone, reuse the residential building proportions calculated for workforce residences.
- Where residential workforce allocation totals zero, use residential floorspace multiplied by the existing demand-type coefficients.
- Preserve each subzone’s population total. Report populated subzones with no usable residential buildings as unresolved inputs.
- For residential buildings absent from the original aggregation, use the incremental merging procedure below.

Aggregate this measure through the membership mapping. Keep it separate from the existing `residents` column, which represents workforce origin capacity.

Preserve stable source-building IDs in the building export. Keep hotel-classified building rows excluded from workforce allocation; special-demand hotel origins are loaded separately from the explicit hotel dataset.

### 2. Prepare special-demand inputs in the special-demand notebooks

Extend healthcare preparation to export visitation demand before its current workforce export discards inpatient/outpatient information. Keep staff demand in the existing workforce pipeline.

Use separate university, airport, and tourism preparation sections or notebooks as their processing grows. Follow the existing notebook setup conventions.

Each adapter produces destinations, origin pools, and demand budgets in a common format:

| Category | Existing-residential component | New-residential component |
| --- | --- | --- |
| Hospital visitation | Entire visitation budget | None |
| University | Student demand remaining after campus allocation | University-linked campus housing |
| Airport passengers | Configured residential share | Configured hotel share |
| Tourism | Configured residential share | Configured hotel share |

Normalize source statistics to one declared modeled-day demand basis before allocation. Annual attendance, passenger movements, occupied beds, and visits must have explicit conversion assumptions; do not automatically double counts for return travel.

For universities:

- Identify housing buildings explicitly; exclude teaching and administrative buildings.
- Calibrate **occupied student residents per square metre of housing floorspace** from the university with a published residence estimate.
- Apply the coefficient to other campuses’ housing floorspace, allowing documented university-specific overrides.
- Allocate campus residents only to their associated university. Existing-residential demand is the remainder of the university’s modeled student demand.
- Fail validation if estimated campus demand exceeds total student demand, so the estimate or attendance assumptions can be corrected.

For hotels, calculate one shared guest-weight layer from the explicit hotel dataset's room counts. A common occupancy/guests-per-room factor cancels during normalization; no absolute guest population is inferred. Airport and tourism destinations independently specify their hotel-origin shares. These allocations do not consume a shared guest budget.

### 3. Merge additional origins incrementally

Add a reusable aggregation utility that accepts fixed base points and additional residential building points.

- Attach a new origin to the nearest original aggregate containing residential sources when within **200 metres**; resolve distance ties by point ID.
- Preserve existing IDs and coordinates.
- Cluster remaining origins using the current weighted inhibition approach with 200-metre seed spacing and weighted centroids.
- Combine residual clusters below the current 50-person threshold only when their representative points are within 200 metres; retain isolated small clusters.
- Sum origin weights by pool through an explicit membership mapping. Campus ownership and hotel classification remain available even when their physical points merge.
- Give newly created points namespaced IDs.

The 200-metre attachment radius is a new explicit rule inspired by the existing seed spacing; the current aggregation does not itself define a universal 200-metre merge radius.

Create destinations as separate namespaced points, retaining their coordinates and identities even beside workforce destinations. Multiple demand components for the same destination share its destination ID.

### 4. Allocate special commutes after workforce allocation in notebook 4

Run `distribute_population` with the original workforce inputs first. Then allocate special demand against the extended point registry.

For destination `j`, origin pool `c`, and eligible origin `i`:

```text
p(i | j, c) = P[i,c] * exp(-distance[i,j] / scale[c])
              / sum(P[k,c] * exp(-distance[k,j] / scale[c]) for k in eligible[j,c])
```

Here, `P[i,c]` is the pool’s population weight, distances use EPSG:3414, and eligibility restricts campus housing to its university.

- Configure decay scales per component, defaulting to the existing **10 km**.
- Use destination-centric multinomial allocation in 50-person units, with reproducible random streams derived from a global seed and stable component IDs.
- Round each destination’s total to 50-person units, then apportion those units between origin pools using largest remainders. Report rounding differences.
- Emit 200-person groups from sufficiently large assigned origin–destination totals and 50-person groups for the remainder.
- Do not apply workforce OD quotas, decrement origin weights, or balance special demand against workforce totals.
- Reject positive budgets with no eligible positive-weight origins. Do not silently transfer campus or hotel demand to existing residences.

Combine workforce and special groups and call the existing `build_demand_data` exporter once. This preserves its JSON schema and recalculates endpoint totals and `popIds` from every group.

Exported `residents` and `jobs` therefore represent total modeled origin and destination demand. Retain physical population and category breakdowns in intermediate outputs.

## Interfaces and intermediate artifacts

Keep reusable preparation, merging, and allocation logic under `src/utils`; notebooks handle configuration, inspection, and orchestration.

Introduce these logical tables, stored as Parquet/GeoParquet:

| Table | Essential fields |
| --- | --- |
| Point registry | `point_id`, geometry |
| Source membership | `source_id`, `point_id` |
| Origin weights | `point_id`, `pool_id`, `population_weight` |
| Destinations | `destination_id`, category, geometry |
| Demand components | `component_id`, `destination_id`, `pool_id`, modeled demand, decay scale |
| Allocated groups | Existing pop fields plus internal category/component provenance |

Expose utilities for incremental origin merging and special-demand allocation. Leave `distribute_population` and the game JSON contract unchanged. Keep provenance in a companion allocation export; use distinct workforce and special pop-ID namespaces.

Add a preparation notebook between notebooks 3 and 4 to assemble the extended point registry and normalized special-demand inputs. Update the workflow documentation with that dependency.

## Validation and acceptance

- Disabling special demand reproduces the existing workforce output; enabling it leaves workforce groups, IDs, and coordinates unchanged.
- Residential weights conserve all-resident subzone totals and survive every aggregation merge.
- New origins attach within the configured radius; distant origins remain separate; merged campus and hotel weights retain their eligibility.
- University calibration reproduces the published residence estimate and conserves each university’s campus/existing-residential split.
- Hospital, university, airport, and tourism fixtures preserve rounded destination budgets exactly.
- Equal-distance origins allocate proportionally to population; equal-population origins favor shorter distances. Test probabilities directly and sampling behavior over repeated draws.
- Missing housing, empty hotel pools, invalid counts, boundary exclusions, and zero-demand inputs produce explicit diagnostics.
- Final endpoint totals equal incident group sizes, every endpoint exists, IDs are unique, and JSON keys remain compatible.

Source conversion factors, hotel shares, housing selections, and calibration inputs remain explicit preparation inputs. Missing values block the affected component rather than receiving invented estimates.
