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
from lonboard import Map, PolygonLayer
from lonboard.basemap import CartoStyle
from lonboard.controls import MultiRangeSlider
from lonboard.layer_extension import DataFilterExtension
from shapely.geometry import Point

from src.utils.loaders import process_loaded_building_df
from src.utils.vis.colors_utils import CategoricalColorMap

logger = logging.getLogger(__name__)

from src.utils.vis.map import MapExplorer, MapWrapper, apply_categorical_colormap

# other kinds of nonstandard maps

# basically just fully define it idgaf at this point


def build_map_building_demand_type(
    b_dmdtype_gdf: gpd.GeoDataFrame, cmap: CategoricalColorMap
):
    b_dmdtype_gdf = b_dmdtype_gdf.copy()
    b_dmdtype_gdf = b_dmdtype_gdf.drop(columns=["centroid"]).to_crs(4326)

    b_layer = PolygonLayer.from_geopandas(
        b_dmdtype_gdf,
        extruded=True,
        get_elevation=(b_dmdtype_gdf["net_floors"] * 4)
        .fillna(10)
        .astype(np.float32),
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
