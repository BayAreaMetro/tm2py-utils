# Configuration Reference

Complete reference for `validation_config.yaml` and related configuration files.

## validation_config.yaml

Main configuration file for summary generation and dashboard deployment.

### Top-Level Settings

```yaml
# Summary generation filter: "all", "core", or "validation"
generate_summaries: "all"

# Base directories for input data
input_directories:
  - path: "/path/to/model/run/outputs"
    label: "2023 TM2.2 v05"
  - path: "/path/to/another/run"
    label: "2015 TM2.2 Sprint 04"

# Output directory for generated summaries
output_directory: "outputs"

# Observed data for validation
observed_data_sources:
  - name: "ACS 2019"
    directory: "/path/to/observed/data"
    files:
      auto_ownership: "acs_auto_ownership.csv"
      household_size: "acs_household_size.csv"

# Custom summary definitions
custom_summaries:
  - name: "my_summary"
    # ... (see Custom Summaries section)
```

### Input Directories

Each entry requires:

```yaml
input_directories:
  - path: "/absolute/path/to/outputs"  # Absolute path to CTRAMP outputs
    label: "Dataset Name"               # Display name in charts
```

**Expected files in directory:**
- `householdData_1.csv`
- `personData_1.csv`
- `indivTourData_1.csv`
- `indivTripData_1.csv`
- `wsLocResults.csv`

### Custom Summaries

#### Required Fields

```yaml
custom_summaries:
  - name: "summary_identifier"          # Unique name (becomes filename)
    summary_type: "core"                # "core" or "validation"
    description: "What this summarizes" # Human-readable description
    data_source: "individual_trips"     # Data source (see below)
```

#### Data Sources

Available options:

- `households` - Household-level data
- `persons` - Person-level data
- `individual_tours` - Tour-level data
- `individual_trips` - Trip-level data
- `workplace_school` - Work/school location choice
- `synthetic_population` - PopulationSim output

#### Basic Grouping

**Single column:**
```yaml
group_by: "trip_mode"
count_name: "trips"  # Column name for counts
```

**Multiple columns:**
```yaml
group_by: ["income_category_bin", "trip_mode"]
count_name: "trips"
```

#### Aggregations

**Simple count:**
```yaml
count_name: "trips"
```

**Multiple aggregations:**
```yaml
aggregations:
  trips: "count"                                    # Count rows
  avg_distance:                                     # Mean
    column: "trip_distance_miles"
    agg: "mean"
  total_time:                                       # Sum
    column: "trip_time_minutes"
    agg: "sum"
  max_distance:                                     # Max
    column: "trip_distance_miles"
    agg: "max"
  min_distance:                                     # Min
    column: "trip_distance_miles"
    agg: "min"
```

Available aggregation functions:
- `count` - Count rows
- `mean` - Average
- `sum` - Total
- `max` - Maximum value
- `min` - Minimum value
- `median` - Median value
- `std` - Standard deviation

#### Share Calculations

Calculate percentages within groups:

```yaml
group_by: ["tour_purpose", "tour_mode"]
share_within: "tour_purpose"  # Each purpose sums to 100%
```

Without `share_within`, shares calculated across all rows.

#### Weighting

Apply sample expansion factors:

```yaml
weight_field: "sample_rate"  # Column containing weights
```

#### Binning

Discretize continuous variables:

```yaml
group_by: ["income_bin", "auto_ownership"]
bins:
  income:
    breaks: [0, 30000, 60000, 100000, 150000, 1000000000]
    labels: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
  
  distance:
    breaks: [0, 5, 10, 20, 50, 1000]
    labels: ['<5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
```

**Note:** Column name in `group_by` must match bin name (e.g., `income_bin` references `income` bin definition).

#### Filtering

Apply filters before aggregation:

```yaml
filters:
  tour_purpose: ["Work", "School"]    # Include only these values
  trip_distance_miles: {">": 0}       # Distance greater than 0
```

