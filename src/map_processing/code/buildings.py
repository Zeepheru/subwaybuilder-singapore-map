from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

# these are classes
FLOOR_HEIGHTS = {
    "default": 3.6,
    "landed": 3.2,
    "house": 3.2,
    "bungalow": 3.5,
    "detached": 3.5,
    "terrace": 3.2,
    "semidetached_house": 3.2,
    "condo": 3.4,
    "residential": 3,
    "apartments": 3,
    "dormitory": 3,
    "hotel": 3.1,
    "office": 3.9,
    "government": 3.9,
    "commercial": 3.8,
    "retail": 3.8,
    "public": 3.8,
    "supermarket": 4.5,
    "school": 3.4,
    "university": 3.5,
    "hospital": 3.6,
    "industrial": 5,
    "manufacture": 5.2,
    "warehouse": 6,
    # not really gonna mean anything, idt any of them have building:levels anyway:
    "hangar": 6,
    "garage": 2.8,
    "parking": 2.8,
}
FLOOR_COUNTS_DEFAULT = {
    "default": 1,
    "landed": 1,
    "house": 2,
    "bungalow": 1,
    "detached": 2,
    "terrace": 1.5,
    "semidetached_house": 1.5,
    "condo": 5,
    "residential": 5,
    "apartments": 5,
    "dormitory": 3,
    "hotel": 4,
    "office": 4,
    "government": 2,
    "commercial": 2,
    "retail": 2,
    "public": 2,
    "supermarket": 1,
    "school": 3,
    "university": 4,
    "hospital": 3,
    "industrial": 1,
    "manufacture": 1,
    "warehouse": 1,
    # not really gonna mean anything, idt any of them have building:levels anyway:
    "hangar": 1,
    "garage": 1,
    "parking": 2,
}

RES_GPR_FLOORCOUNT_THRESHOLDS = {1.4: 5, 1.6: 12, 2.1: 24, 2.8: 36}


def _height_assign_helper(
    b_gdf: gpd.GeoDataFrame,
    bp_gdf: gpd.GeoDataFrame,
    height_col: str,
    floor_col: str,
    default_bldg_height,
):
    b_gdf, bp_gdf = b_gdf.copy(), bp_gdf.copy()

    mask_b_w_heights = ~b_gdf[height_col].isna()
    mask_bp_w_heights = ~bp_gdf[height_col].isna()
    mask_b_w_floors = ~b_gdf[floor_col].isna()
    mask_bp_w_floors = ~bp_gdf[floor_col].isna()

    if "class" not in bp_gdf.columns:
        bp_gdf = bp_gdf.merge(
            b_gdf["class"], left_on="building_id", right_index=True
        )

    def h_fc(floors, b_class):
        if b_class not in FLOOR_HEIGHTS:
            return floors * FLOOR_HEIGHTS["default"]
        return floors * FLOOR_HEIGHTS[b_class]

    def h_no_fc(b_class):
        floors = (
            FLOOR_COUNTS_DEFAULT[b_class]
            if b_class in FLOOR_COUNTS_DEFAULT
            else FLOOR_COUNTS_DEFAULT["default"]
        )
        floor_height = (
            FLOOR_HEIGHTS[b_class]
            if b_class in FLOOR_HEIGHTS
            else FLOOR_HEIGHTS["default"]
        )
        return floors * floor_height

    # might wanna have a custom list as well
    if default_bldg_height is not None:
        # e.g. for min_height -> default sets to 0
        b_gdf.loc[~mask_b_w_heights & ~mask_b_w_floors, height_col] = (
            default_bldg_height
        )
        bp_gdf.loc[~mask_bp_w_heights & ~mask_bp_w_floors, height_col] = (
            default_bldg_height
        )
    else:
        # assign using default floor_count and floor_height
        b_gdf.loc[~mask_b_w_heights & ~mask_b_w_floors, height_col] = b_gdf[
            ~mask_b_w_heights & ~mask_b_w_floors
        ].apply(lambda row: h_no_fc(row["class"]), axis=1)
        bp_gdf.loc[~mask_bp_w_heights & ~mask_bp_w_floors, height_col] = bp_gdf[
            ~mask_bp_w_heights & ~mask_bp_w_floors
        ].apply(lambda row: h_no_fc(row["class"]), axis=1)

    # also assign building with has_parts=true, with no height/floor -> height=0
    # necessary for bpart height calculations later
    b_gdf.loc[~mask_b_w_heights & ~mask_b_w_floors & b_gdf["has_parts"], height_col] = 0

    b_gdf.loc[~mask_b_w_heights & mask_b_w_floors, height_col] = b_gdf[
        ~mask_b_w_heights & mask_b_w_floors
    ].apply(lambda row: h_fc(row[floor_col], row["class"]), axis=1)
    bp_gdf.loc[~mask_bp_w_heights & mask_bp_w_floors, height_col] = bp_gdf[
        ~mask_bp_w_heights & mask_bp_w_floors
    ].apply(lambda row: h_fc(row[floor_col], row["class"]), axis=1)

    return b_gdf, bp_gdf


def assign_height_from_floors(
    b_gdf: gpd.GeoDataFrame, bp_gdf: gpd.GeoDataFrame, default_bldg_height=4.0
):
    return _height_assign_helper(
        b_gdf, bp_gdf, "height", "num_floors", default_bldg_height
    )


