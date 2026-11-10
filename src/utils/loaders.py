import geopandas as gpd
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

import src.data_filepaths as data_filepaths
from src.utils.vis.colors_utils import DEFAULT_MASTERPLAN_LANDUSE_COLORS


def load_masterplan_landuse_geojson_to_gdf(fpath: str, crs = 3414):
    """
    Loaded columns:
    * LU_DESC
    * LU_TEXT - "U, W, E, H" - basically shortened text to show on map GUIs
        * removed
    * GPR - special values: LND (landed), EVA (plots with no GPR),
        SDP (subject to detailed planning)
    * WHI_Q_MX - maximum white proportion, exactly 12 plots
    * GPR_B_MN - minimum base plot use for white landuse, exactly 60 plots
    * INC_CRC, FMEL_UPD_D - various IDs
        * removed
    * SHAPE.AREA, SHAPE.LEN, geometry

    Special processing:
    * GPR - non-numeric values removed
        * LND - new column `is_landed`, GPR := 0
        * EVA - GPR := 0
        * SDP - new column `is_sdp`, GPR := 0
    * add `color` column

    Renamed columns:
    * `gpr`, LU_DESC -> `landuse`, `white_q_max`, `gpr_b_min`, `is_landed`, `is_sdp`
    """

    default_colors = DEFAULT_MASTERPLAN_LANDUSE_COLORS
    for k, v in default_colors.items():
        default_colors[k] = mcolors.to_rgba(v)

    # select columns
    landuse_gdf = gpd.read_file(fpath)

    landuse_gdf = landuse_gdf.set_index("OBJECTID")
    landuse_gdf = landuse_gdf[["LU_DESC", "GPR", "WHI_Q_MX", "GPR_B_MN", "geometry"]]

    # modifications
    landuse_gdf["is_landed"] = landuse_gdf["GPR"] == "LND"
    landuse_gdf["is_sdp"] = landuse_gdf["GPR"] == "SDP"
    
    # print(landuse_gdf["GPR"].value_counts())
    landuse_gdf["GPR"] = landuse_gdf["GPR"].replace(["LND", "SDP", "EVA"], "0")
    # print(landuse_gdf["GPR"].value_counts())
    landuse_gdf["GPR"] = pd.to_numeric(landuse_gdf["GPR"])

    # rename columns
    landuse_gdf = landuse_gdf.rename(
        columns={
            "GPR": "gpr",
            "LU_DESC": "landuse",
            "WHI_Q_MX": "white_q_max",
            "GPR_B_MN": "gpr_b_min",
        }
    )

    # add color
    landuse_gdf["color"] = landuse_gdf["landuse"].map(default_colors)

    return landuse_gdf.to_crs(crs)


