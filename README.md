# Subway Builder Singapore Map

Modelled demand:

- **Working: 3,013,150**
  - The actual allocated employment population is different from the original number due to rounding steps during the distribution process.
  - This includes pre-distributed _special workforce demand_: government, military, hospitals
- **Non-working: 283,850**
  - Airports: 63,400
  - Higher Education (Universities, Technical Colleges): 220,450
- **Total: 3,297,000**

## Methodology

_Note: there are two concepts of residence that are discussed. Legal residence concerns only total population numbers and is discussed in its own section. Otherwise, residents/residence refers to where a person lives._

The relevant statistics are available at different administrative units:

- **Planning region**: there are 5 regions in Singapore. Median size: 136.41 km²
- **Planning area**: there are 55 planning areas in Singapore. Planning areas have about 50,000 to 250,000 residents. Median size: 10.60 km²
- **Subzone**: there are 332 subzones in Singapore. The average subzone has around 10,000 to 30,000 residents, but the largest has >100,000. Median size: 1.19 km²

The map's population data is grounded on 3 main datasets, all from the 2025 General Household Survey:

- Resident population by **subzone** of residence.
- Employed residents by **planning area** of residence.
- Employed workers by **planning area of workplace**, broken out by **planning region of residence**.

Population statistics are extrapolated to final working-population totals (including non-residents and excluding invalid resident employment). Employed residence counts are pushed down to the **subzone** level by splitting a planning area's employed residents proportionally to subzones based the subzone's number of residents.

