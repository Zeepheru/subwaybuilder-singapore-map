"""Capacity-constrained, population-weighted commuter allocation."""

import numbers

import geopandas as gpd
import numpy as np
import pandas as pd

from src.utils.point_dist import integer_proportional_allocation


def locate_demand_points(points, planning_areas, planning_regions):
    """Label aggregate points by location, retaining unmatched points as nulls.

    Boundary ties use the first sorted boundary ID so a point is never
    duplicated. Existing point IDs are preserved; other indices get ``p_``.
    The result uses Singapore's metric CRS (EPSG:3414).
    """
    if points.crs is None:
        raise ValueError("Demand points need a CRS")
    result = points.to_crs(3414).copy()
    if not result.index.is_unique:
        raise ValueError("Demand point indices must be unique")
    result.index = pd.Index(
        [i if isinstance(i, str) and not i.isdecimal() else f"p_{i}" for i in result.index],
        name="point_id",
    )
    if not result.index.is_unique:
        raise ValueError("Demand point IDs must be unique after conversion")
    for boundaries, column in (
        (planning_areas, "pln_area_id"),
        (planning_regions, "pln_region_id"),
    ):
        boundary = boundaries[["geometry"]].to_crs(result.crs).copy()
        boundary.index.name = column
        joined = gpd.sjoin(result[["geometry"]], boundary, how="left")
        joined = joined.sort_values(column).loc[
            lambda frame: ~frame.index.duplicated(keep="first")
        ]
        result[column] = joined[column]
    return result


def _apportion(values, total):
    """Scale nonnegative weights to an exact integer total."""
    if total == 0:
        return np.zeros(len(values), dtype=np.int64)
    targets = np.asarray(values, dtype=float) / np.sum(values) * total
    counts = np.floor(targets).astype(np.int64)
    order = np.argsort(-(targets - counts), kind="stable")
    counts[order[:total - int(counts.sum())]] += 1
    return counts


def _weighted_choice(rng, candidates, weights):
    return int(rng.choice(candidates, p=weights / weights.sum()))


