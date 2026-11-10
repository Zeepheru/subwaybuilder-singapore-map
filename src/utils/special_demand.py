"""Additive non-workforce demand; weights never consume workforce capacity."""

import hashlib
import numbers

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

from src.utils.population_distribution import _apportion


def _points(frame):
    if frame.crs is None:
        raise ValueError("Points need a CRS")
    if not frame.index.is_unique:
        raise ValueError("Point indices must be unique")
    if frame.geometry.isna().any() or frame.geometry.is_empty.any() or not frame.geom_type.eq("Point").all():
        raise ValueError("Geometries must be nonempty POINTs")
    result = frame.to_crs(3414).copy()
    if not np.isfinite(np.column_stack([result.geometry.x, result.geometry.y])).all():
        raise ValueError("Point coordinates must be finite")
    return result


def _nonnegative(values, label):
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all() or (array < 0).any():
        raise ValueError(f"{label} must be finite and nonnegative")
    return array


def residential_population_origins(residential_buildings, subzone_population, coefficients):
    """Redistribute all-resident subzone totals using workforce building shares.

    For zero-workforce subzones use floorspace * demand-type coefficient.
    Input residential buildings are notebook 3's b_sz_res_gdf. Preserve their
    indices so the notebook can attach the original aggregation membership.
    Return origins and a per-subzone coverage report. Populations without usable
    buildings remain explicitly unallocated rather than moving to other subzones.
    """
    origins = _points(residential_buildings)
    totals = subzone_population["res_pop_residence"]
    _nonnegative(totals, "Subzone populations")
    work = _nonnegative(origins["residents"], "Residential workforce weights")
    fallback = origins["floorspace"] * origins["demand_type"].map(coefficients)
    _nonnegative(fallback, "Residential floorspace weights")
    origins["population_weight"] = work
    zero = origins.groupby("subzone_id")["population_weight"].transform("sum").eq(0)
    origins.loc[zero, "population_weight"] = fallback.loc[zero]
    sums = origins.groupby("subzone_id")["population_weight"].sum()
    if not origins["subzone_id"].isin(totals.index).all():
        raise ValueError("Residential subzones need population totals")
    origins["population_weight"] *= origins["subzone_id"].map(totals) / origins["subzone_id"].map(sums).replace(0, 1)
    origins["pool_id"] = "existing_residential"
    represented = origins.groupby("subzone_id")["population_weight"].sum()
    report = pd.DataFrame({"requested": totals, "represented": represented.reindex(totals.index, fill_value=0)})
    report["unallocated"] = report["requested"] - report["represented"]
    return origins[["geometry", "pool_id", "population_weight"]], report


def airport_destinations(airports, hotel_shares, days_per_year=365):
    """Annual modeled passengers become daily destination demand, without doubling.

    Terminal capacities determine within-airport shares. Coordinates in the
    manual airport definitions are longitude/latitude. Hotel shares are required
    per IATA code; no default is silently supplied here.
    Point IDs follow AIR_<terminal-name>, with airport code included to avoid
    cross-airport collisions and whitespace replaced by underscores.
    """
    if not np.isfinite(days_per_year) or days_per_year <= 0:
        raise ValueError("days_per_year must be finite and positive")
    records = []
    for airport in airports:
        share = hotel_shares.get(airport.iata)
        if share is None or not np.isfinite(share) or not 0 <= share <= 1:
            raise ValueError(f"Provide a hotel share between 0 and 1 for {airport.iata}")
        _nonnegative([airport.annual_passengers], "Annual passengers")
        capacities = _nonnegative([t.annual_capacity for t in airport.terminals], "Terminal capacities")
        if not len(capacities) or capacities.sum() <= 0:
            raise ValueError(f"{airport.iata} needs positive terminal capacity")
        for index, terminal in enumerate(airport.terminals):
            name = f"{airport.iata} {terminal.name or ''}"
            records.append({
                "point_id": "AIR_" + "_".join(name.split()),
                "name": name,
                "geometry": terminal.coord,
                "daily_demand": airport.annual_passengers * capacities[index] / capacities.sum() / days_per_year,
                "hotel_share": float(share),
            })
    return _points(gpd.GeoDataFrame(records, columns=["point_id", "name", "geometry", "daily_demand", "hotel_share"], geometry="geometry", crs=4326).set_index("point_id"))


