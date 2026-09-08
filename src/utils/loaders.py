import geopandas as gpd
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from src.utils.vis.colors_utils import DEFAULT_MASTERPLAN_LANDUSE_COLORS


def load_masterplan_landuse_geojson_to_gdf(fpath: str, crs: str = 3414):
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
    landuse_gdf["is_landed"] = np.where(landuse_gdf["GPR"] == "LND", True, False)
    landuse_gdf["is_sdp"] = np.where(landuse_gdf["GPR"] == "SDP", True, False)
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


def load_osm_landuse_1_geojson_to_gdf(fpath: str, crs: str = 3414):
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
    gdf: gpd.GeoDataFrame, crs: str = 3414
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
        * `area_m2`
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
    gdf_processed["area_m2"] = gdf_processed.area

    return gdf_processed
