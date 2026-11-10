import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree


def exponential_bucketed_pairing() -> pd.DataFrame:
    return None


"""
Not currently used
"""


def exponential_random_pairing(
    gdf_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    scale: float,
    k: int = 50,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Randomly create one-to-one A/B pairings, with probability favoring
    shorter distances according to exp(-distance / scale).

    Parameters
    ----------
    gdf_a, gdf_b
        GeoDataFrames with columns ['point_id', 'geometry'] and POINT geometries.
        They should be in a projected CRS where distance units are meaningful.
    scale
        Exponential distance scale lambda. Smaller => stronger preference for
        nearby points.
    k
        Number of nearest B candidates considered for each A.
    seed
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: ['point_id_a', 'point_id_b', 'distance']
    """
    rng = np.random.default_rng(seed)

    if scale <= 0:
        raise ValueError("scale must be > 0")

    if len(gdf_a) > len(gdf_b):
        raise ValueError(
            "For one-to-one matching, gdf_b must have at least as many points as gdf_a."
        )

    # Extract coordinates
    coords_a = np.column_stack((gdf_a.geometry.x, gdf_a.geometry.y))
    coords_b = np.column_stack((gdf_b.geometry.x, gdf_b.geometry.y))

    # KD-tree on B
    tree_b = cKDTree(coords_b)

    # Candidate B indices and distances for every A
    k_eff = min(k, len(gdf_b))
    distances, indices = tree_b.query(coords_a, k=k_eff)

    if k_eff == 1:
        distances = distances[:, None]
        indices = indices[:, None]

    # Randomize order in which A points are assigned.
    # This prevents the result from being driven entirely by A's original order.
    a_order = rng.permutation(len(gdf_a))

    available_b = np.ones(len(gdf_b), dtype=bool)

    result_a = []
    result_b = []
    result_d = []

    for i in a_order:
        candidate_b = indices[i]
        candidate_d = distances[i]

        # Exclude:
        # 1. B points already assigned
        # 2. B points at exactly the same coordinate as A
        mask = available_b[candidate_b] & (candidate_d > 0)

        candidate_b = candidate_b[mask]
        candidate_d = candidate_d[mask]

        if len(candidate_b) == 0:
            continue

        weights = np.exp(-candidate_d / scale)
        weights /= weights.sum()

        j = rng.choice(len(candidate_b), p=weights)
        b_idx = candidate_b[j]

        available_b[b_idx] = False

        result_a.append(gdf_a.iloc[i]["point_id"])
        result_b.append(gdf_b.iloc[b_idx]["point_id"])
        result_d.append(candidate_d[j])

    return pd.DataFrame(
        {
            "point_id_a": result_a,
            "point_id_b": result_b,
            "distance": result_d,
        }
    )


def allocate_b_to_a_gravity(
    gdf_a: gpd.GeoDataFrame,
    gdf_b: gpd.GeoDataFrame,
    k: int = 30,
    distance_scale: float = 10_000.0,
    random_strength: float = 1.0,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Allocate integer counts from B to A.

    Returns columns:
        point_id_a, point_id_b, count

    Properties:
        sum(count for each A) == original A.count
        sum(count for each B) == original B.count

    Parameters
    ----------
    k:
        Number of nearest candidates per point.
        20-50 is usually a reasonable starting range for ~5000 points.
    distance_scale:
        Scale for exponential distance weighting:
            w = exp(-distance / distance_scale)
        In the optimizer we use the equivalent cost:
            distance / distance_scale
    random_strength:
        Amount of random Gumbel perturbation. 0 gives deterministic
        shortest-distance transport; larger values give more randomness.
    seed:
        Random seed for reproducibility.
    """
    rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if not gdf_a.geometry.geom_type.eq("Point").all():
        raise ValueError("gdf_a must contain only POINT geometries")
    if not gdf_b.geometry.geom_type.eq("Point").all():
        raise ValueError("gdf_b must contain only POINT geometries")

    if (gdf_a["count"] < 0).any() or (gdf_b["count"] < 0).any():
        raise ValueError("count must be non-negative")

    if not np.issubdtype(gdf_a["count"].dtype, np.integer):
        raise ValueError("gdf_a['count'] must be integer")
    if not np.issubdtype(gdf_b["count"].dtype, np.integer):
        raise ValueError("gdf_b['count'] must be integer")

    total_a = int(gdf_a["count"].sum())
    total_b = int(gdf_b["count"].sum())

    if total_a != total_b:
        raise ValueError("Total A count must equal total B count")

    if len(gdf_a) == 0 or len(gdf_b) == 0:
        return pd.DataFrame(columns=["point_id_a", "point_id_b", "count"])

    # ------------------------------------------------------------------
    # Coordinates
    #
    # Distances should be in a projected CRS with meaningful units.
    # ------------------------------------------------------------------
    if gdf_a.crs is None or gdf_b.crs is None:
        raise ValueError("Both GeoDataFrames need a CRS")

    if gdf_a.crs != gdf_b.crs:
        gdf_b = gdf_b.to_crs(gdf_a.crs)

    a = gdf_a.copy()
    b = gdf_b.copy()

    # If this is lat/lon, use a metric CRS.
    # For a production workflow, choose an appropriate local CRS rather
    # than blindly using Web Mercator.
    if a.crs.is_geographic:
        metric_crs = a.estimate_utm_crs()
        a = a.to_crs(metric_crs)
        b = b.to_crs(metric_crs)

    Axy = np.column_stack([a.geometry.x.to_numpy(), a.geometry.y.to_numpy()])
    Bxy = np.column_stack([b.geometry.x.to_numpy(), b.geometry.y.to_numpy()])

    na = len(a)
    nb = len(b)

    supply = a["count"].to_numpy(dtype=np.int64)
    demand = b["count"].to_numpy(dtype=np.int64)

    # ------------------------------------------------------------------
    # Sparse candidate edges:
    #   - k nearest A for every B
    #   - k nearest B for every A
    # This gives a roughly O(n k) graph instead of O(n^2).
    # ------------------------------------------------------------------
    tree_a = cKDTree(Axy)
    tree_b = cKDTree(Bxy)

    kb = min(k, na)
    ka = min(k, nb)

    d_ba, idx_ba = tree_a.query(Bxy, k=kb)
    d_ab, idx_ab = tree_b.query(Axy, k=ka)

    edges = set()

    # B -> k nearest A
    if kb == 1:
        d_ba = d_ba[:, None]
        idx_ba = idx_ba[:, None]

    for j in range(nb):
        for col in range(kb):
            i = int(idx_ba[j, col])
            edges.add((i, j))

    # A -> k nearest B
    if ka == 1:
        d_ab = d_ab[:, None]
        idx_ab = idx_ab[:, None]

    for i in range(na):
        for col in range(ka):
            j = int(idx_ab[i, col])
            edges.add((i, j))

    # ------------------------------------------------------------------
    # Add a guaranteed-feasible "northwest corner" transportation plan.
    #
    # These edges guarantee that the sparse optimization problem has
    # at least one feasible solution, regardless of the geometry.
    # ------------------------------------------------------------------
    ia = 0
    jb = 0
    rem_a = supply.copy()
    rem_b = demand.copy()

    while ia < na and jb < nb:
        x = min(rem_a[ia], rem_b[jb])

        if x > 0:
            edges.add((ia, jb))

        rem_a[ia] -= x
        rem_b[jb] -= x

        if rem_a[ia] == 0:
            ia += 1
        if rem_b[jb] == 0:
            jb += 1

    # ------------------------------------------------------------------
    # Convert edge set to arrays.
    # ------------------------------------------------------------------
    edge_list = np.asarray(list(edges), dtype=np.int32)
    ei = edge_list[:, 0]
    ej = edge_list[:, 1]

    # Exact Euclidean distances only for candidate edges.
    dx = Axy[ei, 0] - Bxy[ej, 0]
    dy = Axy[ei, 1] - Bxy[ej, 1]
    dist = np.hypot(dx, dy)

    # ------------------------------------------------------------------
    # Exponential weight:
    #
    #     w_ij = exp(-dist_ij / distance_scale)
    #
    # Maximizing product(weights ** x) is equivalent to minimizing:
    #
    #     sum x_ij * dist_ij / distance_scale
    #
    # We add Gumbel noise to make the solution random.
    # ------------------------------------------------------------------
    base_cost = dist / distance_scale

    if random_strength > 0:
        # Gumbel noise: approximately equivalent to a randomized
        # "soft minimum" choice.
        gumbel = rng.gumbel(size=len(base_cost))
        cost = base_cost - random_strength * gumbel
    else:
        cost = base_cost

    # ------------------------------------------------------------------
    # Transportation constraints:
    #
    # for each A_i: sum_j x_ij = supply_i
    # for each B_j: sum_i x_ij = demand_j
    # ------------------------------------------------------------------
    rows = np.concatenate([ei, na + ej])
    cols = np.concatenate(
        [
            np.arange(len(edges)),
            np.arange(len(edges)),
        ]
    )
    vals = np.ones(2 * len(edges), dtype=np.float64)

    Aeq = coo_matrix((vals, (rows, cols)), shape=(na + nb, len(edges))).tocsr()

    beq = np.concatenate(
        [
            supply.astype(np.float64),
            demand.astype(np.float64),
        ]
    )

    # No upper bounds on edge flow.
    # The transportation polytope is integral for integer margins, so
    # the LP has an integer optimal basic solution.
    result = linprog(
        c=cost,
        A_eq=Aeq,
        b_eq=beq,
        bounds=(0, None),
        method="highs",
    )

    if not result.success:
        raise RuntimeError(f"Transportation optimization failed: {result.message}")

    x = np.rint(result.x).astype(np.int64)

    # ------------------------------------------------------------------
    # Return only nonzero edges.
    # ------------------------------------------------------------------
    mask = x > 0

    out = pd.DataFrame(
        {
            "point_id_a": a.iloc[ei[mask]]["point_id"].to_numpy(),
            "point_id_b": b.iloc[ej[mask]]["point_id"].to_numpy(),
            "count": x[mask],
        }
    )

    # Final integrity checks.
    check_a = out.groupby("point_id_a")["count"].sum()
    check_b = out.groupby("point_id_b")["count"].sum()

    expected_a = a.set_index("point_id")["count"]
    expected_b = b.set_index("point_id")["count"]

    if not check_a.equals(expected_a[expected_a > 0]):
        raise AssertionError("A margins do not match")

    if not check_b.equals(expected_b[expected_b > 0]):
        raise AssertionError("B margins do not match")

    return out


def distribute_gravity_v1(
    res_pops_gdf: gpd.GeoDataFrame,
    work_pops_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Each x_pops_gdf has `point_id` (string), `geometry` (POINT)

    This function handles all the initialization and pop_gdf specific matters.
    Gravity model allocation logic is in the called `allocate_b_to_a_gravity`.

    pops are grouped back first

    Return GDF has:
    * `pop_id` (string)
    * `res_point_id`, `res_geometry`, `work_point_id`, `size`
    """
    assert res_pops_gdf.crs == work_pops_gdf.crs

    res_gdf = gpd.GeoDataFrame(
        res_pops_gdf.groupby("point_id").agg(
            count=("geometry", "count"), geometry=("geometry", "first")
        ),
        geometry="geometry",
        crs=res_pops_gdf.crs,
    ).reset_index()
    work_gdf = gpd.GeoDataFrame(
        work_pops_gdf.groupby("point_id").agg(
            count=("geometry", "count"), geometry=("geometry", "first")
        ),
        geometry="geometry",
        crs=work_pops_gdf.crs,
    ).reset_index()

    result = allocate_b_to_a_gravity(
        res_gdf,
        work_gdf,
        k=30,
        seed=0,
    )

    return result
