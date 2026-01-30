# Validation Summary System

Complete guide to creating, configuring, and deploying validation summaries for Travel Model Two analysis.

## Overview

The validation summary system is a **data aggregation and comparison pipeline** that:

1. **Reads raw data** from CTRAMP model outputs or household travel surveys formatted to match the [CTRAMP data model](data-model.md)
2. **Aggregates and transforms** data according to user specifications in YAML configuration files
3. **Combines datasets** into standardized CSVs for cross-scenario and model-vs-observed comparisons
4. **Visualizes results** through a Streamlit dashboard (or any BI tool - Tableau, PowerBI, Shiny, etc.)

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT DATA SOURCES (CTRAMP Data Model Format)              │
├─────────────────────────────────────────────────────────────┤
│ • Model Outputs: householdData_1.csv, personData_1.csv,    │
│                  indivTourData_1.csv, indivTripData_1.csv   │
│ • Travel Surveys: Munged to exactly match CTRAMP format    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ AGGREGATION ENGINE (Config-Driven)                         │
├─────────────────────────────────────────────────────────────┤
│ • Group by dimensions (mode, purpose, county, etc.)        │
│ • Apply weights (sample_rate)                              │
│ • Bin continuous variables (distance, income, age)         │
│ • Aggregate categories (4+ person households)              │
│ • Calculate shares within groups                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ EXTERNAL DATA INTEGRATION (Preprocessed to Match Format)   │
├─────────────────────────────────────────────────────────────┤
│ • ACS: Preprocessed household/person summaries             │
│ • CTPP: Journey-to-work tables matched to model geography  │
│ • Other surveys: Aggregated to same dimensions as model    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Combined CSVs by Topic Area                        │
├─────────────────────────────────────────────────────────────┤
│ • Single CSV per summary with all datasets                 │
│ • Common schema: dimensions + metrics + dataset column     │
│ • Ready for any visualization tool                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ VISUALIZATION (Streamlit Dashboard or Your Tool of Choice) │
└─────────────────────────────────────────────────────────────┘
```

### Key Concepts

**Data Model Alignment**: All input data must conform to the [CTRAMP data model](data-model.md). Model outputs already match this format. Household travel surveys must be transformed to match it exactly (same column names, same codes, same geography).

**Aggregation Pipeline**: The system transforms raw microdata into summary statistics through:
- **Grouping**: Combine records by categorical dimensions
- **Binning**: Convert continuous variables to categories  
- **Aggregation**: Map detailed categories to broader groups (e.g., 4+ person households)
- **Weighting**: Apply sample expansion factors
- **Share calculation**: Compute percentages within groups

**External Data Integration**: For comparison with observed data (ACS, CTPP, surveys), you must **preprocess external data** to match the model's summary format - same columns, same categories, same geography. The system then merges them automatically.

**Visualization Flexibility**: While we provide a Streamlit dashboard, the output CSVs can be used with any BI tool. The value is in the data preparation, not the visualization layer.

### What This System Does

✅ **Compiles** data from multiple model runs and surveys  
✅ **Transforms** raw microdata into comparable summary statistics  
✅ **Cleans** and standardizes data for cross-dataset comparison  
✅ **Packages** results into analysis-ready CSV files  

❌ Does NOT automatically convert ACS/CTPP raw data (you must preprocess)  
❌ Does NOT validate data quality (assumes correct CTRAMP format)  
❌ Does NOT provide statistical testing (just descriptive summaries)

### Quick Navigation

**Getting Started:**
- **[Generate Summaries from Model Runs](generate-summaries.md)** - Run summaries on CTRAMP outputs, understand system workflow
- **[CTRAMP Data Model Reference](data-model.md)** - Complete schema for households, persons, tours, trips

**Advanced Configuration:**
- **[Create Custom Summaries](custom-summaries.md)** - Define new aggregations, binning, and filtering
- **[Integrate External Data](external-data.md)** - Add ACS, CTPP, or survey comparisons

**Visualization:**
- **[Deploy Dashboard](deploy-dashboard.md)** - Launch and customize Streamlit dashboard

**Development:**
- **[Development Tasks & Next Steps](validation-development.md)** - Ongoing work: data model updates, survey formatting, CTPP integration
- **[Code Flow and Execution Guide](code-flow.md)** - Detailed technical documentation for developers

### Pre-Configured Summaries

The system includes **25 pre-configured summaries** across 5 topic areas:
- **Auto Ownership** (5 summaries) - Vehicle ownership by household characteristics
- **Work Location** (3 summaries) - Journey to work patterns  
- **CDAP** (2 summaries) - Coordinated Daily Activity Patterns
- **Tours** (6 summaries) - Tour frequency, mode, purpose, timing
- **Trips** (9 summaries) - Trip mode, purpose, distance, time-of-day

### Development Roadmap

See **[Development Tasks & Next Steps](validation-development.md)** for ongoing work including:
- Updating the data model with new postprocessed fields
- Formatting 2023 household travel survey data
- Fixing broken summaries and adding new validation targets
- Integrating CTPP journey-to-work data

### Code Flow

For developers who want to understand how the validation system executes from configuration files to final outputs, see the **[Code Flow and Execution Guide](code-flow.md)** for detailed technical documentation including class architecture, data processing pipelines, and visual execution diagrams.

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
    name: "2023_base_year"
    display_name: "2023 Base Year"
    source_type: "model"
    iteration: 1  # Use iteration 1 files (_1.csv)
  
  - path: "C:/model_runs/2050_plan"
    name: "2050_plan"
    display_name: "2050 RTP"
    source_type: "model"
    iteration: 1
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
summaries:
  - name: "trip_mode_choice"
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
summaries:
  - name: "tour_mode_by_purpose"
    description: "Tour mode choice by purpose"
    data_source: "individual_tours"
    group_by: ["tour_purpose", "tour_mode"]
    weight_field: "sample_rate"
    count_name: "tours"
    share_within: "tour_purpose"
```

