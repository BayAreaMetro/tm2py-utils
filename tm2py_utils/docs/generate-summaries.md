# Generate Summaries from Model Runs

Guide to generating validation summaries from CTRAMP model outputs.

## Overview

The summary generation system reads raw model outputs (CSV files) and produces **aggregated summary tables** for validation and comparison. The process is entirely **configuration-driven** - no coding required.

**What it does:**
- Loads model outputs (households, persons, tours, trips)
- Applies weights (sample expansion)
- Groups data by specified dimensions
- Calculates counts and shares
- Bins continuous variables (distance, time, age)
- Aggregates categories (4+ household sizes, mode groups)
- Combines multiple model runs into single CSVs

**Output:** CSV files ready for visualization in dashboards or BI tools.

---

## Quick Start

### 1. Configure Input Data

Edit `validation_config.yaml` to point to your model run directories:

```yaml
# Input datasets to analyze
input_directories:
  - path: "A:\\2023-tm22-dev-version-05\\ctramp_output"
    name: "2023_version_05"
    display_name: "2023 TM2.2 v05"
    source_type: "model"
    description: "2023 TM2.2 Development Version 05"
    iteration: 1  # Use iteration 1 files
    
  - path: "A:\\2015-tm22-dev-sprint-04\\ctramp_output"
    name: "2015_sprint_04"
    display_name: "2015 TM2.2 Sprint 04"
    source_type: "model"
    description: "2015 TM2.2 Development Sprint 04"
    iteration: 1
```

**Configuration Fields:**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `path` | ✅ | Directory containing CTRAMP outputs | `"A:\\model_run\\ctramp_output"` |
| `name` | ✅ | Internal identifier (no spaces) | `"2023_version_05"` |
| `display_name` | ✅ | Human-readable name for dashboards | `"2023 TM2.2 v05"` |
| `source_type` | ⚠️ | Data source type | `"model"`, `"survey"` |
| `description` | ⚠️ | Long description | `"Base year 2023 model"` |
| `iteration` | ⚠️ | Which iteration files to load | `1` (uses `*_1.csv` files) |

### 2. Set Output Location

```yaml
# Output location
output_directory: "C:\\GitHub\\tm2py-utils\\tm2py_utils\\summary\\validation\\outputs\\dashboard"
```

All summary CSVs will be saved here.

### 3. Run Summary Generation

From the **validation directory** (`tm2py_utils/summary/validation`):

