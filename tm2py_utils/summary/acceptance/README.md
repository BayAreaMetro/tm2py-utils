# Acceptance Criteria Module

## Overview

The acceptance module provides functionality to validate Transportation Model 2 (TM2) runs by comparing simulated model outputs against observed real-world data and established acceptance criteria thresholds. This module is essential for model validation and quality assurance in the Metropolitan Transportation Commission's travel demand modeling process.

## Purpose

This module enables modelers to:
- Compare simulated traffic volumes against PeMS and Caltrans counts
- Validate transit boardings against on-board survey data
- Check home-work flow patterns against Census CTPP data
- Verify demographic distributions (e.g., zero-vehicle households)
- Assess station-to-station flows and access mode shares
- Generate visualization-ready outputs for Tableau dashboards

## Usage

Run the acceptance criteria code as follows:
```batch
python acceptance.py model_run_directory
```

This will read the configuration `.toml` files from the model run directory, read various observed and model input files,
and output into `[model_run_directory]\acceptance\output`.

Currently, we've been running it using the virtual environment defined by tm2py, in which the packages listed in [..\requirements.txt](..\requirements.txt) is also installed.

## Components

### Core Classes

#### 1. **Acceptance** (`acceptance.py`)
The main orchestrator class that coordinates comparisons between simulated and observed data.

**Key Features:**
- Generates roadway network comparisons with ODOT error thresholds
- Creates transit network comparisons with Florida DOT boarding thresholds
- Produces aggregate comparisons (county flows, demographics, etc.)
- Outputs GeoJSON files for visualization

**Output Files:**
- `acceptance-roadway-network.geojson`: Link-level traffic volume comparisons
- `acceptance-transit-network.geojson`: Route and segment-level transit comparisons
- `acceptance-other.geojson`: Aggregate metric comparisons

#### 2. **Canonical** (`canonical.py`)
Manages naming conventions and crosswalk mappings between different data sources.

**Key Features:**
- Standardizes agency and station names across data sources
- Maps between different node numbering systems (EMME, standard, model)
- Links PeMS stations to network links
- Connects census geographies to model zones

**Crosswalk Files Required:**
- Agency names mapping
- Station names mapping
- Node ID crosswalks
- PeMS to link mapping
- Census to MAZ mapping

#### 3. **Observed** (`observed.py`)
Handles all observed/real-world data processing.

**Data Sources:**
- **Traffic Counts**: PeMS (2014-2016 average), Caltrans AADT
- **Transit**: On-board surveys, BART OD data
- **Demographics**: Census ACS (zero-vehicle households)
- **Commute Patterns**: CTPP 2012-2016 county flows
- **Bridge Tolls**: FasTrak transaction data

**Key Processing:**
- Applies ODOT volume-based error thresholds to traffic counts
- Applies Florida DOT boarding-based thresholds to transit
- Aggregates multi-year observations to typical values
- Standardizes time periods and geography

#### 4. **Simulated** (`simulated.py`)
Processes tm2py model outputs for comparison.

**Model Outputs Processed:**
- **Roadway**: EMME link shapefiles with volumes by vehicle class
- **Transit**: Boarding files, segment files, station-to-station matrices
- **Demographics**: Household/person files from CTRAMP
- **Skims**: OMX matrices for travel times and transit paths

**Key Processing:**
- Combines general purpose and managed lane volumes
- Aggregates time periods to daily totals
- Calculates volume/capacity ratios for transit
- Allocates trips to technologies based on in-vehicle times

## Data Flow

```
Configuration Files (TOML)
         ↓
    Canonical
    ↙        ↘
Observed    Simulated
    ↘        ↙
   Acceptance
        ↓
  GeoJSON Outputs
```

## Configuration

The module requires three TOML configuration files:

### 1. `canonical.toml`
```toml
[remote_io]
crosswalk_folder_root = "path/to/crosswalks"

[crosswalks]
canonical_agency_names_file = "agency_names.csv"
canonical_station_names_file = "station_names.csv"
standard_to_emme_nodes_file = "node_crosswalk.csv"
# ... other crosswalk files
```