Buildings are obtained from Overture Maps, with building types coarsely classified based on OSM building types (via Overture) and [zoning](https://eservice.ura.gov.sg/maps/?service=MP). Floorspace is estimated using a mix of building footprint + height, as well as max allowed floorspace based on zoning to serve as an upper bound. Residence and workplace statistics are then distributed down to these buildings, weighted by estimated floorspace and a set of manual coefficients. Special workforce demand is first injected before per-buliding distribution, and workforce counts subtracted from subzonal totals to prevent double counting.

Per-building demand points are then aggregated with a minimum 200 m spacing. Aggregated demand points with less than 50 people are merged into nearby points.

Commute flows are assigned using a gravity model constrained by the (workplace planning area, residence planning region) O/D matrix.

Special non-workforce demand is then finally added into workforce demand data. Non-university/airport points are merged with existing points if necessary.

### Building Processing

TBC

### Population Distribution

TBC

### Map Creation

The Map is created using a [personal fork](https://github.com/Zeepheru/subwaybuilder-depot) of the Subway Builder map creation tool [Depot](https://github.com/Subway-Builder-Modded/depot). A few custom visual tweaks are made: removing canals/drains, and resolving water/park overlaps with university/retail zones.

Map buildings are notionally from Overture Maps, but ML building quality in Singapore is kinda meh and crucially, picks up way too many false positives, while OSM coverage in Singapore is good enough that the vast majority of rendered buildings after filtering end up being from OSM anyway. MRT stations and depots are all removed.

## Data

### Core Population Data

2025 General Household Survey

- Resident population by **subzone** of residence: [Resident Population by Planning Area/Subzone of Residence, Age Group and Floor Area of Residence (General Household Survey 2025)](https://tablebuilder.singstat.gov.sg/table/CT/C020126)
- Employed residents by **planning area** of residence: [Residents by Planning Area of Residence (General Household Survey 2025)](https://tablebuilder.singstat.gov.sg/table/CT/C020138)
- Employed workers by **planning area of workplace**, broken out by **planning region of residence**: [Employed Residents Aged 15 Years and Over](https://tablebuilder.singstat.gov.sg/table/CT/C020155)

<details>
<summary><strong>Calculation of 3,013,150 Working Population</strong></summary>

All geographic and census statistics concern only **resident** workers (citzens and permanent). Singapore relies heavily on non-resident labour, with about 1.6 non-resident workers to 2.5 resident workers [1].

871,000 non-resident workers:

- Start with the total non-resident population of 1.91 million (2025), which includes working and non-working non-residents [2]
- Non-resident pass types [3]:
  - Employment Pass 11%, S-Pass 9% - general employment passes, _all included_
  - Work Permit 44%
    - Non-CMP (Construction, Marine (shipyard), Process) 21%
    - CMP 23%
      - Construction-sector migrant workers typically stay on dormitories near construction sites and/or are ferried by contractor transport, and so are _not included_ the home-workplace commuter pool. TWC (a local NGO) estimate the share of CMP being construction workers to be 79% [4], though this does vary wildly based on current construction projects.
  - Migrant domestic workers 16% - _not included_
  - Remainder: long term visit pass, dependent's pass, student's pass - all assumed non-working, _not included_
- All in all this leaves 871,000 relevant non-resident workers that also have to be distributed

150,000 daily Malaysia → Singapore commuters:

- Surface-level sources (Wikipedia, news articles) report 300,000 to 450,000 crossings, at the larger of the two land-border crossings, or the sum of both
- This however counts crossings rather than individual commuters.
  - [2017, Straits Times](https://www.straitstimes.com/world/malaysians-returning-to-singapore-for-work-as-border-controls-ease) reported ~100,000 Causeway-crossing commuters/day.
  - A key 2017 ISEAS source explicitly mentions an estimate of 120,000 Malaysian workers commuting daily, against 400,000 daily average crossings [5].
  - The most recent 2025 ICA Annual Report recorded an average of 510,000 daily land border crossings (245 million checkpoint crossings, 76% via land checkpoints) [6]. Combining this updated figure with the 2017 estimate's ratio produces a current figure of 150,000 daily commuters.
- As these are non-resident workers that don't live in Singapore, and I decided to **explicitly not model cross-border demand** (for now), they are subtracted from the total.

A final total of 2379300 resident workers, is derived from the dataset for employed residents by planning area. 81,200 who work-from-home are subtracted. Adding 871,000 non-resident workers and subtracting 150,000 daily Malaysia → Singapore commuters, and then after produces a final total of 3,019,060. But after some rounding during the aggregation and merging processes, the **final modelled workforce population is 3,013,150**.

Geospatial employed resident statistics are then extrapolated up to include the added non-residents.

Sources:

1. <https://stats.mom.gov.sg/Pages/employment-Summary-Table.aspx>
2. <https://www.mom.gov.sg/foreign-workforce-numbers>
3. [data.gov.sg | Share Of Non-Resident Population By Pass Types](https://data.gov.sg/datasets/d_94fd56bdb981f0f966cb487d8247bf1a/view)
4. [twc2.org.sg | Foreign workforce numbers, 2022](https://twc2.org.sg/2023/06/05/foreign-workforce-numbers-2022/)
5. [ISEAS The 2017 Johor Survey : Selected Findings](https://www.iseas.edu.sg/wp-content/uploads/pdfs/TRS20_17.pdf)
6. [ICA Annual Statistics Report 2025](https://www.ica.gov.sg/news-and-publications/statistics)

</details>

### Special Demand (workforce)

Special workforce demand are large, instutitional, concentrations of workplaces that are modelled separately from general employment distribution. These seek to model these specific workplace concentrations more accurately than could be done using the main distribution methods. _It's easier to just ignore hospitals rather than try and come up with yet another heuristic distribution coefficient._

For some of them, exact data can be obtained publicly; but for others, estimations have to be done, just that the types of estimations are specific to the types of demand at play, and start from much more granular workplace totals.

#### Government

Government ministry workplace counts are taken from the number of employees on each ministry's payroll (from [Singapore Budget Revenue and Expenditure Estimates, FY2025/26](https://www.singaporebudget.gov.sg/revenue-and-expenditure)).

Not all government ministries are included. Those _not included_ are:

- Those with <50 payroll employees.
- [Statutory boards](https://en.wikipedia.org/wiki/Statutory_boards_of_the_Government_of_Singapore), which are another key source of concentrated government employment but do not have reliable public data.
- Ministries without a centralised location:
  - Ministry of Education - workforce breakdown is especially muddied with the inclusion of teaching staff.
  - Prime Minister's Office

#### Hospitals

This is modelled for Singapore's 20 acute hospitals, 1 psychiatric hospital, and 10 community hospitals. It excludes polyclinics, private clinics, and other care facilities.

While official public data shows the size of the the [overall healthcare workforce](https://www.moh.gov.sg/others/resources-and-statistics/health-manpower/), these figures are not used as, data for clinics and especially other care facilities is very incomplete, so the estimations given were grossly inaccurate.

Employment figures are hence used for the hospitals/healthcare organisations that report them: All SingHealth hospitals, NHG total, NUH, St Luke's hospital. A combination of bed count (much more consistently reported) and hospital building floorspace (Overture) is then used to predict employment counts for all remaining hospitals using linear regression. IMH's staff numbers are set separately, estimated from a [source from 2015](<https://web.archive.org/web/20260121131415/https://www.moh.gov.sg/newsroom/institute-of-mental-health-(imh)/>), since it has a large number of beds relative to staff and would receive a disproportionately high workforce count.

The individual sources used are in the [Wikipedia List of Hospitals in Singapore](https://en.wikipedia.org/wiki/List_of_hospitals_in_Singapore), I updated them while doing research for making this map.

Hospital **visitation demand** is **not currently modelled**.

#### Military

The military workforce is estimated through a very simple proxy, using the [Wikipedia List of Singapore Armed Forces Bases](https://en.wikipedia.org/wiki/List_of_Singapore_Armed_Forces_bases). The number of military units on each base are the base's distribution weights. Each of the SAF's branches (Army, Navy, Air Force) then have their personnel numbers (active + 1/6 reserve) distributed to bases based on those weights.

### Special Demand (non-workforce)

Non-working demand that is injected after the main population distribution is completed.

#### Hotels

Added on as additional residential demand

Currently only connects to airports, will connect to tourist attractions in the future.

#### Airports

#### Education (Higher Education)

The primary data source: [data.gov.sg | Enrolment by Institutions (latest 2024)](https://data.gov.sg/datasets/d_ec8a16e11a050f11880fb6d4a0e6f93f/view?dataExplorerSort={%22year%22:%22DESC%22})

## Development

See `workflow.md`

## Future Roadmap

Minor improvements:

- Add commute driving paths.

After end-Nov 2026 Overture Maps release:

- Update to building 3D models (increasing coverage HDB apartments with accurate heights to near-complete).
- Addition of on-campus student housing residential points for NUS, NTU, SUTD.

New special demand:

- A limited set of major tourist attractions and museums.
- Hospital visitation. Inpatient/outpatient statistics are available at a national level and for some hospitals/hospital groups, hospital beds can be used as distribution weight.
- (Maybe) Seaports (the two cruise terminals and two ferry terminals). Data is very poor, but I could try estimating.

Far future:

- New version of map that includes cross-border demand with Southern Johor in Malaysia. Heavily dependent on Malaysian data quality, though personally I'm not too optimistic.