def distribute_population(
    points: gpd.GeoDataFrame,
    od_weights: pd.DataFrame,
    small_size: int = 50,
    large_size: int = 200,
    distance_scale: float = 10_000,
    seed: int = 0,
):
    """Assign commuters using remaining population times exponential decay.

    ``points`` has a unique string point-ID index, POINT geometries, a CRS,
    ``residents``, ``workers``, ``pln_area_id``, and ``pln_region_id``.
    ``od_weights`` contains workplace-area rows and residence-region columns.
    Geographic coordinates are converted to EPSG:3414 for metre distances.

    Counts are rounded to multiples of ``small_size``. The larger total is
    proportionally reduced to the smaller with largest-remainder rounding.
    OD quotas minimize deviations from row-normalized weights while exactly
    preserving those balanced area/region totals. Zero weights are soft
    targets, as in the legacy OD allocator, rather than forbidden routes.

    For each region, sample an origin by remaining residents and an area by
    remaining quota, then a workplace by remaining jobs * exp(-distance/scale).
    Emit a large group only when both endpoints originally exceed large_size
    and both remaining capacities and the OD quota can accommodate it.
    Otherwise emit a small group. Same-point commutes are permitted.

    Return metric points with balanced integer populations, commuter groups,
    and the realized OD quotas (in people). Inputs are not modified.
    """
    if any(
        isinstance(value, bool) or not isinstance(value, numbers.Integral) or value <= 0
        for value in (small_size, large_size)
    ) or large_size <= small_size or large_size % small_size:
        raise ValueError("Sizes must be positive integers; large must be a larger multiple of small")
    if not np.isfinite(distance_scale) or distance_scale <= 0:
        raise ValueError("distance_scale must be finite and positive")
    required = {"residents", "workers", "pln_area_id", "pln_region_id"}
    if not required.issubset(points.columns):
        raise ValueError(f"Missing point columns: {sorted(required - set(points.columns))}")
    if points.crs is None:
        raise ValueError("Demand points need a CRS")
    if not points.index.is_unique or not all(isinstance(i, str) for i in points.index):
        raise ValueError("Point IDs must be unique strings")
    if points.geometry.isna().any() or points.geometry.is_empty.any() or not points.geom_type.eq("Point").all():
        raise ValueError("Demand geometries must be nonempty POINTs")
    values = points[["residents", "workers"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Populations must be finite and nonnegative")
    if points[["pln_area_id", "pln_region_id"]].isna().any().any():
        raise ValueError("Demand points must lie in a planning area and region")
    if not od_weights.index.is_unique or not od_weights.columns.is_unique:
        raise ValueError("OD area and region IDs must be unique")

    allocated = points.to_crs(3414).copy()
    xy = np.column_stack([allocated.geometry.x, allocated.geometry.y])
    if not np.isfinite(xy).all():
        raise ValueError("Point coordinates must be finite")
    units = np.rint(values / small_size).astype(np.int64)
    total = int(units.sum(axis=0).min())
    res = _apportion(units[:, 0], total)
    work = _apportion(units[:, 1], total)
    allocated["residents"] = res * small_size
    allocated["workers"] = work * small_size
    pop_columns = ["id", "size", "residenceId", "jobId"]
    if total == 0:
        return allocated, pd.DataFrame(columns=pop_columns), pd.DataFrame(dtype=int)

    areas = allocated["pln_area_id"].to_numpy()
    regions = allocated["pln_region_id"].to_numpy()
    work_totals = pd.Series(work).groupby(areas).sum().loc[lambda x: x > 0]
    res_totals = pd.Series(res).groupby(regions).sum().loc[lambda x: x > 0]
    weights = od_weights.reindex(index=work_totals.index, columns=res_totals.index)
    if weights.isna().any().any():
        raise ValueError("OD weights must cover all populated workplace areas and residence regions")
    weights = weights.astype(float)
    if not np.isfinite(weights.to_numpy()).all() or (weights < 0).any().any() or (weights.sum(axis=1) <= 0).any():
        raise ValueError("OD weights must be finite, nonnegative, and have positive row sums")
    weights = weights.div(weights.sum(axis=1), axis=0)
    quotas = integer_proportional_allocation(weights, work_totals, res_totals)
    remaining_quota = quotas.to_numpy().copy()
    rng = np.random.default_rng(seed)
    ids = allocated.index.to_numpy()
    area_candidates = [np.flatnonzero((areas == area) & (work > 0)) for area in quotas.index]
    large_units = large_size // small_size
    pops = []
    for region_idx in rng.permutation(len(quotas.columns)):
        origins = np.flatnonzero((regions == quotas.columns[region_idx]) & (res > 0))
        while remaining_quota[:, region_idx].sum():
            origin = _weighted_choice(rng, origins, res[origins])
            area_idx = _weighted_choice(
                rng, np.arange(len(quotas)), remaining_quota[:, region_idx]
            )
            candidates = area_candidates[area_idx]
            candidates = candidates[work[candidates] > 0]
            distances = np.linalg.norm(xy[candidates] - xy[origin], axis=1)
            log_weights = np.log(work[candidates]) - (distances - distances.min()) / distance_scale
            destination = _weighted_choice(rng, candidates, np.exp(log_weights - log_weights.max()))
            use_large = (
                values[origin, 0] > large_size
                and values[destination, 1] > large_size
                and min(res[origin], work[destination], remaining_quota[area_idx, region_idx]) >= large_units
            )
            count = large_units if use_large else 1
            pops.append((str(len(pops)), count * small_size, ids[origin], ids[destination]))
            res[origin] -= count
            work[destination] -= count
            remaining_quota[area_idx, region_idx] -= count
    if res.any() or work.any():
        raise RuntimeError("Allocation did not exhaust resident and job capacities")
    return allocated, pd.DataFrame(pops, columns=pop_columns), quotas * small_size


def build_demand_data(points, pops, driving_speed=40 / 3.6):
    """Build the game schema, estimating driving metres/seconds from straight lines.

    Point residents/jobs and popIds are derived from the allocated commuter
    groups, including each self-commute ID only once. Zero-demand points are
    omitted. Driving speed is in metres per second; these are estimates,
    not road-network routes.
    """
    if not np.isfinite(driving_speed) or driving_speed <= 0:
        raise ValueError("driving_speed must be finite and positive")
    if not pops["id"].is_unique or not all(isinstance(i, str) for i in pops["id"]):
        raise ValueError("Pop IDs must be unique strings")
    sizes = pops["size"].to_numpy(dtype=float)
    if not np.isfinite(sizes).all() or (sizes <= 0).any() or (sizes != np.floor(sizes)).any():
        raise ValueError("Pop sizes must be positive integers")
    for column in ("residenceId", "jobId"):
        if not pops[column].isin(points.index).all():
            raise ValueError(f"Unknown point IDs in {column}")
    metric = points.to_crs(3414)
    lonlat = points.to_crs(4326)
    residents = dict.fromkeys(points.index, 0)
    jobs = dict.fromkeys(points.index, 0)
    pop_ids = {point_id: [] for point_id in points.index}
    pop_records = []
    for row in pops.itertuples(index=False):
        distance = metric.geometry.loc[row.residenceId].distance(metric.geometry.loc[row.jobId])
        residents[row.residenceId] += int(row.size)
        jobs[row.jobId] += int(row.size)
        for point_id in dict.fromkeys((row.residenceId, row.jobId)):
            pop_ids[point_id].append(row.id)
        pop_records.append({
            "id": row.id, "size": int(row.size),
            "residenceId": row.residenceId, "jobId": row.jobId,
            "drivingSeconds": int(distance / driving_speed),
            "drivingDistance": int(distance),
        })
    point_records = [
        {"id": point_id, "location": [float(geometry.x), float(geometry.y)],
         "jobs": jobs[point_id], "residents": residents[point_id], "popIds": pop_ids[point_id]}
        for point_id, geometry in lonlat.geometry.items() if pop_ids[point_id]
    ]
    return {"points": point_records, "pops": pop_records}
