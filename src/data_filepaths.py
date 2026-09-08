import os

path_overture = r"./SG-Singapore_DATA/Overture_foundation"
path_sgdata_base = r"./SG-Singapore_DATA/data_gov_sg/base"
path_osm = r"./SG-Singapore_DATA/OSM_Overpass"

OVERTURE_BUILDING = os.path.join(path_overture, "singapore_building-20260819.parquet")
OVERTURE_BUILDING_PART = os.path.join(
    path_overture, "singapore_building_part-20260819.parquet"
)
MASTERPLAN_LANDUSE = os.path.join(path_sgdata_base, "MP2025LandUse.geojson")

OSM_building = os.path.join(path_osm, "SG_building_20260902.geojson")
OSM_highway = os.path.join(path_osm, "SG_highway_20260902.geojson")
OSM_landuse = os.path.join(path_osm, "SG_landuse_20260902.geojson")
