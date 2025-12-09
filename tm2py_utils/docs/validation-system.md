# Validation Summary System

Complete guide to creating, configuring, and deploying validation summaries for Travel Model Two analysis.

## Overview

The validation summary system provides a flexible, config-driven framework for:
- Generating statistics from CTRAMP model runs
- Comparing model outputs to observed data (ACS, CTPP, travel surveys)
- Creating interactive dashboards for validation
- Managing multiple scenarios and datasets

**Key Features:**
- **No coding required** - Define summaries in YAML
- **34 pre-configured summaries** (21 core + 13 validation)
- **Flexible aggregation** - Group, bin, weight, and filter data
- **Multiple data sources** - Model runs, surveys, census data
- **Interactive visualization** - Streamlit dashboard with 8 tabs

## Quick Start

### Generate Summaries from Model Run

```bash
cd tm2py_utils/summary/validation

# Edit validation_config.yaml to point to your model outputs
# Then generate summaries
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml
```

### Deploy Dashboard

```bash
# Copy summaries and launch dashboard
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --launch-dashboard
```

Visit http://localhost:8501

---

## 1. Working with Model Run Data

### Pointing to New Model Outputs

Edit `validation_config.yaml` to add your model run directory:

```yaml
input_directories:
  - path: "C:/model_runs/2023_base_year"
    label: "2023 Base Year"
  
  - path: "C:/model_runs/2050_plan"
    label: "2050 RTP"
```

**Required files in directory:**
- `householdData_1.csv` - Household attributes
- `personData_1.csv` - Person attributes
- `indivTourData_1.csv` - Tour-level data
- `indivTripData_1.csv` - Trip-level data
- `wsLocResults.csv` - Work/school locations (optional)

### Creating Summaries from Model Data

#### Example 1: Simple Trip Mode Choice

```yaml
custom_summaries:
  - name: "trip_mode_choice"
    summary_type: "core"
    description: "Trip mode choice distribution"
    data_source: "individual_trips"
    group_by: "trip_mode"
    weight_field: "sample_rate"
    count_name: "trips"
```

**Output:** `trip_mode_choice.csv`
```csv
trip_mode,trips,share,dataset
Drive Alone,450000,42.5,2023 Base Year
Carpool,180000,17.0,2023 Base Year
Transit,95000,9.0,2023 Base Year
...
```

#### Example 2: Tours by Purpose and Mode

```yaml
custom_summaries:
  - name: "tour_mode_by_purpose"
    summary_type: "core"
    description: "Tour mode choice by purpose"
    data_source: "individual_tours"
    group_by: ["tour_purpose", "tour_mode"]
    weight_field: "sample_rate"
    aggregations:
      tours: "count"
    share_within: "tour_purpose"
```

**Output:** Each purpose shows mode shares summing to 100%

#### Example 3: Trip Distance with Multiple Metrics

```yaml
custom_summaries:
  - name: "trip_distance_stats"
    summary_type: "validation"
    description: "Trip distance statistics by mode"
    data_source: "individual_trips"
    group_by: "trip_mode"
    weight_field: "sample_rate"
    aggregations:
      trips: "count"
      avg_distance:
        column: "trip_distance_miles"
        agg: "mean"
      total_vmt:
        column: "trip_distance_miles"
        agg: "sum"
      max_distance:
        column: "trip_distance_miles"
        agg: "max"
```

### Available Data Sources

| Data Source | File Pattern | Common Uses |
|-------------|--------------|-------------|
| `households` | `householdData_1.csv` | Auto ownership, household size, income |
| `persons` | `personData_1.csv` | Person type, age, employment |
| `individual_tours` | `indivTourData_1.csv` | Tour frequency, mode choice, timing |
| `individual_trips` | `indivTripData_1.csv` | Trip mode, purpose, distance, time |
| `workplace_school` | `wsLocResults.csv` | Journey to work, commute patterns |

