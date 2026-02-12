# MAZ Land Use Input Creation Pipeline

This directory contains the pipeline for creating MAZ-level land use inputs for Travel Model Two (TM2). The pipeline integrates **employment**, **enrollment**, and **parking** data into a single MAZ-level file.

---

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Data Sources](#data-sources)
4. [Methods](#methods)
5. [Usage](#usage)

---

## Overview

The land use pipeline creates MAZ-level attributes from multiple data sources:

- **Employment**: Business locations → 27-way steelhead employment categories
- **Enrollment**: School/college locations → enrollment by grade level and institution type  
- **Parking**: Published meter data + web scraping + capacity allocation + cost estimation



---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  MAZ Land Use Input Pipeline                        │
│                   (land_use_pipeline.py)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
        ┌───────▼────────┐              ┌──────▼──────┐
        │  Employment    │              │ Enrollment  │
        │  (job_counts)  │              │ (enrollment_│
        │                │              │  counts)    │
        └───────┬────────┘              └──────┬──────┘
                │                              │
                │  Spatial Join to MAZ         │  Spatial Join to MAZ
                │  (firms → MAZ)               │  (schools → MAZ)
                │                              │
                ▼                              ▼
        ┌───────────────┐              ┌───────────────┐
        │ jobs_maz.gpkg │              │enrollment_maz │
        │ (interim)     │              │ .gpkg(interim)│
        └───────────────┘              └───────────────┘
                │                              │
                └───────────┬──────────────────┘
                            │
                    ┌───────▼────────┐
                    │ Merge with MAZ │
                    │  + Synth Pop   │
                    └───────┬────────┘
                            │
                ┌───────────▼────────────┐
                │   Parking Pipeline     │
                │ ┌────────────────────┐ │
                │ │ 1. Scraped costs   │ │ ← SpotHero (daily/monthly)
                │ │ 2. Published costs │ │ ← SF/Oak/SJ meters (hourly)
                │ │ 3. Capacity        │ │ ← Block group allocation
                │ │ 4. Parking areas   │ │ ← Downtowns, downtown periphery, etc
                │ │ 5. Cost estimation │ │ ← Estimate unobserved costs
                │ └────────────────────┘ │
                └───────────┬────────────┘
                            │
                    ┌───────▼────────┐
                    │  Final Merge   │
                    │  & Write CSV   │
                    └───────┬────────┘
                            │
                            ▼
                  ┌─────────────────────────┐
                  │ maz_landuse_            │
                  │ {MAZ Version}_2023.csv  │
                  │ (FINAL OUTPUT)          │
                  └─────────────────────────┘
```

---

## Data Sources

### Employment Data

| Component | Source | Vintage | Format | Location |
|-----------|--------|---------|--------|----------|
| **Business locations** | Esri Business Analyst | 2023 | GDB | `M:\Data\BusinessData\Businesses_2023.gdb` |
| **NAICS crosswalk** | Manual mapping | 2022 | XLSX | `M:\Crosswalks\NAICS\2022_NAICS_Descriptions.xlsx` |


---

### Enrollment Data

| Component | Source | Vintage | Format | Location | URL | Download Date | Notes |
|-----------|--------|---------|--------|----------|-----|---------------|-------|
| **Public schools** | CA Dept of Education (CDE) | 2024-25 | GPKG | `{BOX}/enrollment/SchoolSites2425.gpkg` | [CDE Data Portal](https://data-cdegis.opendata.arcgis.com/datasets/CDEGIS::california-public-schools-2024-25/about) | 11/21/2025 | |
| **Private schools** | CA Dept of Education (CDE) | 2023-24 | GPKG | `{BOX}/enrollment/cprs_2324.gpkg` | [CDE Data Portal](https://data-cdegis.opendata.arcgis.com/datasets/CDEGIS::california-private-schools-2023-24-2/about) | 11/21/2025 | |
| **College locations** | NCES via Esri Living Atlas | 2023-24 | SHP | `{BOX}/enrollment/bayarea_postsec_2324.shp` | [Living Atlas](https://www.arcgis.com/home/item.html?id=a15e8731a17a46aabc452ea607f172c0) | - | Accessed from Living Atlas in Pro, filtered to Bay Area, and saved here |
| **College enrollment** | IPEDS | 2023-24 | CSV | `{BOX}/enrollment/postsec_enroll_2324.csv` | [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/InstitutionByGroup.aspx?sid=2e6e42bc-97bb-4007-a9f8-73d7e6dc15f6&rtid=1) | - | Selected and downloaded schools in CA with "Total 12-month unduplicated headcount" variable (UNDUP DRVEF122024 field) |



---

### Parking Data

#### Scraped Costs (daily/monthly)
| Component | Source | Vintage | Format | Location |
|-----------|--------|---------|--------|----------|
| **Raw scrape** | SpotHero website | 2026-01 | CSV | `{INTERIM}/parking_scrape_spots.csv` |
| **Geocoded** | Nominatim | 2026-01 | GPKG | `{INTERIM}/parking_scrape_location_cost.gpkg` |



#### Published Meter Costs (hourly)
| Component | Source | Vintage | Format | Location | URL |
|-----------|--------|---------|--------|----------|-----|
| **Oakland meters** | City of Oakland open data | 2026-01 | GeoJSON | `{PARKING_RAW}/City_of_Oakland_Parking_Meters_20260107.geojson` | [Oakland Data Portal](https://www.oaklandca.gov/Public-Safety-Streets/Transportation-Projects-Reports/Parking-and-Mobility-Related-Maps-and-Data) |
| **San Jose meters** | City of San Jose open data | 2026 | GeoJSON | `{PARKING_RAW}/Parking_Meters.geojson` | [San Jose Data Portal](https://data.sanjoseca.gov/dataset/parking-meters) |
| **San Francisco meters** | SF open data | 2026-02 | GeoJSON | `{PARKING_RAW}/Parking_Meters_20260203.geojson` | [SF Data Portal](https://data.sfgov.org/Transportation/Map-of-Parking-Meters/fqfu-vcqd) |
| **SF variable rates** | SFMTA | 2026-01 | CSV | `{PARKING_RAW}/January 2026 Parking Meter Rate Change Data.csv` | [SFMTA Meter Rate Adjustments](https://www.sfmta.com/notices/citywide-meter-rate-adjustments) |
| **SF parking mgmt districts** | SF open data | 2026-02 | GeoJSON | `{PARKING_RAW}/Parking_Management_Districts_20260203.geojson` | [SF Data Portal](https://data.sfgov.org/Transportation/Map-of-Parking-Management-Districts/fqfe-qhy8) |



#### Parking Capacity
| Component | Source | Vintage | Format | Location | URL |
|-----------|--------|---------|--------|----------|-----|
| **Block group capacity** | ACS (via MTC dataset 2123) | 2019 | SHP | `{PARKING_RAW}/2123-Dataset/parking_density_Employee_Capita/parking_density_Employee_Capita.shp` | [SPUR Bay Area Parking Census](https://www.spur.org/publications/spur-report/2022-02-28/bay-area-parking-census) |

**Citation:**
> Mikhail Chester, Alysha Helmrich, and Rui Li. "San Francisco Bay Area Parking Census [Dataset]" Mineta Transportation Institute Publications (2022). doi: https://doi.org/10.31979/mti.2022.2123.ds

---

## Methods

### Employment Processing (`job_counts.py`)

**High-Level Workflow**:
1. **Load** business locations from Esri Business Analyst GDB (Bay Area, 2023)
2. **Extract** 6-digit NAICS codes from business records
3. **Crosswalk** NAICS codes → Steelhead 27-way employment categories  
4. **Spatial Join** business points to MAZ polygons
5. **Aggregate** employees (`EMPNUM`) by MAZ and steelhead category
6. **Validate** conservation: total jobs in output = total jobs in input
7. **Write** to interim cache as `jobs_maz_v{VERSION}_{VINTAGE}.gpkg`

**Output Schema**: `[MAZ_NODE, TAZ_NODE, ag, min, util, const, ..., emp_total]` (27 employment columns + total)

---

### Enrollment Processing (`enrollment_counts.py`)

**High-Level Workflow**:

#### Public Schools
1. **Load** CA Dept of Education school sites (2024-25)
2. **Filter** to active schools in Bay Area counties
3. **Derive** enrollment variables:
   - Sum grades TK-8 → `publicEnrollGradeKto8`
   - Sum grades 9-12 → `publicEnrollGrade9to12`
   - Separate adult education → `AdultSchEnrl`

#### Private Schools
1. **Load** CA CPRS private school data (2023-24)
2. **Filter** to Bay Area counties
3. **Derive** enrollment variables:
   - Sum grades K-8 → `privateEnrollGradeKto8`
   - Sum grades 9-12 → `privateEnrollGrade9to12`

#### Colleges
1. **Load** IPEDS college locations + enrollment CSV (2023-24)
2. **Merge** location and enrollment by `UNITID`
3. **Classify** college types:
   - `Institutional category` = 1,2 → `collegeEnroll` (baccalaureate+)
   - `Institutional category` = 3,4 AND public → `comm_coll_enroll`
   - Other → `otherCollegeEnroll` (private 2-year, certificates)

#### Spatial Join & Aggregation
1. **Spatial Join** all schools/colleges to MAZ
2. **Aggregate** enrollment by MAZ
3. **Compute** combined totals:
   - `EnrollGradeKto8` = public + private K-8
   - `EnrollGrade9to12` = public + private 9-12
4. **Write** to interim cache as `enrollment_maz_v{VERSION}_{VINTAGE}.gpkg`

**Output Schema**: `[MAZ_NODE, TAZ_NODE, publicEnrollGradeKto8, privateEnrollGradeKto8, EnrollGradeKto8, publicEnrollGrade9to12, privateEnrollGrade9to12, EnrollGrade9to12, comm_coll_enroll, collegeEnroll, otherCollegeEnroll, AdultSchEnrl]`

---

### Parking Processing

#### 1. Scraped Costs (`parking_scrape.py` + `parking_geocode.py`)
**Method**: Web scraping + geocoding
- **Tool**: Selenium WebDriver to scrape SpotHero parking facility search pages
- **Coverage**: Daily and monthly parking in SF, Oakland, San Jose, Berkeley, Palo Alto, Walnut Creek, Millbrae, Concord
- **Geocoding**: Nominatim API to convert addresses → lat/lon
- **Output**: GeoPackage with point geometries, `price_value`, `rate_type` (daily/monthly)
- **Runtime**: ~1-2 hours (run separately, not part of main pipeline)
- **Storage**: `{INTERIM}/parking_scrape_location_cost.gpkg`

#### 2. Published Costs (`parking_published.py`)
**Method**: Direct import of city-published meter data
- **Oakland/San Jose**: Load meter point shapefiles, extract hourly rates
- **San Francisco**: Load parking management district polygons + rate CSV, join on district ID, calculate average hourly rate by district
- **Spatial Join**: Meters/districts → MAZ
- **Output**: `hparkcost` (hourly parking cost in dollars)

#### 3. Capacity Allocation (`parking_capacity.py`)
**Method**: Weighted spatial overlay from block groups to MAZ
- **Load** block group parking capacity shapefile (on-street, off-street stalls)
- **Spatial Overlay**: Intersect MAZ polygons × block group polygons
- **Allocation Weights**:
  - **Off-street (`off_nres`)**: Employment-weighted (uses MAZ employment from `job_counts`)
  - **On-street (`on_all`)**: Area-weighted only
- **Validation**: Check conservation (total capacity pre/post allocation should match within 0.1%)
- **Output**: `parking_capacity.gpkg` → `[MAZ_NODE, TAZ_NODE, on_all, off_nres, emp_total]`

#### 4. Parking Area Classification (`parking_area.py`)
**Method**: Statistical identification of downtown cores and peripheries using Local Moran's I
  1. Calculate Local Moran's I statistic for downtown employment density
  2. Identify statistically significant High-High employment clusters (p ≤ 0.05)
  3. Assign largest contiguous cluster as downtown core (`parkarea = 1`)
  4. Assign 1/4-mile buffer around downtown as periphery (`parkarea = 2`)
- **Output**: Spatial downtown classification (Stage 1: parkarea 1, 2, and temporary 0)
- **Note**: `parkarea = 3` and `parkarea = 4` are assigned after cost estimation.


#### 5. Cost Estimation (`parking_estimation.py`)
**Method**: Hybrid ML + threshold-based estimation

##### Hourly Parking (`hparkcost`)
- **Approach**: Multi-model classification comparison (paid vs free)
- **Training Data**: SF, Oakland, San Jose MAZs with observed meter costs
- **Features**:
  - `commercial_emp_den` = (retail + prof + fire + info + services + eat) / ACRES
  - `downtown_emp_den` = (prof + fire + info + business services) / ACRES
  - `pop_den` = synthesized population / ACRES
- **Model Selection**: Compares Logistic Regression, Random Forest, Gradient Boosting, and Support Vector Machine via leave-one-city-out cross-validation; selects model with highest mean F1 score across all held-out cities (balances precision and recall for paid parking identification)
- **Prediction**:
  - Eligible: MAZs with `on_all > 0` (on-street capacity) AND not in cities with observed cost data
  - Assignment: If predicted paid → `hparkcost = $2.00/hr` (flat rate)
- **Validation**: Leave-one-city-out cross-validation with performance metrics

##### Daily/Monthly Parking (`dparkcost`, `mparkcost`)
- **Approach**: County-level density percentile thresholds
- **Rationale**: Not enough observed data for binary classifier
- **Method**:
  1. Calculate `commercial_emp_den` for all MAZs in county
  2. Determine percentile thresholds (default: 95th for daily, 99th for monthly)
  3. Assign costs to MAZs above threshold:
     - Uses assumed suburban discount factor (0.65) to reflect lower costs in non-core cities
     - Daily: 65% of observed median daily cost from SpotHero scrape
     - Monthly: 65% of observed median monthly cost from SpotHero scrape
- **Eligibility**: Only MAZs with `off_nres > 0` (off-street capacity) and without observed daily/monthly parking costs

##### Final `parkarea` Classification (Stage 2)
After cost estimation, finalize parkarea codes:
- **`parkarea = 1`**: Downtown core (Local Moran's I cluster)
- **`parkarea = 2`**: Within 1/4 mile of downtown core
- **`parkarea = 3`**: Paid parking (observed or predicted costs, not `parkarea` 1 or 2)
- **`parkarea = 4`**: Free parking / no parking cost

**Output Schema**: `[MAZ_NODE, TAZ_NODE, hparkcost, dparkcost, mparkcost, hstallsoth, hstallssam, dstallsoth, dstallssam,	mstallsoth,	mstallssam, parkarea]`

---

## Usage

### Full Pipeline

```bash
# Run complete pipeline with defaults (uses cache if available, validates parking, compares models)
cd tm2py_utils/inputs/land_use
python land_use_pipeline.py

# Run from scratch without caching
python land_use_pipeline.py --no-cache
```


### Standalone Module Execution

Each module can be run independently for testing:

```bash
# Employment only
cd tm2py_utils/inputs/land_use
python job_counts.py --write
```
```bash
# ===== Run separately BEFORE pipeline (long-running web operations) =====
# Web scraping (~1-2 hours)
python parking_scrape.py

# Geocode scraped parking addresses (~30 min)
python parking_geocode.py
```

---
