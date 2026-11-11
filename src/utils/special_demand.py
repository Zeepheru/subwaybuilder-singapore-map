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
            name = f"{airport.iata} {terminal.name or ''}".strip()
            records.append({
                "point_id": "AIR_" + "_".join(name.split()),
                "name": name,
                "geometry": terminal.coord,
                "daily_demand": airport.annual_passengers * capacities[index] / capacities.sum() / days_per_year,
                "hotel_share": float(share),
            })
    return _points(gpd.GeoDataFrame(records, columns=["point_id", "name", "geometry", "daily_demand", "hotel_share"], geometry="geometry", crs=4326).set_index("point_id"))


def university_destinations(campuses):
    """One modeled daily commute per enrolled student, from existing residences.

    Includes every campus in the higher-education source (universities, arts,
    polytechnics, and ITE). Source coordinates are longitude/latitude. Fractional
    faculty splits are retained until allocation rounds each campus budget.
    Campus housing is not estimated or added until housing data is available.
    """
    records = []
    for campus in campuses:
        if not isinstance(campus.name_short, str) or not campus.name_short.strip():
            raise ValueError("University campuses need a nonempty name_short")
        _nonnegative([campus.students], "Campus students")
        records.append({
            "point_id": "UNI_" + "_".join(campus.name_short.split()),
            "name": campus.name,
            "institution": campus.institution,
            "notes": campus.notes,
            "geometry": campus.coord,
            "category": "university",
            "daily_demand": float(campus.students),
            "hotel_share": 0.0,
        })
    columns = ["point_id", "name", "institution", "notes", "geometry",
               "category", "daily_demand", "hotel_share"]
    destinations = gpd.GeoDataFrame(records, columns=columns, geometry="geometry", crs=4326)
    return _points(destinations.set_index("point_id"))


def hotel_origins(hotels):
    """Build hotel origins from the explicit hotel dataset's TOTALROOMS field.

    Room counts are relative guest weights, not absolute guest estimates. A
    common occupancy/guests-per-room factor cancels during normalization. Keep
    this pool separate even when a hotel shares a residential point. OBJECTID
    supplies stable source IDs independently of input row order or index.
    """
    required = {"OBJECTID", "TOTALROOMS"}
    if not required.issubset(hotels.columns):
        raise ValueError(f"Missing hotel columns: {sorted(required - set(hotels.columns))}")
    identifiers = hotels["OBJECTID"].astype("string").str.strip()
    if identifiers.isna().any() or identifiers.eq("").any():
        raise ValueError("Hotel OBJECTID values must be nonempty")
    hotels = hotels.copy()
    hotels.index = pd.Index([f"hotel:{i}" for i in identifiers], name="source_id")
    hotels = _points(hotels)
    rooms = pd.to_numeric(
        hotels["TOTALROOMS"].astype("string").str.replace(",", "", regex=False),
        errors="raise",
    ).to_numpy(dtype=float, na_value=np.nan)
    rooms = _nonnegative(rooms, "Hotel room counts")
    if (rooms != np.floor(rooms)).any():
        raise ValueError("Hotel room counts must be integers")
    hotels["population_weight"] = rooms
    hotels["pool_id"] = "hotel"
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


def distribute_airport_demand(points, origin_weights, destinations, small_size=50, large_size=200, distance_scale=10_000, seed=0,
                              group_allocation_mode="large_first"):
    """Airport-only compatibility interface; use distribute_special_demand for classes."""
    registry, pops, report = distribute_special_demand(
        points, origin_weights, destinations.assign(category="airport"),
        distance_scales={"airport": distance_scale}, small_size=small_size,
        large_size=large_size, seed=seed,
        group_allocation_modes={"airport": group_allocation_mode},
    )
    return registry, pops, report.drop(columns=["category", "distance_scale", "group_allocation_mode"])