---

## 2. Working with Other Data Sources (ACS, CTPP, Surveys)

### Overview

Observed data from census sources (ACS, CTPP) and household travel surveys must be preprocessed to match the model output format before use in the validation system.

**Key requirements for all observed data:**
- Include `dataset` column with source name (e.g., "ACS 2019", "2022 Travel Survey")
- Use same column names as model outputs (e.g., `trip_mode`, not `mode`)
- Match model geography (regional, county, TAZ)
- Pre-aggregate to summary level (counts/shares)

### Adding Preprocessed Observed Data

Once your data is preprocessed to match model format:

#### Step 1: Save Preprocessed Files

**Example: `survey_trip_mode.csv`**
```csv
trip_mode,trips,share,dataset
Drive Alone,1250,45.2,2022 Travel Survey
Carpool,380,13.7,2022 Travel Survey
Transit,295,10.7,2022 Travel Survey
Walk,520,18.8,2022 Travel Survey
Bike,320,11.6,2022 Travel Survey
```

#### Step 2: Configure as Observed Data Source

Add to `validation_config.yaml`:

```yaml
observed_data_sources:
  - name: "2022 Travel Survey"
    directory: "C:/data/travel_survey_2022"
    files:
      trip_mode_choice: "survey_trip_mode.csv"
      tour_mode_choice: "survey_tour_mode.csv"
      trip_distance: "survey_trip_distance.csv"
```

#### Step 3: Reference in Summary Definition

```yaml
custom_summaries:
  - name: "trip_mode_choice"
    data_source: "individual_trips"
    group_by: "trip_mode"
    weight_field: "sample_rate"
    count_name: "trips"
    observed_data: "2022 Travel Survey"
    observed_file: "trip_mode_choice"
```

**Result:** Model and observed data combined in one CSV for side-by-side comparison in dashboard.

---

## 3. Preprocessing ACS and CTPP Data

Census data (ACS, CTPP) and household travel surveys require preprocessing to match model geography and format. Below are examples of preprocessing workflows.

### Preprocessing ACS Data

#### Example: Auto Ownership from ACS

**Step 1: Download ACS Table B08201**

Use Census API or data.census.gov:
- Table: B08201 (Household Size by Vehicles Available)
- Geography: Counties in Bay Area

**Step 2: Aggregate to Model Geography**

Python preprocessing script:

```python
import pandas as pd

# Load ACS data
acs = pd.read_csv("acs_b08201_raw.csv")

# Aggregate to region
regional = acs.groupby('vehicles_available').agg({
    'estimate': 'sum',
    'moe': lambda x: (x**2).sum()**0.5  # Combine margins of error
}).reset_index()

# Calculate shares
regional['share'] = regional['estimate'] / regional['estimate'].sum() * 100

# Format for validation system
output = pd.DataFrame({
    'auto_ownership': regional['vehicles_available'].map({
        0: '0 autos',
        1: '1 auto',
        2: '2 autos',
        3: '3+ autos'
    }),
    'households': regional['estimate'],
    'share': regional['share'],
    'dataset': 'ACS 2019'
})

output.to_csv("acs_auto_ownership_regional.csv", index=False)
```

**Step 3: Configure as Observed Data**

```yaml
observed_data_sources:
  - name: "ACS 2019"
    directory: "C:/data/acs_2019"
    files:
      auto_ownership_regional: "acs_auto_ownership_regional.csv"
      auto_ownership_by_size: "acs_auto_by_size.csv"
```

### Preprocessing CTPP Data

#### Example: Journey to Work

**Step 1: Download CTPP Part 3**

- Table: Means of Transportation to Work
- Geography: TAZ-to-TAZ or County-to-County

**Step 2: Process CTPP Data**