**Output:** Each purpose shows mode shares summing to 100%

#### Example 3: Trip Distance Binning

```yaml
summaries:
  - name: "trip_distance_distribution"
    description: "Trip distance distribution (binned)"
    data_source: "individual_trips"
    group_by: "trip_distance_bin"  # Uses binning_specs
    weight_field: "sample_rate"
    count_name: "trips"

# Define bins in binning_specs section
binning_specs:
  trip_distance:
    bins: [0, 1, 3, 5, 10, 20, 1000]
    labels: ['0-1', '1-3', '3-5', '5-10', '10-20', '20+']
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
observed_summaries:
  - name: "travel_survey_2022"
    display_name: "2022 Travel Survey"
    summaries:
      trip_mode_choice:
        file: "C:/data/travel_survey_2022/survey_trip_mode.csv"
        columns:
          trip_mode: "trip_mode"
          trips: "trips"
          share: "share"
```

**How it works:**
- System loads observed data from specified files
- Applies column mapping to match model output format
- Adds `dataset` column with display_name ("2022 Travel Survey")
- Merges with model summaries automatically by matching name

**Result:** Combined CSV with model and observed data for side-by-side comparison.

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
observed_summaries:
  - name: "acs_2019"
    display_name: "ACS 2019"
    summaries:
      auto_ownership_regional:
        file: "C:/data/acs_2019/acs_auto_ownership_regional.csv"
        columns:
          num_vehicles: "num_vehicles"
          households: "households"
          share: "share"
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

### Aggregating Household Size (4+ Category)

To match ACS categories that group 4+ person households:

```yaml
# Define aggregation mapping
aggregation_specs:
  num_persons_agg:
    apply_to: ["num_persons"]
    mapping:
      1: 1
      2: 2
      3: 3
      4: 4
      5: 4
      6: 4
      7: 4
      8: 4
      9: 4
      10: 4

# Use in summary
summaries:
  - name: "auto_ownership_by_household_size_acs"
    description: "Vehicle ownership by household size (ACS categories)"
    data_source: "households"
    group_by: ["num_persons_agg", "num_vehicles"]
    weight_field: "sample_rate"
    count_name: "households"
    share_within: "num_persons_agg"
```