```powershell
# Activate environment (required for dependencies)
conda activate tm2py-utils

# Generate all summaries
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

**Alternative (from workspace root):**

```powershell
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
python -m tm2py_utils.summary.validation.summaries.run_all --config C:\GitHub\tm2py-utils\tm2py_utils\summary\validation\validation_config.yaml
```

---

## Expected Input Files

The system looks for these files in each `input_directories.path`:

### Required Files

| File Pattern | Description | Example |
|-------------|-------------|---------|
| `householdData_{iteration}.csv` | Household data | `householdData_1.csv` |
| `personData_{iteration}.csv` | Person data | `personData_1.csv` |
| `indivTourData_{iteration}.csv` | Individual tours | `indivTourData_1.csv` |
| `indivTripData_{iteration}.csv` | Individual trips | `indivTripData_1.csv` |

### Optional Files

| File Pattern | Description |
|-------------|-------------|
| `wsLocResults.csv` | Workplace/school location (no iteration number) |
| `jointTourData_{iteration}.csv` | Joint household tours |
| `jointTripData_{iteration}.csv` | Joint household trips |

**File Naming:**
- `{iteration}` is replaced with the value from `input_directories[].iteration` config
- Default: `iteration: 1` → looks for `householdData_1.csv`
- If `iteration` not specified, uses highest numbered file (e.g., `householdData_3.csv` if 1, 2, 3 exist)

**Data Format:**
All files must match the [CTRAMP data model](data-model.md). See that page for required columns and codes.

---

## Output Structure

The system generates **two types of output files**:

### 1. Per-Dataset Files

One file per summary per dataset, with dataset name in filename:

```
auto_ownership_regional_2023 TM2.2 v05.csv
auto_ownership_regional_2015 TM2.2 Sprint 04.csv
tour_mode_choice_2023 TM2.2 v05.csv
tour_mode_choice_2015 TM2.2 Sprint 04.csv
```

### 2. Combined Files

One file per summary with **all datasets merged** via `dataset` column:

```
auto_ownership_regional.csv  # Contains both 2023 and 2015 data
tour_mode_choice.csv         # Contains both 2023 and 2015 data
```

**Combined File Structure:**

```csv
num_vehicles,households,share,dataset
0,150000,0.25,2023 TM2.2 v05
1,200000,0.33,2023 TM2.2 v05
2,180000,0.30,2023 TM2.2 v05
0,120000,0.22,2015 TM2.2 Sprint 04
1,190000,0.35,2015 TM2.2 Sprint 04
2,175000,0.32,2015 TM2.2 Sprint 04
```

The `dataset` column contains the `display_name` from your config.

**Dashboard Usage:**
Combined files are what dashboards use - the `dataset` column enables filtering/comparison across runs.

---

## Pre-Configured Summaries

The system includes **25 pre-configured summaries** across 5 topic areas:

### Auto Ownership (5 summaries)

| Summary Name | Description | Dimensions |
|-------------|-------------|------------|
| `auto_ownership_regional` | Vehicle ownership distribution | `num_vehicles` |
| `auto_ownership_by_income` | Vehicles by income quartile | `income_category`, `num_vehicles` |
| `auto_ownership_by_household_size` | Vehicles by household size | `num_persons`, `num_vehicles` |
| `auto_ownership_by_county` | Vehicles by county | `county`, `num_vehicles` |
| `auto_ownership_by_household_size_acs` | Vehicles by 1/2/3/4+ persons (ACS format) | `num_persons_agg`, `num_vehicles` |

### Work Location (3 summaries)

| Summary Name | Description | Dimensions |
|-------------|-------------|------------|
| `work_distance_by_county` | Commute distance distribution | `county`, `work_distance_bin` |
| `workplace_destination_by_home_county` | Where residents work | `county` (home), `work_county` |
| `work_location_by_income` | Work location by income | `income_category`, `work_county` |

### CDAP - Coordinated Daily Activity Patterns (2 summaries)

| Summary Name | Description | Dimensions |
|-------------|-------------|------------|
| `cdap_by_person_type` | Activity pattern by person type | `person_type`, `cdap` |
| `cdap_by_share` | Overall activity pattern distribution | `cdap` |

### Tours (6 summaries)

| Summary Name | Description | Dimensions |
|-------------|-------------|------------|
| `tour_frequency_by_purpose` | Tours per person by purpose | `tour_purpose`, `tours_per_person` |
| `tour_mode_choice` | Tour mode distribution (17 modes) | `tour_mode` |
| `tour_mode_choice_aggregated` | Tour mode aggregated (Auto/Transit/Active) | `tour_mode_agg` |
| `tour_mode_by_purpose` | Mode choice by trip purpose | `tour_purpose`, `tour_mode` |
| `tour_mode_by_purpose_aggregated` | Aggregated mode by purpose | `tour_purpose`, `tour_mode_agg` |
| `tour_distance` | Tour distance distribution | `tour_distance_bin` |

### Trips (9 summaries)

| Summary Name | Description | Dimensions |
|-------------|-------------|------------|
| `trip_mode_choice` | Trip mode distribution (17 modes) | `trip_mode` |
| `trip_mode_choice_aggregated` | Trip mode aggregated | `trip_mode_agg` |
| `trip_mode_by_purpose` | Mode by trip purpose | `trip_purpose`, `trip_mode` |
| `trip_mode_by_purpose_aggregated` | Aggregated mode by purpose | `trip_purpose`, `trip_mode_agg` |
| `trip_distance` | Trip distance distribution | `trip_distance_bin` |
| `trip_purpose` | Trip purpose distribution | `trip_purpose` |
| `time_of_day_tours` | Tour start time distribution | `start_period` |
| `tour_start_time` | Tour departure time | `start_period_bin` |
| `tour_end_time` | Tour arrival time | `end_period_bin` |

---

## Sample Expansion (Weighting)

All summaries are **automatically weighted** using the household `sampleRate` field.

**How it works:**

1. **Read `sampleRate`** from `householdData_1.csv` (value between 0 and 1)
   - `0.05` = 5% sample
   - `0.5` = 50% sample
   - `1.0` = 100% sample (no expansion needed)

2. **Calculate expansion factor** = `1 / sampleRate`
   - `0.05` → weight of `20.0` (each record represents 20 households)
   - `0.5` → weight of `2.0` (each record represents 2 households)
   - `1.0` → weight of `1.0` (no expansion)

3. **Apply to all related tables**:
   - Households: Use `sampleRate` directly
   - Persons: Inherit from household
   - Tours: Inherit from household
   - Trips: Inherit from household

**Example:**

```csv
# householdData_1.csv
hh_id,autos,sampleRate
1,2,0.05
2,1,0.05
```

**After weighting:**
- Household 1 represents `1 / 0.05 = 20` actual households with 2 vehicles
- Household 2 represents `20` actual households with 1 vehicle
- Total: `40` households in the weighted summary

**Output summary:**

```csv
num_vehicles,households,share
1,20,0.50
2,20,0.50
```

**No configuration needed** - weighting happens automatically based on the CTRAMP data model.

---

## Understanding Output Columns

Summaries contain three types of columns:

### 1. Dimension Columns

The grouping variables (from `group_by` in config):

```csv
num_vehicles,income_category  # Dimensions
0,1
0,2
1,1
```

### 2. Metric Columns

Calculated values:

| Column | Description | Calculation |
|--------|-------------|-------------|
| `households` | Weighted count | `sum(weight)` |
| `persons` | Weighted count | `sum(weight)` |
| `tours` | Weighted count | `sum(weight)` |
| `trips` | Weighted count | `sum(weight)` |
| `share` | Percentage within group | `count / total` |

The metric name depends on the data source (households → `households`, tours → `tours`, etc.).

### 3. Dataset Column

Identifier for multi-run comparisons:

```csv
dataset
2023 TM2.2 v05
2015 TM2.2 Sprint 04
```

---

## Command Line Options

### Full Options

```powershell
python -m tm2py_utils.summary.validation.summaries.run_all --help
```

### Key Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--config PATH` | Configuration file | `--config validation_config.yaml` |
| `--input-dirs DIR [DIR...]` | Input directories (alternative to config) | `--input-dirs path1 path2` |
| `--output-dir PATH` | Output directory (alternative to config) | `--output-dir results/` |
| `--summaries TYPE [TYPE...]` | Generate specific summary types only | `--summaries auto_ownership trip_mode` |

