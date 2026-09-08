import geopandas as gpd
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd


def map_values_b_to_bp(
    b_gdf: gpd.GeoDataFrame,
    bp_gdf: gpd.GeoDataFrame,
    b_col: str,
    bp_col: str,
) -> None:
    """
    Maps values from a set column in `building_gdf` to a set column in
    `building_part_gdf`. Applies in place.

    keeps values in bp unchanged if no corresponding b is found
    (though this means an "orphaned" building part with no building).
    """

    if bp_col in bp_gdf.columns:
        # fill in new null values of bp_col (no b value found) with existing bp_gdf[bp_col] values
        bp_gdf[bp_col] = (
            bp_gdf["building_id"].map(b_gdf[b_col]).combine_first(bp_gdf[bp_col])
        )
    else:
        bp_gdf[bp_col] = bp_gdf["building_id"].map(b_gdf[b_col])


def map_values_bp_to_b(
    bp_gdf: gpd.GeoDataFrame,
    b_gdf: gpd.GeoDataFrame,
    bp_col: str,
    b_col: str,
    agg,
) -> None:
    """
    Maps values from a set column in `building_part_gdf` to a set column in
    `building_gdf`. Applies in place.
    As this many-to-one operation, that combines multiple `building_part` values into one `building` value,
    an aggregation function `agg` needs to be supplied.

    `agg`: Series -> value

    keeps values in b unchanged if it has not constituent building parts.
    """
    aggregated = bp_gdf.groupby("building_id")[bp_col].agg(agg)
    if b_col in b_gdf.colums:
        # retain existing b_gdf[b_col] values
        b_gdf[b_col] = b_gdf.index.map(aggregated).combine_first(b_gdf[b_col])
    else:
        b_gdf[b_col] = b_gdf.index.map(aggregated)