def assign_min_height_from_min_floor(
    b_gdf: gpd.GeoDataFrame, bp_gdf: gpd.GeoDataFrame
):
    return _height_assign_helper(
        b_gdf, bp_gdf, "min_height", "min_floor", default_bldg_height=0
    )


### === building height envelope stuff ===

def polygon_components(geom):
    """Extract nonempty polygons from a Shapely geometry."""
    if geom is None or geom.is_empty:
        return

    if isinstance(geom, Polygon):
        if geom.area > 0:
            yield geom

    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            if not poly.is_empty and poly.area > 0:
                yield poly

    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from polygon_components(part)


def resolve_building_envelope(
    b_gdf,
    bp_gdf,
    dissolve=True,
    min_area=0.0,
    remove_elevated_parts=False,
    min_height_fraction_threshold=0.5,
):
    """
    Resolve overlaps across all buildings and parts using maximum height.
    Outputs one unified b_gdf.

    Parameters
    ----------
    b_gdf : GeoDataFrame
        Indexed by building ID, with height and geometry.

    bp_gdf : GeoDataFrame
        Indexed by part ID, with building_id, height, geometry.
        Requires min_height when remove_elevated_parts is enabled.

    dissolve : bool
        Merge adjacent output polygons at identical heights,
        within each parent building.

    min_area : float
        Minimum retained polygon area in CRS units squared.

    remove_elevated_parts : bool
        Exclude parts with min_height > 0 and
        min_height > min_height_fraction_threshold * height before resolving
        overlaps, unless another part overlaps it in positive area and has
        height >= its min_height - 1. Supporting parts may belong
        to any building and are checked before filtering. Missing min_height
        or height values do not trigger removal. Parent buildings are retained.

    min_height_fraction_threshold : float
        Fraction of total height above which elevated parts are excluded.
        Must be between 0 and 1 inclusive when the filter is enabled.

    Returns
    -------
    GeoDataFrame
        Columns:
            building_id
            height
            geometry

        All output polygons are disjoint in area across all buildings.
        Overlaps retain the building_id of the tallest candidate. Equal-height
        ties go to the first candidate in input order (parent before parts).
    """

    if b_gdf.crs != bp_gdf.crs:
        raise ValueError("Building and part CRS must match")

    if remove_elevated_parts:
        if not 0 <= min_height_fraction_threshold <= 1:
            raise ValueError("min_height_fraction_threshold must be between 0 and 1")
        if "min_height" not in bp_gdf.columns:
            raise ValueError("Parts must have min_height when remove_elevated_parts is enabled")
        elevated = (
            (bp_gdf["min_height"] > 0)
            & (bp_gdf["min_height"] > min_height_fraction_threshold * bp_gdf["height"])
        ).fillna(False).to_numpy(dtype=bool, copy=True)
        part_index = bp_gdf.sindex
        for position in np.flatnonzero(elevated):
            part = bp_gdf.iloc[position]
            if part.geometry is None or part.geometry.is_empty:
                continue
            underneath = part_index.query(part.geometry, predicate="intersects")
            underneath = underneath[underneath != position]
            lower_parts = bp_gdf.iloc[underneath]
            lower_parts = lower_parts.loc[
                (lower_parts["height"] >= part.min_height - 1).fillna(False)
            ]
            if any(
                lower_geom.intersection(part.geometry).area > 0
                for lower_geom in lower_parts.geometry
            ):
                elevated[position] = False
        bp_gdf = bp_gdf.loc[~elevated]

    # Group parts by parent building ID.
    parts_by_building = defaultdict(list)

    for part_id, part in bp_gdf.iterrows():
        if pd.isna(part.building_id):
            continue

        parts_by_building[part.building_id].append((part.height, part.geometry))

    # Collect every parent and its parts before resolving overlaps globally.
    candidates = []
    for building_id, building in b_gdf.iterrows():
        building_geom = building.geometry
        if building_geom is None or building_geom.is_empty:
            continue

        building_candidates = [(building.height, building_geom)]
        building_candidates.extend(parts_by_building.get(building_id, []))
        candidates.extend(
            (building_id, float(height), geom)
            for height, geom in building_candidates
            if pd.notna(height) and geom is not None and not geom.is_empty
        )

    # Stable sorting gives equal-height overlaps to the first input candidate.
    candidates.sort(key=lambda candidate: candidate[1], reverse=True)
    geometries = gpd.GeoSeries(
        [geom for _, _, geom in candidates], crs=b_gdf.crs
    )
    spatial_index = geometries.sindex
    resolved = defaultdict(list)

    for position, (building_id, height, geom) in enumerate(candidates):
        # Earlier candidates are at least as tall. Subtract their full geometry,
        # including any tiny regions discarded by min_area.
        overlaps = spatial_index.query(geom, predicate="intersects")
        overlaps = overlaps[overlaps < position]
        remaining = (
            geom.difference(unary_union(geometries.iloc[overlaps]))
            if len(overlaps)
            else geom
        )
        for poly in polygon_components(remaining):
            if poly.area > min_area:
                resolved[(building_id, height)].append(poly)

    results = []
    for (building_id, height), geoms in resolved.items():
        if dissolve:
            geoms = polygon_components(unary_union(geoms))
        for poly in geoms:
            if poly.area > min_area:
                results.append(
                    {
                        "building_id": building_id,
                        "height": height,
                        "geometry": poly,
                    }
                )

    return gpd.GeoDataFrame(
        results,
        columns=["building_id", "height", "geometry"],
        geometry="geometry",
        crs=b_gdf.crs,
    ).reset_index(drop=True)