**How it works:**
- `aggregation_specs` section defines the mapping
- `apply_to` specifies which column(s) to transform
- `mapping` converts values (5→4, 6→4, etc.)
- System creates new column `num_persons_agg` automatically
- Use aggregated column in `group_by`

---

## 5. Creating Custom Bins

Binning converts continuous variables to categories for analysis. Define bins once in `binning_specs`, then reference in summaries.

### Distance Bins

```yaml
# Define bins in binning_specs section
binning_specs:
  trip_distance:
    bins: [0, 1, 3, 5, 10, 20, 1000]
    labels: ['0-1', '1-3', '3-5', '5-10', '10-20', '20+']

# Use in summary by referencing the binned column
summaries:
  - name: "trip_distance_distribution"
    description: "Trip distance distribution (binned)"
    data_source: "individual_trips"
    group_by: "trip_distance_bin"  # Automatically created from trip_distance
    weight_field: "sample_rate"
    count_name: "trips"
```

**How it works:**
- System finds `trip_distance` column in data
- Creates `trip_distance_bin` column using bins and labels
- Use `_bin` suffix in `group_by`

**Parameters:**
- `bins`: Bin boundaries (left-inclusive, right-exclusive)
- `labels`: Display names for bins (one less than bins length)

### Time of Day Bins

```yaml
binning_specs:
  tour_start_hour:
    bins: [0, 6, 9, 15, 19, 24]
    labels: ['Early AM', 'AM Peak', 'Midday', 'PM Peak', 'Evening']
```

### Age Bins

```yaml
binning_specs:
  worker_age:
    bins: [0, 25, 35, 45, 55, 65, 120]
    labels: ['<25', '25-34', '35-44', '45-54', '55-64', '65+']
```

### Income Categories

```yaml
binning_specs:
  income_category:
    bins: [0, 30000, 60000, 100000, 150000, 1000000000]
    labels: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
```

### Using Bins in Summaries

```yaml
summaries:
  - name: "trips_by_distance_and_mode"
    data_source: "individual_trips"
    group_by: ["trip_distance_bin", "trip_mode"]
    weight_field: "sample_rate"
    count_name: "trips"
    share_within: "trip_distance_bin"
```
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
# (Create CSV with same columns as model output + dataset column)
python convert_acs_data.py

# 2. Add to validation_config.yaml:
#   observed_summaries:
#     - name: "acs_2023"
#       display_name: "ACS 2023"
#       summaries:
#         auto_ownership_regional:
#           file: "C:/data/acs_2023/acs_auto_ownership.csv"
#           columns:
#             num_vehicles: "num_vehicles"
#             households: "households"
#             share: "share"

# 3. Regenerate summaries (system auto-merges by matching name)
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml

# 4. Verify combined file includes observed data
# Check outputs/dashboard/auto_ownership_regional.csv
```

### Workflow 3: Creating Complete New Analysis

```bash
# 1. Define summary in validation_config.yaml under summaries section

# 2. Test generation
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml

# 3. Create dashboard YAML (optional - for visualization)
# dashboard/dashboard-households.yaml (or appropriate tab)

# 4. Deploy dashboard
python run_and_deploy_dashboard.py \
  --config validation_config.yaml \
  --launch-dashboard