**Available operators:**
- `["value1", "value2"]` - Equals any of these
- `{">": value}` - Greater than
- `{"<": value}` - Less than
- `{">=": value}` - Greater than or equal
- `{"<=": value}` - Less than or equal

#### Observed Data

Compare to validation data:

```yaml
observed_data: "ACS 2019"      # Name from observed_data_sources
observed_file: "auto_ownership" # File key from observed_data_sources
```

Observed data merged into output with `dataset` = observed data name.

### Complete Summary Example

```yaml
custom_summaries:
  - name: "trip_distance_by_mode_income"
    summary_type: "validation"
    description: "Trip distance distribution by mode and income category"
    data_source: "individual_trips"
    group_by: ["distance_bin", "trip_mode", "income_bin"]
    weight_field: "sample_rate"
    aggregations:
      trips: "count"
      avg_distance:
        column: "trip_distance_miles"
        agg: "mean"
    bins:
      distance:
        breaks: [0, 5, 10, 20, 50, 1000]
        labels: ['<5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
      income:
        breaks: [0, 30000, 60000, 100000, 150000, 1000000000]
        labels: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
    filters:
      trip_distance_miles: {">": 0}
    share_within: "income_bin"
```

## ctramp_data_model.yaml

Maps CTRAMP output file columns to standardized names.

### Structure

```yaml
data_source_name:
  file_pattern: "fileName_{iteration}.csv"  # {iteration} replaced with run iteration
  columns:
    standard_name: "ctramp_column_name"
```

### Example

```yaml
individual_trips:
  file_pattern: "indivTripData_{iteration}.csv"
  columns:
    trip_mode: "trip_mode"
    tour_purpose: "tour_purpose"
    trip_distance_miles: "trip_distance"
    depart_period: "depart_period"
    trip_time_minutes: "travelTime"
    sample_rate: "sampleRate"

households:
  file_pattern: "householdData_{iteration}.csv"
  columns:
    household_id: "hh_id"
    income: "income"
    auto_ownership: "autos"
    household_size: "size"
    county: "county"
```

### Adding New Mappings

1. Identify CTRAMP output file and column names
2. Add to appropriate data source or create new section
3. Use in `validation_config.yaml` summaries

## variable_labels.yaml

Human-readable labels for variables used in charts.

### Structure

```yaml
column_name: "Display Label"
```

### Example

```yaml
# Mode
trip_mode: "Trip Mode"
tour_mode: "Tour Mode"

# Purpose
tour_purpose: "Tour Purpose"
trip_purpose: "Trip Purpose"

# Geography
county: "County"
taz: "TAZ"

# Household
income_category_bin: "Income Category"
auto_ownership: "Autos Owned"
household_size: "Household Size"

# Time
depart_period: "Departure Period"
arrive_period: "Arrival Period"

# Distance/Time
trip_distance_miles: "Distance (miles)"
trip_time_minutes: "Travel Time (minutes)"
```

Labels automatically applied in dashboard charts.

## Dashboard YAML Files

Located in `dashboard/` directory. Named `dashboard-N-title.yaml`.

### Structure

```yaml
title: "Tab Title"
description: "Tab description shown at top"

sections:
  - title: "Section Name"
    layout: "two_column"  # single_column, two_column, three_column
    charts:
      - type: "bar"
        title: "Chart Title"
        # ... chart config
      
      - type: "line"
        title: "Another Chart"
        # ... chart config
```

### Chart Types

#### Bar Chart

```yaml
- type: "bar"
  title: "Trips by Mode"
  data_file: "trip_mode_choice.csv"
  x: "trip_mode"
  y: "trips"
  color: "dataset"
  orientation: "h"  # "h" or "v"
  barmode: "group"  # "group", "stack", "relative"
```

#### Line Chart

```yaml
- type: "line"
  title: "Mode Share Trend"
  data_file: "mode_share_trend.csv"
  x: "year"
  y: "share"
  color: "trip_mode"
```