```python
import pandas as pd

# Load CTPP data
ctpp = pd.read_csv("ctpp_journey_to_work.csv")

# Aggregate modes to match model categories
mode_mapping = {
    'Car, truck, or van - drove alone': 'Drive Alone',
    'Car, truck, or van - carpooled': 'Carpool',
    'Public transportation': 'Transit',
    'Walked': 'Walk',
    'Bicycle': 'Bike',
    'Taxicab, motorcycle, or other means': 'Other'
}

ctpp['mode'] = ctpp['mode_detailed'].map(mode_mapping)

# Aggregate to region
regional = ctpp.groupby('mode').agg({
    'workers': 'sum'
}).reset_index()

regional['share'] = regional['workers'] / regional['workers'].sum() * 100
regional['dataset'] = 'CTPP 2012-2016'

# Save
regional.to_csv("ctpp_journey_to_work_mode.csv", index=False)
```

### Geography Crosswalks

For TAZ-level comparisons, create crosswalks:

```python
# Map Census tracts to model TAZs
crosswalk = pd.read_csv("tract_to_taz_crosswalk.csv")

acs_tract = pd.read_csv("acs_by_tract.csv")

# Apportion to TAZ based on population weights
acs_taz = acs_tract.merge(crosswalk, on='tract')
acs_taz['value'] = acs_taz['value'] * acs_taz['weight']
acs_taz = acs_taz.groupby('taz')['value'].sum().reset_index()
```

---

## 4. Creating Custom Aggregations

### Defining New Mode Groups

#### Step 1: Map Detailed Modes to Groups

Create aggregation in preprocessing or post-processing:

```yaml
# In validation_config.yaml, reference aggregated column
custom_summaries:
  - name: "tour_mode_aggregated"
    data_source: "individual_tours"
    group_by: "tour_mode_agg"  # Pre-created aggregated column
    count_name: "tours"
```

#### Step 2: Create Aggregated Column

Add to data model processing (if not in CTRAMP output):

```python
# In custom summary logic or preprocessing
mode_aggregation = {
    'DRIVEALONEFREE': 'Drive Alone',
    'DRIVEALONEPAY': 'Drive Alone',
    'SHARED2FREE': 'Carpool',
    'SHARED2PAY': 'Carpool',
    'SHARED3FREE': 'Carpool',
    'SHARED3PAY': 'Carpool',
    'WALK_LOC': 'Transit',
    'WALK_LRF': 'Transit',
    'WALK_EXP': 'Transit',
    'WALK_HVY': 'Transit',
    'WALK_COM': 'Transit',
    'WALK': 'Walk',
    'BIKE': 'Bike'
}

df['tour_mode_agg'] = df['tour_mode'].map(mode_aggregation)
```

### Aggregating Income Categories

```yaml
custom_summaries:
  - name: "auto_ownership_by_income_group"
    data_source: "households"
    group_by: ["income_group", "auto_ownership"]
    bins:
      income:
        breaks: [0, 60000, 150000, 1000000000]
        labels: ['Low', 'Medium', 'High']
        bin_column: "income_group"
```

### Custom Purpose Groups

Group related purposes:

```yaml
custom_summaries:
  - name: "trips_by_purpose_group"
    data_source: "individual_trips"
    group_by: "purpose_group"
    # Assumes purpose_group pre-created:
    # Work/School, Shopping/Maintenance, Social/Recreation
```

---

## 5. Creating Custom Bins

Binning converts continuous variables to categories for analysis.

### Distance Bins

```yaml
custom_summaries:
  - name: "trips_by_distance_bin"
    data_source: "individual_trips"
    group_by: ["distance_bin", "trip_mode"]
    weight_field: "sample_rate"
    count_name: "trips"
    bins:
      distance:
        breaks: [0, 1, 3, 5, 10, 20, 50, 1000]
        labels: ['<1mi', '1-3mi', '3-5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
        source_column: "trip_distance_miles"
        bin_column: "distance_bin"
```

