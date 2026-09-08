# [data.gov.sg](data.gov.sg) Data Sources

## Base

MAIN:

[Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON)](https://data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view)

MP2025PlanningAreaBoundary.geojson: [Master Plan 2025 Planning Area Boundary (No Sea)](https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view)

MP2025RegionBoundary.geojson: [Master Plan 2025 Region Boundary (No Sea)](https://data.gov.sg/datasets/d_4ce0038f7ac689652350bb91b7fb92ed/view)

MP2025LandUse.geojson: [Master Plan 2025 Land Use Layer](https://data.gov.sg/datasets/d_a8c3546b26712e35021f3a681d0353ae/view)

Older:

MP2019LandUse.geojson: [Master Plan 2019 Land Use layer](https://data.gov.sg/datasets/d_90d86daa5bfaa371668b84fa5f01424f/view)


## Resident

### C020126.csv

[Resident Population by Planning Area/Subzone of Residence, Age Group and Floor Area of Residence (General Household Survey 2025)](https://tablebuilder.singstat.gov.sg/table/CT/C020126)

2025 General Household Survey

The data format is pretty bad, so cleanup and careful parsing is required

Planning Area rows have "- Total"

### ...

## Employment

> Note the `No Transport Required` mode of transport! (Other Modes as well, prolly encompasses cycling) - could be useful for that gravity model

2020CoP_WorkplacePlanningArea_Industry.csv: [Employed Residents Aged 15 Years and Over by Planning Area of Workplace and Travelling Time to Work (Census of Population 2020)](https://data.gov.sg/datasets/d_8ec1d0f5a86e5492f98e8598d6d258d1/view)

2020CoP_WorkplacePlanningArea_Industry.csv: [Employed Residents Aged 15 Years and Over by Planning Area of Workplace and Industry (Census of Population 2020)](https://data.gov.sg/datasets/d_66ddd6e816c3ae99502a325bd04d480f/view)

2020CoP_WorkplacePlanningArea_ModeOfTransport.csv: [Employed Residents Aged 15 Years and Over by Planning Area of Workplace and Usual Mode of Transport to Work (Census of Population 2020)](https://data.gov.sg/datasets/d_f6ddbf6228d561454e27dd158846c688/view)

> Industry: "others" -  Includes Agriculture, Fishing, Quarrying, Utilities and Sewerage & Waste Management.

### 2025 GHS Data

(From Tablebuilder so less clean)

[Employed Residents Aged 15 Years and Over](https://tablebuilder.singstat.gov.sg/table/CT/C020155)

* Planning Area of Workplace - Planning Region of Residence - Usual Mode of Transport
* No other ones have point-point OD

## Other

TouristAttractions.geojson: [Tourist Attractions](https://data.gov.sg/datasets/d_0f2f47515425404e6c9d2a040dd87354/view)

### Schools/Students by Planning Region, Level/Type

2025 latest annual figure

schools.csv: [Number of Schools By Level, Type, And Planning Region](https://tablebuilder.singstat.gov.sg/table/TS/M850791)

students.csv: [Number Of Students By School Level, Planning Region And Sex](https://tablebuilder.singstat.gov.sg/table/TS/M850801)