#### Scatter Plot

```yaml
- type: "scatter"
  title: "Distance vs Time"
  data_file: "trip_characteristics.csv"
  x: "trip_distance_miles"
  y: "trip_time_minutes"
  color: "trip_mode"
```

#### Box Plot

```yaml
- type: "box"
  title: "Distance Distribution"
  data_file: "trip_distance.csv"
  x: "trip_mode"
  y: "trip_distance_miles"
  color: "dataset"
```

#### Histogram

```yaml
- type: "histogram"
  title: "Trip Distance Distribution"
  data_file: "trip_distance.csv"
  x: "trip_distance_miles"
  nbins: 50
```

### Chart Options

#### Faceting

Create subplots by category:

```yaml
facet_col: "county"        # Create subplot for each county
facet_col_wrap: 2          # Number of columns
```

#### Category Ordering

Control order of categories:

```yaml
category_orders:
  trip_mode: ["Walk", "Bike", "Transit", "Drive Alone", "Carpool"]
  income_category_bin: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
```

#### Custom Labels

Override axis labels:

```yaml
labels:
  trip_mode: "Travel Mode"
  trips: "Number of Trips"
  share: "Share (%)"
```

### Complete Chart Example

```yaml
- type: "bar"
  title: "Mode Choice by Income Category"
  data_file: "trip_mode_by_income.csv"
  x: "trip_mode"
  y: "share"
  color: "dataset"
  orientation: "h"
  barmode: "group"
  facet_col: "income_category_bin"
  facet_col_wrap: 3
  category_orders:
    trip_mode: ["Walk", "Bike", "Transit", "Drive Alone", "Carpool"]
    income_category_bin: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
  labels:
    trip_mode: "Travel Mode"
    share: "Mode Share (%)"
```

## Environment Variables

Optional environment variables:

```bash
# Dashboard port
export STREAMLIT_SERVER_PORT=8501

# Data directory override
export TM2PY_UTILS_DATA_DIR="/path/to/data"

# Log level
export TM2PY_UTILS_LOG_LEVEL="DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

## File Locations

```
tm2py_utils/summary/validation/
├── validation_config.yaml          # Main config
├── data_model/
│   ├── ctramp_data_model.yaml     # Column mappings
│   └── variable_labels.yaml       # Display labels
├── dashboard/
│   ├── dashboard-0-population.yaml
│   ├── dashboard-1-households.yaml
│   └── ...                         # Dashboard tab configs
├── outputs/                        # Generated summaries
│   ├── auto_ownership_regional.csv
│   ├── trip_mode_choice.csv
│   └── dashboard/                  # Copied for dashboard
│       ├── auto_ownership_regional.csv
│       └── ...
└── summaries/
    ├── run_all.py                  # Main runner
    └── custom.py                   # Custom summary logic
```

## Validation

Check configuration validity:

```bash
cd tm2py_utils/summary/validation

# List configured summaries
python list_summaries.py

# Test generation (dry run)
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml --dry-run

# Generate single summary for testing
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml --summary-name trip_mode_choice
```

## Common Configurations

### Core vs Validation Filter

```yaml
# Generate only core summaries (fast)
generate_summaries: "core"

# Generate only validation summaries
generate_summaries: "validation"

# Generate all summaries
generate_summaries: "all"
```

### Multiple Model Runs

```yaml
input_directories:
  - path: "/model/runs/2015_base"
    label: "2015 Base Year"
  
  - path: "/model/runs/2023_v05"
    label: "2023 TM2.2 v05"
  
  - path: "/model/runs/2023_v06_draft"
    label: "2023 TM2.2 v06 (draft)"
```

All runs compared side-by-side in dashboard.

### Custom Output Location

```yaml
output_directory: "/shared/validation/outputs"
```

## See Also

- [Summary System Guide](summaries.md)
- [Dashboard Guide](dashboard.md)
- [Contributing Guide](contributing.md)