def hotel_origins(buildings):
    """Hotel floorspace is a relative guest-population proxy, not a guest count.

    A common occupancy/density factor cancels during probability normalization.
    Keep this pool separate even when a hotel shares a residential point.
    """
    hotels = _points(buildings.loc[buildings["demand_type"].eq("hotel")])
    hotels["population_weight"] = _nonnegative(hotels["floorspace"], "Hotel floorspace")
    hotels["pool_id"] = "hotel"
    hotels.index = pd.Index([f"hotel:{i}" for i in hotels.index], name="source_id")
    return hotels[["geometry", "pool_id", "population_weight"]]


def merge_origin_points(base_points, origins, radius=200, seed=0):
    """Attach origins to fixed residential points; cluster remaining origins.

    Optional base_point_id uses exact notebook 3 membership. Otherwise attach
    within radius to original positive-residential points, with ID tie breaks.
    Unattached origins use mass-biased inhibition seeds and weighted centroids.
    Origin weights are not assumed to be trip budgets, so isolated small
    clusters are retained. Return registry, per-point/pool weights, membership.
    """
    if not np.isfinite(radius) or radius <= 0:
        raise ValueError("Merge radius must be finite and positive")
    base = _points(base_points)
    sources = _points(origins).sort_index()
    if not all(isinstance(i, str) for i in base.index):
        raise ValueError("Base point IDs must be strings")
    _nonnegative(sources["population_weight"], "Origin weights")
    if sources["pool_id"].isna().any():
        raise ValueError("Origin pools must be specified")
    membership = pd.Series(index=sources.index, dtype=object, name="point_id")
    if "base_point_id" in sources:
        valid = sources["base_point_id"].isin(base.index)
        membership.loc[valid] = sources.loc[valid, "base_point_id"]
    eligible = base.loc[base["residents"] > 0].sort_index()
    xy = np.column_stack([sources.geometry.x, sources.geometry.y])
    if len(eligible):
        base_xy = np.column_stack([eligible.geometry.x, eligible.geometry.y])
        tree = cKDTree(base_xy)
        for i in np.flatnonzero(membership.isna()):
            candidates = tree.query_ball_point(xy[i], radius)
            if candidates:
                nearest = min(candidates, key=lambda j: (np.linalg.norm(xy[i] - base_xy[j]), eligible.index[j]))
                membership.iloc[i] = eligible.index[nearest]
    remaining = np.flatnonzero(membership.isna())
    new_points = {}
    if len(remaining):
        # Normalize each pool separately before combining spatial priorities.
        means = sources.groupby("pool_id")["population_weight"].transform("mean").replace(0, 1)
        score = np.sqrt(sources["population_weight"] / means).to_numpy()
        rng = np.random.default_rng(seed)
        order = remaining[np.argsort(rng.exponential(1 / np.maximum(score[remaining], 1e-9)), kind="stable")]
        cells = {}
        seeds = []
        for i in order:
            cell = tuple(np.floor(xy[i] / radius).astype(int))
            nearby = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((cell[0] + dx, cell[1] + dy), [])]
            if any(np.linalg.norm(xy[i] - xy[j]) < radius for j in nearby):
                continue
            seeds.append(i)
            cells.setdefault(cell, []).append(i)
        seeds = sorted(seeds, key=lambda i: sources.index[i])
        seed_tree = cKDTree(xy[seeds])
        for i in remaining:
            distance, _ = seed_tree.query(xy[i])
            candidates = seed_tree.query_ball_point(xy[i], distance + 1e-8)
            chosen = min(candidates, key=lambda j: (np.linalg.norm(xy[i] - xy[seeds[j]]), sources.index[seeds[j]]))
            membership.iloc[i] = f"special_origin:{sources.index[seeds[chosen]]}"
        for point_id, indices in membership.iloc[remaining].groupby(membership.iloc[remaining]).groups.items():
            positions = sources.index.get_indexer(indices)
            weights = score[positions]
            center = np.average(xy[positions], axis=0, weights=weights if weights.sum() else None)
            new_points[point_id] = Point(*center)
    if set(new_points) & set(base.index):
        raise ValueError("New origin IDs collide with base points")
    extra = gpd.GeoDataFrame(geometry=gpd.GeoSeries(new_points, crs=3414), crs=3414)
    registry = gpd.GeoDataFrame(pd.concat([base, extra]), geometry="geometry", crs=3414)
    weights = sources[["pool_id", "population_weight"]].assign(point_id=membership).reset_index(drop=True).groupby(["point_id", "pool_id"], as_index=False)["population_weight"].sum()
    return registry, weights, membership.rename_axis("source_id").reset_index()