```

---

## System Architecture

### Summary File Generation

The validation system generates **two types of CSV files** for each summary:

1. **Per-Dataset Files**: One file per input directory with dataset name in filename
   - Example: `cdap_by_share_2023 TM2.2 v05.csv`, `cdap_by_share_2015 TM2.2 Sprint 04.csv`
   - Contains data for single model run only
   - Useful for debugging and individual analysis

2. **Combined Files**: Single file merging all datasets with `dataset` column
   - Example: `cdap_by_share.csv` (contains rows for all datasets)
   - Used by dashboard for multi-run comparisons
   - Generated automatically in `save_summaries()` function

**File locations:**
- `outputs/` - All generated CSV files (both types)
- `outputs/dashboard/` - Copy of all files for dashboard use
- `summary_index.csv` - Metadata catalog of all generated summaries

### How Summary Combination Works

When you have multiple model runs configured (e.g., base year and plan year), the system:

1. Generates individual summary for each dataset
2. Groups summaries by base name (removes dataset suffix)
3. Concatenates DataFrames and adds `dataset` column
4. Saves combined file without dataset suffix

Example:
```python
# Generated files:
cdap_by_share_2023 TM2.2 v05.csv      # 3 rows (H, M, N)
cdap_by_share_2015 TM2.2 Sprint 04.csv  # 3 rows (H, M, N)

# Combined automatically:
cdap_by_share.csv                     # 6 rows (3 per dataset)
```

### Dashboard Integration

Dashboard YAML files reference the **combined files** (without dataset suffix):

```yaml
charts:
  - type: bar
    dataset: cdap_by_share.csv  # Combined file
    x: cdap
    y: share
    color: dataset  # Splits bars by model run
```

The `facet: dataset` or `color: dataset` parameter creates side-by-side comparisons.

---

## Troubleshooting

### Summary Not Generating

**Check 1: Required columns exist in data**

Some summaries require columns that must be derived or joined from other sources:

```yaml
# Example: This will FAIL if person data doesn't have age_category
- name: "cdap_by_age"
  group_by: ["cdap", "age_category"]  # ❌ age_category doesn't exist
```

**Solutions:**
- Check `personData_1.csv` columns: `python -c "import pandas as pd; print(pd.read_csv('personData_1.csv', nrows=1).columns.tolist())"`
- Derive needed columns in data preprocessing
- Comment out summary in `validation_config.yaml` if not feasible

**Check 2: Data source file exists**

```yaml
# This fails if wsLocResults.csv is missing
- name: "journey_to_work"
  data_source: "workplace_school"  # Requires wsLocResults.csv
```

**Check 3: Review summary_index.csv**

```bash
# See what actually generated
cat outputs/dashboard/summary_index.csv | grep "your_summary_name"
```

### Dashboard Shows No Data

**Symptom:** Chart area is blank or shows "No data"

**Common causes:**

1. **CSV file doesn't exist**
   ```bash
   # Check if file exists
   ls outputs/dashboard/cdap_by_share.csv
   ```

2. **Column names don't match**
   ```yaml
   # Dashboard expects 'cdap' but CSV has 'cdap_pattern'
   charts:
     - x: cdap  # ❌ Column not found
   ```

3. **Wrong file referenced** (per-dataset instead of combined)
   ```yaml
   # Wrong:
   dataset: cdap_by_share_2023 TM2.2 v05.csv
   
   # Right:
   dataset: cdap_by_share.csv
   ```

**Debug steps:**
```bash
# Check CSV structure
python -c "import pandas as pd; df = pd.read_csv('outputs/dashboard/cdap_by_share.csv'); print(df.columns); print(df.head())"
```

### Known Limitations

**Disabled Summaries** (commented out in `validation_config.yaml`):

| Summary | Issue | Solution Required |
|---------|-------|-------------------|
| `cdap_by_age` | Needs `age_category` column | Derive from `age` (e.g., <18, 18-64, 65+) |
| `cdap_by_home_county` | Needs `county_name` column | Join household geography or derive from MAZ |
| `cdap_by_auto_ownership` | Needs `num_vehicles` from household | Join person to household data |
| `journey_to_work` | `workplace_school` data not loading | Fix `wsLocResults.csv` data loading |
| `journey_to_work_by_mode` | `workplace_school` data not loading | Fix `wsLocResults.csv` data loading |

**To enable these summaries:**
1. Implement required data derivation/joins
2. Uncomment summary configuration in `validation_config.yaml`
3. Update dashboard YAML if needed
4. Test generation and verify output

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