### 2. `observed.toml`
```toml
[remote_io]
obs_folder_root = "path/to/observed/data"

[roadway]
pems_traffic_count_file = "pems_counts.csv"
caltrans_count_file = "caltrans_aadt.csv"
bridge_transactions_file = "bridge_tolls.txt"

[transit]
on_board_survey_file = "transit_survey.csv"
bart_boardings_file = "bart_od.csv"

[census]
ctpp_2012_2016_file = "county_flows.csv"
vehicles_by_block_group_file = "acs_vehicles.csv"
```

### 3. `scenario.toml`
```toml
[scenario]
root_dir = "path/to/model/run"
maz_landuse_file = "landuse/maz_data.csv"
```

## Output Data Structure

### Roadway Network GeoJSON
```json
{
  "features": [{
    "properties": {
      "model_link_id": 12345,
      "emme_a_node_id": 1001,
      "emme_b_node_id": 1002,
      "time_period": "am",
      "observed_flow": 5000,
      "simulated_flow": 4800,
      "odot_flow_category": "4000-6000",
      "odot_maximum_error": 45,
      "percent_error": -4.0
    },
    "geometry": {...}
  }]
}
```

### Transit Network GeoJSON
```json
{
  "features": [{
    "properties": {
      "model_line_id": "511_BART_01_AM",
      "operator": "BART",
      "technology": "Heavy Rail",
      "route_observed_boardings": 15000,
      "route_simulated_boardings": 14500,
      "florida_threshold": 25,
      "am_segment_vc_ratio_total": 0.85
    },
    "geometry": {...}
  }]
}
```

### Other Comparisons GeoJSON
```json
{
  "features": [{
    "properties": {
      "criteria_number": 23,
      "criteria_name": "County-to-county worker flows",
      "dimension_01_name": "residence_county",
      "dimension_01_value": "San Francisco",
      "dimension_02_name": "work_county", 
      "dimension_02_value": "San Mateo",
      "observed_outcome": 25000,
      "simulated_outcome": 24500,
      "acceptance_threshold": "Less than 15 percent RMSE"
    },
    "geometry": {...}
  }]
}
```

## Acceptance Criteria

The module evaluates model performance against various criteria:

### Traffic Volume (ODOT Standards)
- Error thresholds based on volume ranges
- Stricter standards for higher volume facilities
- Separate standards for daily vs. hourly counts

| Daily Volume | Max % RMSE |
|-------------|-----------|
| 0-500       | 200%      |
| 500-1,500   | 100%      |
| 1,500-2,500 | 62%       |
| 2,500-3,500 | 54%       |
| 3,500-4,500 | 48%       |
| 4,500-5,500 | 45%       |
| >30,000     | 24%       |

### Transit Boardings (Florida DOT Standards)
- Error thresholds based on boarding levels
- More tolerance for low-ridership routes

| Boardings   | Max % Error |
|------------|------------|
| 0-1,000    | 150%       |
| 1,000-2,000| 100%       |
| 2,000-5,000| 65%        |
| 5,000-10,000| 35%       |
| >10,000    | 20%        |

### Specific Criteria
- **#6**: District-level transit flows by technology
- **#16**: BART station-to-station flows (<40% RMSE)
- **#17**: BART park-and-ride demand (<20% RMSE for lots >500 vehicles)
- **#19**: Rail station access mode shares
- **#23**: County-to-county work flows (<15% RMSE)
- **#24**: Zero-vehicle household spatial patterns

## Dependencies

- pandas >= 1.3.0
- geopandas >= 0.10.0
- numpy >= 1.21.0
- openmatrix >= 0.3.5
- toml >= 0.10.2

## File Structure

```
tm2py_utils/summary/acceptance/
├── __init__.py           # Module documentation
├── acceptance.py         # Main orchestrator
├── canonical.py          # Naming/crosswalk handler
├── observed.py           # Observed data processor
├── simulated.py          # Model output processor
└── README.md            # This file
```

## Notes

- All geographic outputs use EPSG:4326 (WGS84) for Tableau compatibility
- Time periods are standardized: ea, am, md, pm, ev, daily
- Vehicle classes: da (drive alone), s2/s3 (shared ride), trk (trucks)
- Technologies: Local Bus, Express Bus, Light Rail, Heavy Rail, Commuter Rail, Ferry
- Districts: MTC planning districts 1-34

## Contact

For questions or issues, contact the MTC modeling team or submit an issue to the repository.