**Parameters:**
- `breaks`: Bin boundaries (left-inclusive, right-exclusive)
- `labels`: Display names for bins
- `source_column`: Column to bin (default: bin name)
- `bin_column`: Output column name (default: bin name + "_bin")

### Time of Day Bins

```yaml
bins:
  time_period:
    breaks: [0, 6, 9, 15, 19, 24]
    labels: ['Early AM', 'AM Peak', 'Midday', 'PM Peak', 'Evening']
    source_column: "departure_hour"
```

### Age Bins

```yaml
bins:
  age_category:
    breaks: [0, 18, 25, 35, 50, 65, 120]
    labels: ['0-17', '18-24', '25-34', '35-49', '50-64', '65+']
    source_column: "age"
```

### Income Quartiles

```yaml
bins:
  income_quartile:
    breaks: [0, 35000, 70000, 120000, 1000000000]
    labels: ['Q1', 'Q2', 'Q3', 'Q4']
    source_column: "household_income"
```

### Multi-Dimensional Binning

```yaml
custom_summaries:
  - name: "trip_distance_time_matrix"
    group_by: ["distance_bin", "time_bin", "trip_mode"]
    bins:
      distance:
        breaks: [0, 5, 10, 20, 1000]
        labels: ['<5mi', '5-10mi', '10-20mi', '20+mi']
      time:
        breaks: [0, 15, 30, 60, 1000]
        labels: ['<15min', '15-30min', '30-60min', '60+min']
        source_column: "trip_time_minutes"
```

---

## 6. Dashboard Visualization

### Creating Dashboard YAML Files

Dashboard tabs are defined in `dashboard/dashboard-N-title.yaml`.

#### Step 1: Create Dashboard File

**Example: `dashboard-8-distance-analysis.yaml`**

```yaml
title: "Distance Analysis"
description: "Trip and tour distance patterns by mode and purpose"

sections:
  - title: "Trip Distance Distribution"
    layout: "two_column"
    charts:
      - type: "bar"
        title: "Trips by Distance"
        data_file: "trips_by_distance_bin.csv"
        x: "distance_bin"
        y: "trips"
        color: "dataset"
        orientation: "v"
        category_orders:
          distance_bin: ['<1mi', '1-3mi', '3-5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
      
      - type: "bar"
        title: "Mode Share by Distance"
        data_file: "trip_mode_by_distance.csv"
        x: "distance_bin"
        y: "share"
        color: "trip_mode"
        orientation: "v"
        barmode: "stack"

  - title: "Distance by Mode"
    layout: "single_column"
    charts:
      - type: "box"
        title: "Distance Distribution by Mode"
        data_file: "trip_distance_detailed.csv"
        x: "trip_mode"
        y: "trip_distance_miles"
        color: "dataset"
```

#### Step 2: Ensure Required CSVs Exist

Configure summaries to generate needed files:

```yaml
# In validation_config.yaml
custom_summaries:
  - name: "trips_by_distance_bin"
    # ... configuration
  
  - name: "trip_mode_by_distance"
    # ... configuration
  
  - name: "trip_distance_detailed"
    # ... configuration
```

#### Step 3: Test Dashboard

```bash
cd tm2py_utils/summary/validation

# Generate summaries
python run_and_deploy_dashboard.py --config validation_config.yaml

# Dashboard auto-discovers new YAML files
# Visit http://localhost:8501
```

### Chart Types Reference

#### Bar Chart

```yaml
- type: "bar"
  title: "Chart Title"
  data_file: "summary.csv"
  x: "category"
  y: "value"
  color: "dataset"
  orientation: "h"  # or "v"
  barmode: "group"  # or "stack", "relative"
```

#### Line Chart

```yaml
- type: "line"
  title: "Trend Over Time"
  data_file: "trend.csv"
  x: "year"
  y: "value"
  color: "category"
```

#### Scatter Plot

```yaml
- type: "scatter"
  title: "Correlation"
  data_file: "scatter.csv"
  x: "variable1"
  y: "variable2"
  color: "group"
  size: "weight"
```

