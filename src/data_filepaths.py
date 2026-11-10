import os

path_overture = r"./SG-Singapore_DATA/Overture_foundation"
path_sgdata_base = r"./SG-Singapore_DATA/data_gov_sg/base"
path_sgdata_resident = r"./SG-Singapore_DATA/data_gov_sg/resident"
path_sgdata_employment = r"./SG-Singapore_DATA/data_gov_sg/employment"
path_sd_military = r"./SG-Singapore_DATA/special_demand/military"
path_sd_education = r"./SG-Singapore_DATA/special_demand/education"
path_osm = r"./SG-Singapore_DATA/OSM_Overpass"
path_data_intermediate = r"./src/data_intermediate"

OVERTURE_BUILDING = os.path.join(
    path_overture,
    # "singapore_building-20260819.parquet",
    "singapore_building-20261021.parquet",
)
OVERTURE_BUILDING_PART = os.path.join(
    path_overture,
    # "singapore_building_part-20260819.parquet",
    "singapore_building_part-20261021.parquet",
)
MASTERPLAN_LANDUSE = os.path.join(path_sgdata_base, "MP2025LandUse.geojson")

BASE_PLN_AREA = os.path.join(path_sgdata_base, "MP2025PlanningAreaBoundary.geojson")
BASE_PLN_REGION = os.path.join(path_sgdata_base, "MP2025RegionBoundary.geojson")
BASE_SUBZONE = os.path.join(path_sgdata_base, "MP2019SubzoneBoundary.geojson")

OSM_building = os.path.join(path_osm, "SG_building_20260902.geojson")
OSM_highway = os.path.join(path_osm, "SG_highway_20260902.geojson")
OSM_landuse = os.path.join(path_osm, "SG_landuse_20260915.geojson")

OUT_DEMAND_DATA = r"./out/demand_data"