def distribute_airport_demand(points, origin_weights, destinations, small_size=50, large_size=200, distance_scale=10_000, seed=0):
    """Allocate independent daily terminal budgets using population * decay.

    Round terminal totals to small_size, then apportion between origin pools.
    Stable terminal/pool seeds make allocation independent of destination order.
    Return extended registry, groups with provenance, and rounding diagnostics.
    """
    if any(isinstance(v, bool) or not isinstance(v, numbers.Integral) or v <= 0 for v in (small_size, large_size)) or large_size <= small_size or large_size % small_size:
        raise ValueError("Large size must be a larger integer multiple of small size")
    if not np.isfinite(distance_scale) or distance_scale <= 0:
        raise ValueError("Distance scale must be finite and positive")
    base, terminals = _points(points), _points(destinations).sort_index()
    if not all(isinstance(i, str) for i in base.index) or not all(isinstance(i, str) for i in terminals.index):
        raise ValueError("Point IDs must be strings")
    if len(base.index.intersection(terminals.index)):
        raise ValueError("Airport destination IDs collide with existing points")
    _nonnegative(terminals["daily_demand"], "Daily demand")
    shares = _nonnegative(terminals["hotel_share"], "Hotel shares")
    if (shares > 1).any():
        raise ValueError("Hotel shares must be between zero and one")
    weights = origin_weights.groupby(["point_id", "pool_id"], as_index=False)["population_weight"].sum()
    _nonnegative(origin_weights["population_weight"], "Origin weights")
    if origin_weights[["point_id", "pool_id"]].isna().any().any():
        raise ValueError("Origin point and pool IDs must be specified")
    if not weights["point_id"].isin(base.index).all():
        raise ValueError("Unknown origin point IDs")
    groups, report = [], []
    for destination_id, terminal in terminals.iterrows():
        units = int(np.floor(terminal.daily_demand / small_size + 0.5))
        split = _apportion([1 - terminal.hotel_share, terminal.hotel_share], units)
        for pool_id, pool_units in zip(("existing_residential", "hotel"), split):
            report.append((destination_id, pool_id, terminal.daily_demand * (terminal.hotel_share if pool_id == "hotel" else 1 - terminal.hotel_share), int(pool_units) * small_size))
            if not pool_units:
                continue
            eligible = weights.loc[weights.pool_id.eq(pool_id) & weights.population_weight.gt(0)].sort_values("point_id")
            if eligible.empty:
                raise ValueError(f"{destination_id} has demand but no positive {pool_id} origins")
            geometry = base.geometry.loc[eligible.point_id]
            distances = geometry.distance(terminal.geometry).to_numpy()
            log_weights = np.log(eligible.population_weight.to_numpy()) - distances / distance_scale
            probabilities = np.exp(log_weights - log_weights.max())
            probabilities /= probabilities.sum()
            digest = hashlib.sha256(f"{seed}:{destination_id}:{pool_id}".encode()).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:16], "big"))
            assignments = rng.multinomial(int(pool_units), probabilities)
            for origin_id, count in zip(eligible.point_id, assignments):
                for size, number in ((large_size, int(count) // (large_size // small_size)), (small_size, int(count) % (large_size // small_size))):
                    for _ in range(number):
                        groups.append((f"special:{destination_id}:{pool_id}:{len(groups)}", size, origin_id, destination_id, "airport", pool_id))
    registry = gpd.GeoDataFrame(pd.concat([base, terminals[["geometry"]]]), geometry="geometry", crs=3414)
    pops = pd.DataFrame(groups, columns=["id", "size", "residenceId", "jobId", "category", "pool_id"])
    diagnostics = pd.DataFrame(report, columns=["destination_id", "pool_id", "requested", "allocated"])
    diagnostics["rounding_delta"] = diagnostics["allocated"] - diagnostics["requested"]
    return registry, pops, diagnostics