#### Box Plot

```yaml
- type: "box"
  title: "Distribution"
  data_file: "distribution.csv"
  x: "category"
  y: "value"
  color: "dataset"
```

### Faceting (Small Multiples)

Create subplots for each category:

```yaml
- type: "bar"
  title: "Mode Share by County"
  data_file: "mode_by_county.csv"
  x: "trip_mode"
  y: "share"
  color: "dataset"
  facet_col: "county"
  facet_col_wrap: 3  # 3 columns of subplots
```

### Custom Category Ordering

```yaml
category_orders:
  trip_mode: ["Walk", "Bike", "Transit", "Carpool", "Drive Alone"]
  tour_purpose: ["Work", "School", "Shopping", "Maintenance", "Eating Out", "Social"]
  county: ["San Francisco", "Alameda", "Contra Costa", "Santa Clara", "San Mateo"]
```

### Custom Labels

```yaml
labels:
  trip_mode: "Travel Mode"
  trips: "Number of Trips"
  share: "Mode Share (%)"
  distance_bin: "Distance Category"
```

---

## 7. Deploying the Dashboard

### Local Deployment

#### Option 1: Full Workflow

```bash
cd tm2py_utils/summary/validation

# Generate all summaries and launch
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --launch-dashboard
```

#### Option 2: Batch Script (Windows)

```bash
# Double-click deploy_dashboard.bat
# Select option 5: "Generate and LAUNCH dashboard"
```

#### Option 3: Manual Steps

```bash
# 1. Generate summaries
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml

# 2. Copy to dashboard folder
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --skip-generation

# 3. Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
```

### Streamlit Cloud Deployment

#### Step 1: Push to GitHub

```bash
git add .
git commit -m "Update validation dashboard"
git push origin main
```

#### Step 2: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select repository: `BayAreaMetro/tm2py-utils`
4. Set branch: `main`
5. Set main file path: `tm2py_utils/summary/validation/dashboard/dashboard_app.py`
6. Click "Deploy"

#### Step 3: Configure Secrets (if needed)

If using private data sources, add secrets in Streamlit Cloud:

```toml
# .streamlit/secrets.toml
[data_paths]
model_runs = "/path/to/data"
```

### Server Deployment

For internal servers:

```bash
# Run in background with nohup
nohup streamlit run dashboard/dashboard_app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 &

# Or use screen/tmux
screen -S dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
# Ctrl+A, D to detach
```

---

## 8. Frequently Asked Questions

### Data Issues

**Q: "Column not found" error when generating summaries**

A: Check `data_model/ctramp_data_model.yaml` for correct column mappings:

```yaml
individual_trips:
  columns:
    trip_mode: "trip_mode"  # Match actual CTRAMP column name
```

**Q: Summary CSV is empty**

A: Check filters and data availability:
- Verify input directory path in `validation_config.yaml`
- Check if CTRAMP files exist and contain data
- Review any `filters` in summary definition

**Q: Shares don't sum to 100%**

A: Check `share_within` parameter:

```yaml
# Shares within each purpose sum to 100%
share_within: "tour_purpose"

# Without share_within, shares across all rows sum to 100%
```

### Configuration Issues

**Q: How do I add a new column to summaries?**

A: Two steps:
1. Add to `ctramp_data_model.yaml`:
```yaml
individual_trips:
  columns:
    my_new_column: "ctramp_column_name"
```

2. Add label to `variable_labels.yaml`:
```yaml
my_new_column: "My Column Label"
```

**Q: Can I use calculated fields?**

A: Yes, create them in preprocessing or custom summary logic:

```python
# Example: Speed calculation
df['speed_mph'] = df['trip_distance_miles'] / (df['trip_time_minutes'] / 60)
```

Then reference in summary:
```yaml
aggregations:
  avg_speed:
    column: "speed_mph"
    agg: "mean"
```