def distribute_special_demand(points, origin_weights, destinations, distance_scales,
                              small_size=50, large_size=200, seed=0,
                              group_allocation_modes=None):
    """Allocate additive budgets with a separate distance scale per demand class.

    Destinations have category, daily_demand, and hotel_share. University demand
    uses only existing_residential; airport demand splits residential/hotel pools.
    distance_scales maps each category to a finite positive scale in metres.
    Round destination totals to small_size before apportioning origin pools.
    group_allocation_modes maps each class to large_first (default) or small_first.
    Large-first samples full large_size groups, then only small_size remainders;
    small-first samples small_size units before combining by endpoint pair.
    Stable destination/pool seeds make allocation independent of input order.
    Return extended registry, groups with provenance, and rounding diagnostics.
    """
    if any(isinstance(v, bool) or not isinstance(v, numbers.Integral) or v <= 0 for v in (small_size, large_size)) or large_size <= small_size or large_size % small_size:
        raise ValueError("Large size must be a larger integer multiple of small size")
    base, terminals = _points(points), _points(destinations).sort_index()
    required = {"category", "daily_demand", "hotel_share"}
    if not required.issubset(terminals.columns):
        raise ValueError(f"Missing destination columns: {sorted(required - set(terminals.columns))}")
    categories = terminals["category"]
    if not categories.map(lambda value: isinstance(value, str) and bool(value.strip())).all():
        raise ValueError("Destination categories must be nonempty strings")
    missing = set(categories) - set(distance_scales)
    if missing:
        raise ValueError(f"Missing distance scales for demand classes: {sorted(missing)}")
    for category, scale in distance_scales.items():
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"Distance scale for {category} must be finite and positive")
    if group_allocation_modes is None:
        group_allocation_modes = dict.fromkeys(categories.unique(), "large_first")
    missing_modes = set(categories) - set(group_allocation_modes)
    if missing_modes:
        raise ValueError(f"Missing group allocation modes for demand classes: {sorted(missing_modes)}")
    for category, mode in group_allocation_modes.items():
        if mode not in ("large_first", "small_first"):
            raise ValueError(f"Group allocation mode for {category} must be large_first or small_first")
    if not all(isinstance(i, str) for i in base.index) or not all(isinstance(i, str) for i in terminals.index):
        raise ValueError("Point IDs must be strings")
    if len(base.index.intersection(terminals.index)):
        raise ValueError("Special-demand destination IDs collide with existing points")
    _nonnegative(terminals["daily_demand"], "Daily demand")
    shares = _nonnegative(terminals["hotel_share"], "Hotel shares")
    if (shares > 1).any():
        raise ValueError("Hotel shares must be between zero and one")
    if (categories.eq("university") & terminals["hotel_share"].ne(0)).any():
        raise ValueError("University demand must use only existing residential origins")
    weights = origin_weights.groupby(["point_id", "pool_id"], as_index=False)["population_weight"].sum()
    _nonnegative(origin_weights["population_weight"], "Origin weights")
    if origin_weights[["point_id", "pool_id"]].isna().any().any():
        raise ValueError("Origin point and pool IDs must be specified")
    if not weights["point_id"].isin(base.index).all():
        raise ValueError("Unknown origin point IDs")
    groups, report = [], []
    for destination_id, terminal in terminals.iterrows():
        category = terminal.category
        distance_scale = distance_scales[category]
        group_mode = group_allocation_modes[category]
        units = int(np.floor(terminal.daily_demand / small_size + 0.5))
        split = _apportion([1 - terminal.hotel_share, terminal.hotel_share], units)
        pools = (("existing_residential", units),) if category == "university" else zip(("existing_residential", "hotel"), split)
        for pool_id, pool_units in pools:
            report.append((destination_id, pool_id, terminal.daily_demand * (terminal.hotel_share if pool_id == "hotel" else 1 - terminal.hotel_share), int(pool_units) * small_size, category, distance_scale, group_mode))
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
            large_units = large_size // small_size
            if group_mode == "large_first":
                large_count, remainder = divmod(int(pool_units), large_units)
                large_assignments = rng.multinomial(large_count, probabilities)
                small_assignments = rng.multinomial(remainder, probabilities)
            else:
                assignments = rng.multinomial(int(pool_units), probabilities)
                large_assignments = assignments // large_units
                small_assignments = assignments % large_units
            for origin_id, large_count, small_count in zip(eligible.point_id, large_assignments, small_assignments):
                for size, number in ((large_size, int(large_count)), (small_size, int(small_count))):
                    for _ in range(number):
                        groups.append((f"special:{destination_id}:{pool_id}:{len(groups)}", size, origin_id, destination_id, category, pool_id))
    registry = gpd.GeoDataFrame(pd.concat([base, terminals[["geometry"]]]), geometry="geometry", crs=3414)
    pops = pd.DataFrame(groups, columns=["id", "size", "residenceId", "jobId", "category", "pool_id"])
    diagnostics = pd.DataFrame(report, columns=["destination_id", "pool_id", "requested", "allocated", "category", "distance_scale", "group_allocation_mode"])
    diagnostics["rounding_delta"] = diagnostics["allocated"] - diagnostics["requested"]
    return registry, pops, diagnostics
