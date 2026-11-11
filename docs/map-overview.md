# Singapore Map Overview

Modelled demand

- Working: 3013150
  - The actual allocated employment population is different from the original number due to rounding steps during the distribution process.
  - This includes pre-distributed special workforce demand: government, military, hospitals
- Non-working:
  - Airports: 63400
  - Higher Education (Unversities, Technical Colleges): 220450

## Pipeline Overview

Actual modelled core employment data is

## Data

### Core Data

#### Working Population

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

150,000 daily Malaysia -> Singapore commuters:

- Surface-level sources (Wikipedia, news articles) report 300,000 to 450,000 crossings, at one of two land-border crossings, or the sum of both
- This however counts crossings rather than individual commuters.
  - [2017, Straits Times](https://www.straitstimes.com/world/malaysians-returning-to-singapore-for-work-as-border-controls-ease) reported ~100,000 Causeway-crossing commuters/day.
  - A key 2017 ISEAS source explicitly mentions 120,000 Malaysian workers commuting daily, against 400,000 daily average crossings [5].
  - The most recent 2025 ICA Annual Report recorded an average of 510,000 daily land border crossings (245 million checkpoint crossings, 76% via land checkpoints) [6]. Combining this updated figure with the 2017 estimate's ratio produces a current figure of 150,000 daily commuters.
- As these are non-resident workers that don't live in Singapore, and I decided to **explicitly not model cross-border demand** (for now), they are subtracted from the total.

Application to population distribution:

- A final total of 2379300 resident workers, is derived from the dataset for employed residents by planning area. 81,200 who work-from-home are subtracted.
- Geospatial employed resident statistics are then extrapolated up to include the added non-residents.

Sources:

1. <https://stats.mom.gov.sg/Pages/employment-Summary-Table.aspx>
2. <https://www.mom.gov.sg/foreign-workforce-numbers>
3. [data.gov.sg | Share Of Non-Resident Population By Pass Types](https://data.gov.sg/datasets/d_94fd56bdb981f0f966cb487d8247bf1a/view)
4. [twc2.org.sg | Foreign workforce numbers, 2022](https://twc2.org.sg/2023/06/05/foreign-workforce-numbers-2022/)
5. [ISEAS The 2017 Johor Survey : Selected Findings](https://www.iseas.edu.sg/wp-content/uploads/pdfs/TRS20_17.pdf)
6. [ICA Annual Statistics Report 2025](https://www.ica.gov.sg/news-and-publications/statistics)

### Special Demand (workforce)

Special workforce demand are large, instutitional, concentrations of workplaces that are modelled separately from general employment distribution. These seek to model these specific workplace concentrations more accurately than could be done using normal distribution methods.

For some of them, exact data can be obtained publicly; but for others, estimations have to be done, just that the types of estimations are specific to the types of demand at play, and start from much more granular workplace counts.

#### Government

Government ministry workplace counts are derived from the number of employees on each ministry's payroll (from [Singapore Budget Revenue and Expenditure Estimates, FY2025/26](https://www.singaporebudget.gov.sg/revenue-and-expenditure)).

Ministries not included are:

- Those with <50 payroll employees
- [Statutory boards](https://en.wikipedia.org/wiki/Statutory_boards_of_the_Government_of_Singapore) - which are another key source of concentrated government employment but do not have good public data
- Ministries without a centralised location:
  - Ministry of Education - workforce breakdown is especially muddied with the inclusion of teaching staff
  - Prime Minister's Office

#### Hospitals

> Only hospitals; excludes polyclinics and private clinics

This is modelled for Singapore's 20 acute hospitals, 1 psychiatric hospital, and 10 community hospitals.

While official public data shows the size of the the [overall healthcare workforce](https://www.moh.gov.sg/others/resources-and-statistics/health-manpower/), these figures are not used as, data for clinics and especially other care facilities is very incomplete, so the estimations given were grossly inaccurate.

Employment figures are hence used for the hospitals/healthcare organisations that report them: All SingHealth hospitals, NHG total, NUH, St Luke's hospital. A combination of bed count (much more consistently reported) and hospital building floorspace is then used to estimate employment counts for all remaining hospitals using linear regression. IMH is set separately, estimated from a [source from 2015](<https://web.archive.org/web/20260121131415/https://www.moh.gov.sg/newsroom/institute-of-mental-health-(imh)/>), since it has a large number of beds relative to staff.

The individual sources used are in the [Wikipedia List of Hospitals in Singapore](https://en.wikipedia.org/wiki/List_of_hospitals_in_Singapore), I updated them while doing research for making this map.

Hospital visitation demand is not currently modelled.

#### Military

The military workforce is estimated through a very simple proxy. It uses the [Wikipedia List of Singapore Armed Forces Bases](https://en.wikipedia.org/wiki/List_of_Singapore_Armed_Forces_bases).

The number of military units each base has are then distribution weights. Each of the SAF's branches (Army, Navy, Air Force) then have their personnel numbers (active + 1/6 reserve) distributed to bases based on those weights.

### Special Demand (non-workforce)

#### Airports

#### Education (Higher Education)

The primary data source: [data.gov.sg | Enrolment by Institutions (latest 2024)](https://data.gov.sg/datasets/d_ec8a16e11a050f11880fb6d4a0e6f93f/view?dataExplorerSort={%22year%22:%22DESC%22})