### Dashboard Issues

**Q: New dashboard tab doesn't appear**

A: Check:
1. File naming: Must be `dashboard-N-title.yaml` (with number)
2. Location: Must be in `dashboard/` directory, not `outputs/dashboard/`
3. YAML syntax: Validate with `python -c "import yaml; yaml.safe_load(open('dashboard-N-title.yaml'))"`

**Q: Chart shows "No data available"**

A: Verify:
1. CSV file exists in `outputs/dashboard/`
2. `data_file` in YAML matches CSV filename exactly
3. CSV contains data (not empty)
4. Required columns exist in CSV

**Q: Categories in wrong order**

A: Use `category_orders`:

```yaml
category_orders:
  distance_bin: ['<1mi', '1-3mi', '3-5mi', '5-10mi', '10-20mi']
```

### Performance Issues

**Q: Summary generation takes too long**

A: Optimization strategies:
1. Generate only core summaries for quick checks:
```yaml
generate_summaries: "core"
```

2. Process fewer model runs (comment out in `input_directories`)

3. Use more specific filters to reduce data size

**Q: Dashboard is slow**

A: Tips:
1. Limit number of facets (subplots)
2. Reduce number of model runs being compared
3. Pre-aggregate data more (fewer rows in CSV)
4. Consider using Parquet instead of CSV for large files

### Comparison Issues

**Q: Model and observed data don't align in charts**

A: Ensure matching:
1. **Column names**: Model and observed must use same names
2. **Categories**: Mode names, purpose names must match exactly
3. **Dataset column**: Observed data must include `dataset` column

**Q: How do I compare to previous model version?**

A: Add as separate input directory:

```yaml
input_directories:
  - path: "/model_runs/v05"
    label: "TM2.2 v05"
  
  - path: "/model_runs/v06"
    label: "TM2.2 v06"
```

Both will appear in same charts for side-by-side comparison.

---

## 9. Common Workflows

### Workflow 1: Quick Model Run Validation

```bash
# 1. Point to new model run
# Edit validation_config.yaml:
#   input_directories:
#     - path: "C:/new_model_run"
#       label: "Test Run"

# 2. Generate core summaries only (fast)
# Edit validation_config.yaml:
#   generate_summaries: "core"

# 3. Run and deploy
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --launch-dashboard

# 4. Review dashboard at http://localhost:8501
```

### Workflow 2: Adding New Observed Data

```bash
# 1. Preprocess observed data to match model format
python preprocess_acs_data.py

# 2. Add to validation_config.yaml:
#   observed_data_sources:
#     - name: "ACS 2021"
#       directory: "C:/data/acs_2021"
#       files:
#         auto_ownership: "acs_auto.csv"

# 3. Reference in existing summary:
#   custom_summaries:
#     - name: "auto_ownership_regional"
#       observed_data: "ACS 2021"
#       observed_file: "auto_ownership"

# 4. Regenerate summaries
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml
```

### Workflow 3: Creating Complete New Analysis

```bash
# 1. Define summary in validation_config.yaml
# 2. Test generation
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml \
  --summary-name my_new_summary

# 3. Create dashboard YAML
# dashboard/dashboard-9-my-analysis.yaml

# 4. Deploy
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --launch-dashboard
```

---

## Additional Resources

- **[Configuration Reference](configuration.md)** - Complete YAML syntax
- **[Dashboard Guide](dashboard.md)** - Chart types and options
- **[Summary Generation](summaries.md)** - Aggregation and filtering
- **[Contributing Guide](contributing.md)** - Adding features
- **[Consolidation Proposal](../summary/CONSOLIDATION_PROPOSAL.md)** - System architecture

## Support

- **Issues**: https://github.com/BayAreaMetro/tm2py-utils/issues
- **Email**: modeling@bayareametro.gov
- **Documentation**: https://bayareametro.github.io/tm2py-utils/