### Examples

**Generate all summaries from config:**

```powershell
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

**Generate only auto ownership and tour mode summaries:**

```powershell
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml --summaries auto_ownership tour_mode
```

**Use command line instead of config file:**

```powershell
python -m tm2py_utils.summary.validation.summaries.run_all \
  --input-dirs A:\model_2023\ctramp_output A:\model_2015\ctramp_output \
  --output-dir C:\results\summaries
```

---

## Execution Log

The script provides detailed logging of each step:

```
INFO - Starting CTRAMP validation summary generation
INFO - Input directories: 2
INFO - Output directory: C:\...\outputs\dashboard
INFO - Enabled summaries: ['auto_ownership', 'work_location', 'tour_frequency', 'tour_mode', 'tour_time', 'trip_mode']

INFO - Loading data from 2023_version_05: A:\2023-tm22-dev-version-05\ctramp_output
INFO -   → Found iteration 1: householdData_1.csv
INFO -   ✓ Loaded households: 2,490,000 records from householdData_1.csv
INFO -     → Applied data model mapping for households
INFO -     → Aggregated 'num_persons' into 4 categories (num_persons_agg)
INFO -   → Found iteration 1: personData_1.csv
INFO -   ✓ Loaded persons: 6,840,000 records from personData_1.csv
...
INFO - Generated auto_ownership_regional: 7 rows
INFO - Generated auto_ownership_by_income: 28 rows
...
INFO - Saving 50 summary tables to C:\...\outputs\dashboard
INFO -   ✓ Saved auto_ownership_regional.csv: 14 rows (2 datasets × 7 vehicle categories)
...
INFO - Combining multi-run summaries...
INFO -   ℹ Combined 50 summaries into 25 multi-run tables
```

**Key indicators:**
- ✓ Success
- ⚠ Warning (non-critical)
- ✗ Error (critical)
- → Processing step

---

## Troubleshooting

### File Not Found Errors

```
FileNotFoundError: Required file not found: householdData_1.csv in A:\model_run\ctramp_output
```

**Solutions:**
1. Check that `path` in config points to correct directory
2. Verify files exist: `householdData_1.csv`, `personData_1.csv`, etc.
3. Check `iteration` value matches file suffix (`_1`, `_2`, `_3`, etc.)
4. For final outputs, use `iteration: 1`

### Missing Columns

```
KeyError: 'hh_id'
```

**Solutions:**
1. Verify files match [CTRAMP data model](data-model.md)
2. Check column names exactly match expected format
3. Review `ctramp_data_model.yaml` for column mappings

### Empty Summaries

```
WARNING - Generated auto_ownership_regional: 0 rows
```

**Causes:**
- Data filtering removed all rows
- Missing required columns
- Incorrect data types

**Solutions:**
1. Check data has expected columns and values
2. Review filter conditions in summary config
3. Verify weighting columns exist (`sampleRate`)

### Memory Issues

For very large model runs (>5M households):

```python
# In validation_config.yaml, process fewer datasets at once
input_directories:
  - path: "A:\\large_model\\ctramp_output"
    iteration: 1