def load_osm_landuse_1_geojson_to_gdf(fpath: str, crs = 3414):
    """
    Removes geometry=POINT, LINESTRING, keeps only POLYGON and MULTIPOLYGON

    By default, only loads columns
    * `landuse`
    * `geometry`
    
    Data modifications
    * `landuse=industrial` + `industrial=port` -> `landuse=industrial_port`

    """
    base_gdf = gpd.read_file(fpath)

    out_gdf = base_gdf[["landuse", "geometry"]]

    out_gdf = out_gdf[out_gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    out_gdf.loc[base_gdf["industrial"] == "port", "landuse"] = "industrial_port"

    return out_gdf.to_crs(crs)


def process_loaded_building_df(
    gdf: gpd.GeoDataFrame, crs = 3414
) -> gpd.GeoDataFrame:
    """Process Overture export parquets (loaded as Geopandas GeoDataFrames).
    Reproject to CRS (default: 3414).
    Add and remove relevant data columns to building/building_part geodataframes.

    Sets index to id.

    Retained columns:
    * `id`, `names`, `sources`
    * `height`, `min_height`
    * `is_underground`, `num_floors`, `num_floors_underground`, `min_floor`
    * `subtype`, `class`, `has_parts` - only for building
    * `geometry`
    * `building_id` - only available if it's building_part
    * Removed: `level`, `roof_*`, `facade-*`, `version`, `type` (just building, building_part)

    Added columns:
    * Simple computations
        * `centroid`
        * `area`
    * `src_dataset_label`

    Altered columns:
    """

    REFERENCE_COL_VALUES = {
        "class": [
            "nan",
            "industrial",
            "office",
            "parking",
            "dormitory",
            "transportation",
            "residential",
            "commercial",
            "warehouse",
            "train_station",
            "roof",
            "service",
            "retail",
            "manufacture",
            "hut",
            "storage_tank",
            "fire_station",
            "shed",
            "boathouse",
            "garage",
            "university",
            "grandstand",
            "public",
            "hangar",
            "pavilion",
            "church",
            "guardhouse",
            "apartments",
            "terrace",
            "semidetached_house",
            "house",
            "detached",
            "school",
            "college",
            "temple",
            "chapel",
            "civic",
            "library",
            "government",
            "mosque",
            "hospital",
            "garages",
            "farm_auxiliary",
            "bunker",
            "toilets",
            "sports_hall",
            "kindergarten",
            "bungalow",
            "greenhouse",
            "shrine",
            "sports_centre",
            "stadium",
            "hotel",
            "carport",
            "stable",
            "religious",
            "synagogue",
            "bridge_structure",
            "kiosk",
            "monastery",
            "post_office",
            "supermarket",
        ],
        "subtype": [
            "nan",
            "industrial",
            "commercial",
            "transportation",
            "residential",
            "civic",
            "outbuilding",
            "service",
            "education",
            "entertainment",
            "religious",
            "medical",
            "agricultural",
            "military",
        ],
    }

    retained_columns = (
        ["id", "names", "sources", "height", "min_height"]
        + ["is_underground", "num_floors", "num_floors_underground", "min_floor"]
        + ["geometry"]
    )

    if "building_id" in gdf.columns:
        gdf_processed = gdf[retained_columns + ["building_id"]]
    else:
        gdf_processed = gdf[retained_columns + ["subtype", "class", "has_parts"]]

    gdf_processed["src_dataset_label"] = gdf["sources"].map(
        lambda x: x[0]["dataset"]
    )  # extract dataset label

    gdf_processed = gdf_processed.set_index("id")
    gdf_processed = gdf_processed.to_crs(crs)
    gdf_processed["centroid"] = gdf_processed.centroid
    gdf_processed["area"] = gdf_processed.area

    return gdf_processed


def load_boundary_pln_region(fpath: str = data_filepaths.BASE_PLN_REGION, crs=3414):
    """
    Initial Schema:
    * `OBJECTID`
    * `REGION_N`: name
    * `REGION_C`: code
    * `INC_CRC`, `FMEL_UPD_D`
    * `SHAPE.AREA`, `SHAPE.LEN`, `geometry`

    Output Schema:
    * `pln_region_id` as index
    * `pln_region_name`
    * `area`, `geometry`

    """

    loaded_gdf = gpd.read_file(fpath)
    loaded_gdf = loaded_gdf.to_crs(crs)

    new_gdf = loaded_gdf[["REGION_N", "REGION_C", "SHAPE.AREA", "geometry"]]
    new_gdf = new_gdf.rename(
        columns={
            "REGION_N": "pln_region_name",
            "REGION_C": "pln_region_id",
            "SHAPE.AREA": "area",
        }
    )
    new_gdf = new_gdf.set_index("pln_region_id")

    return new_gdf


def load_boundary_pln_area(fpath: str = data_filepaths.BASE_PLN_AREA, crs=3414):
    """
    Initial Schema:
    * `OBJECTID`
    * `PLN_AREA_N`: name
    * `PLN_AREA_C`: code
    * `REGION_N`, `REGION_C`
    * `INC_CRC`, `FMEL_UPD_D`
    * `SHAPE.AREA`, `SHAPE.LEN`, `geometry`

    Output Schema:
    * `pln_area_id` as index
    * `pln_area_name`
    * `pln_region_id`
    * `pln_region_name`
    * `area`, `geometry`

    """

    loaded_gdf = gpd.read_file(fpath)
    loaded_gdf = loaded_gdf.to_crs(crs)

    new_gdf = loaded_gdf[
        ["PLN_AREA_N", "PLN_AREA_C", "REGION_N", "REGION_C", "SHAPE.AREA", "geometry"]
    ]
    new_gdf = new_gdf.rename(
        columns={
            "PLN_AREA_N": "pln_area_name",
            "PLN_AREA_C": "pln_area_id",
            "REGION_N": "pln_region_name",
            "REGION_C": "pln_region_id",
            "SHAPE.AREA": "area",
        }
    )
    new_gdf = new_gdf.set_index("pln_area_id")

    return new_gdf


def load_boundary_subzone(fpath: str = data_filepaths.BASE_SUBZONE, crs=3414):
    """
    Initial Schema:
    * `OBJECTID`
    * `SUBZONE_NO`
    * `SUBZONE_N`: name
    * `SUBZONE_C`: code
    * `PLN_AREA_N`, `PLN_AREA_C`, `REGION_N`, `REGION_C`
    * `INC_CRC`, `FMEL_UPD_D`
    * `SHAPE.AREA`, `SHAPE.LEN`, `geometry`

    Output Schema:
    * `subzone_id` as index
    * `subzone_name`
    * `pln_area_id`
    * `pln_area_name`
    * `pln_region_id`
    * `pln_region_name`
    * `area`, `geometry`

    """

    loaded_gdf = gpd.read_file(fpath)
    loaded_gdf = loaded_gdf.to_crs(crs)

    new_gdf = loaded_gdf[
        [
            "SUBZONE_N",
            "SUBZONE_C",
            "PLN_AREA_N",
            "PLN_AREA_C",
            "REGION_N",
            "REGION_C",
            "SHAPE.AREA",
            "geometry",
        ]
    ]
    new_gdf = new_gdf.rename(
        columns={
            "SUBZONE_N": "subzone_name",
            "SUBZONE_C": "subzone_id",
            "PLN_AREA_N": "pln_area_name",
            "PLN_AREA_C": "pln_area_id",
            "REGION_N": "pln_region_name",
            "REGION_C": "pln_region_id",
            "SHAPE.AREA": "area",
        }
    )
    new_gdf = new_gdf.set_index("subzone_id")

    return new_gdf
