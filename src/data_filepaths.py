import os

path_overture = r"./SG-Singapore_DATA/Overture_foundation"
path_sgdata_base = r"./SG-Singapore_DATA/data_gov_sg/base"
path_sgdata_resident = r"./SG-Singapore_DATA/data_gov_sg/resident"
path_sgdata_employment = r"./SG-Singapore_DATA/data_gov_sg/employment"
path_sd_military = r"./SG-Singapore_DATA/special_demand/military"
path_sd_education = r"./SG-Singapore_DATA/special_demand/education"
path_osm = r"./SG-Singapore_DATA/OSM_Overpass"
path_data_intermediate = r"./src/data_intermediate"
path_intermediate_buildings = os.path.join(path_data_intermediate, "buildings")
path_intermediate_population = os.path.join(path_data_intermediate, "population")
path_intermediate_workforce = os.path.join(path_data_intermediate, "special_demand", "workforce")
path_intermediate_nonworkforce = os.path.join(path_data_intermediate, "special_demand", "nonworkforce")

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

CLASSIFIED_BUILDINGS = os.path.join(path_intermediate_buildings, "buildings_v2.parquet")
HEALTHCARE_WORKFORCE = os.path.join(path_intermediate_workforce, "healthcare_workforce_v1.parquet")
MILITARY_WORKFORCE = os.path.join(path_intermediate_workforce, "military_workforce_v1.parquet")
GOVERNMENT_WORKFORCE = os.path.join(path_intermediate_workforce, "gov_workforce_v1.parquet")

AGGREGATED_DEMAND_POINTS = os.path.join(path_intermediate_population, "demand_points.parquet")
WORKPLACE_RESIDENCE_OD = os.path.join(path_intermediate_population, "workplace_residence_od.parquet")
RESIDENTIAL_POPULATION_ORIGINS = os.path.join(path_intermediate_population, "residential_population_origins.parquet")
RESIDENTIAL_POPULATION_COVERAGE = os.path.join(path_intermediate_population, "residential_population_coverage.parquet")
AIRPORT_DEMAND = os.path.join(path_intermediate_nonworkforce, "airport_demand.parquet")
