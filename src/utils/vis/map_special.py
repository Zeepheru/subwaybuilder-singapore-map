import io
import logging

import geopandas as gpd
import ipywidgets as widgets
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from ipywidgets import FloatRangeSlider, Layout, Output, VBox, jsdlink
from lonboard import Map, PolygonLayer, ScatterplotLayer
from lonboard.basemap import CartoStyle
from lonboard.controls import MultiRangeSlider
from lonboard.layer_extension import DataFilterExtension
from shapely.geometry import Point

from src.utils.loaders import process_loaded_building_df
from src.utils.vis.colors_utils import CategoricalColorMap

logger = logging.getLogger(__name__)

from src.utils.vis.map import (
    DEFAULT_VIEW_STATE_SINGAPORE,
    MapExplorer,
    MapWrapper,
    apply_categorical_colormap,
)

# other kinds of nonstandard maps

# basically just fully define it idgaf at this point

### UTILS

def drop_nonactive_geometry_columns(gdf):
    active_geom = gdf.geometry.name

    return gdf.drop(
        columns=[
            col
            for col in gdf.columns
            if isinstance(gdf[col].dtype, gpd.array.GeometryDtype) and col != active_geom
        ]
    )

### BUILD

def build_map_building_basic(b_gdf: gpd.GeoDataFrame):
    """
    No elevation, no fill color, just buildings

    Click on buildings to view their characteristics :)
    """
    b_gdf = b_gdf.drop(columns=["centroid"]).to_crs(4326)
    b_layer = PolygonLayer.from_geopandas(
        b_gdf,
        # since it returns both values and the cmap
    )

    m = Map(layers=[b_layer], height=720)

    m.set_view_state(
        longitude=103.8557931,
        latitude=1.2843934,
        pitch=70,
        bearing=340,
        zoom=14,
    )

    return m


def build_map_building_demand_type(
    b_dmdtype_gdf: gpd.GeoDataFrame, cmap: CategoricalColorMap
):
    b_dmdtype_gdf = b_dmdtype_gdf.copy()
    b_dmdtype_gdf = b_dmdtype_gdf.drop(columns=["centroid"]).to_crs(4326)

    b_layer = PolygonLayer.from_geopandas(
        b_dmdtype_gdf,
        extruded=True,
        get_elevation=(b_dmdtype_gdf["net_floors"] * 3.6).fillna(10).astype(np.float32),
        # since it returns both values and the cmap
        get_fill_color=apply_categorical_colormap(
            b_dmdtype_gdf["demand_type"], color_mapping=cmap
        )[0],
    )

    m = Map(layers=[b_layer], height=720)

    m.set_view_state(
        longitude=103.8557931,
        latitude=1.2843934,
        pitch=70,
        bearing=340,
        zoom=14,
    )

    return m


def build_map_point_floorspace_demand_type(
    b_dmdtype_gdf_w_fs: gpd.GeoDataFrame,
    cmap: CategoricalColorMap = None,
    floorspace_col: str = "floorspace",
    demand_type_col: str = "demand_type",
    radius_max: float = 200,
    *args,
    **kwargs,
):
    """
    Assumes only one point geometry column, set to `geometry` by default but can be changed in `geometry_col`
    """
    return build_map_point_numeric_and_category(
        b_dmdtype_gdf_w_fs,
        cmap=cmap,
        numeric_col=floorspace_col,
        category_col=demand_type_col,
        radius_max=radius_max,
        *args,
        **kwargs,
    )


def build_map_point_numeric_and_category(
    gdf: gpd.GeoDataFrame,
    cmap: CategoricalColorMap = None,
    numeric_col: str = None,
    category_col: str = None,
    radius_max: float = 200,
    radius_default: float = 50,
    opacity: float = 0.4,
    geometry_col: str = "geometry",
):
    """
    This can be used for any pairs of (numeric, category) data

    Assumes only one point geometry column, set to `geometry` by default but can be changed in `geometry_col`

    Without a cmap, category_col col gets the usual default cmap
    """
    assert geometry_col in gdf.columns, f"{geometry_col} column not found in gdf to be mapped"

    original_crs = gdf.crs  # should be 3414

    gdf = gdf.copy()
    gdf = (
        gdf.set_geometry(geometry_col)
        .set_crs(original_crs)  # set original first
        .to_crs(4326)  # then only change to WGS 84
    )

    gdf = drop_nonactive_geometry_columns(gdf)

    # decide radiuses
    if not numeric_col:
        radii = radius_default
        scale = 1
    elif numeric_col not in gdf.columns:
        print(f"Warning: desired category col {category_col} not in gdf to be mapped")
        radii = radius_default
        scale = 1
    else:
        fspace_adjusted = np.sqrt(gdf[numeric_col])

        radii = fspace_adjusted
        scale = radius_max / max(radii)

    # decide fill color
    if not category_col:
        fill_color = None
    elif category_col not in gdf.columns:
        print(f"Warning: desired category col {category_col} not in gdf to be mapped")
        fill_color = None
    elif cmap:
        fill_color, _ = apply_categorical_colormap(
            gdf[category_col], color_mapping=cmap
        )
    else:
        fill_color, _ = apply_categorical_colormap(gdf[category_col], k=10)

    b_layer = ScatterplotLayer.from_geopandas(
        gdf,
        get_radius=radii,
        get_fill_color=fill_color,
        # formatting
        get_line_width=0,
        opacity=opacity,
        radius_scale=scale,
    )

    m = Map(layers=[b_layer], height=720)

    m.set_view_state(**DEFAULT_VIEW_STATE_SINGAPORE)

    return m