# Comment out other datasets and run separately
```

### Encoding Errors

```
UnicodeDecodeError: 'charmap' codec can't decode
```

**Solution:** Files should be UTF-8 encoded. The system handles this automatically for standard CTRAMP outputs.

---

## Performance Tips

**Typical runtime:** 2-5 minutes for 2 model runs with 2.5M households each

**Optimize:**
1. **Use iteration numbers** - Don't rely on automatic highest-iteration detection
2. **Generate subsets** - Use `--summaries` to generate only needed summaries
3. **Reduce datasets** - Comment out unnecessary `input_directories` entries
4. **SSD storage** - Put model outputs on fast storage

**Memory usage:** ~2-4 GB for typical Bay Area model run

---

## Next Steps

After generating summaries:

- **[Deploy Dashboard](deploy-dashboard.md)** - Visualize summaries in Streamlit
- **[Create Custom Summaries](custom-summaries.md)** - Define new aggregations
- **[Integrate External Data](external-data.md)** - Add ACS/CTPP/survey comparisons
- **[Data Model Reference](data-model.md)** - Understand required data format

---

## Advanced: Programmatic Usage

For integration into automated workflows:

```python
from pathlib import Path
from tm2py_utils.summary.validation.summaries.run_all import load_config_file, main

# Load config
config, config_data = load_config_file(Path("validation_config.yaml"))

# Modify programmatically
config.output_directory = Path("custom_output_dir")

# Generate summaries
# (Call main() or use SummaryGenerator directly)
```

See `run_all.py` source code for full API.
