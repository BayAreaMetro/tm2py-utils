# Generate Summaries from Model Runs

Guide to generating validation summaries from CTRAMP model outputs using the new simple toolkit.

## Overview

The summary generation system reads raw CTRAMP outputs (CSV files) and produces **aggregated summary tables** for validation and analysis. The process is **configuration-driven** - add summaries by editing YAML, no Python coding required.

!!! tip "System Design"
    To understand the architecture and design principles behind this system, see the [Summary Design System Plan](summary-design-system.md).

**What it does:**
- Loads CTRAMP output files (households, persons, tours, trips)
- Applies value labels (mode 1 → "SOV_GP")
- Creates aggregated categories (17 modes → 5 major groups)
- Bins continuous variables (age → age groups, distance → bins)
- Generates weighted frequency tables
- Validates results for data quality issues
- Saves individual CSV files for each summary

**Output:** 30 CSV files ready for analysis in Excel, pandas, R, or other analysis tools.

---

## Quick Start

### 1. Run Summary Generation

```bash
cd tm2py_utils/summary/validation

# TM1 model or BATS survey (uses default config)
python summarize_model_run.py "C:/path/to/ctramp_output"

# TM2 model (specify TM2 config)
python summarize_model_run.py "C:/path/to/ctramp_output" --config data_model/tm2_data_model.yaml
```

Summaries are saved to `summaries/` by default.

### 2. Specify Custom Output Location

```bash
python summarize_model_run.py "C:/path/to/ctramp_output" --output "my_results"
```

### 3. Use Different Data Model Configuration

```bash
# Available configs:
# - ctramp_data_model.yaml (default) - TM1 format, also works for BATS survey
# - tm2_data_model.yaml - TM2 format
# - survey_data_model.yaml - Specialized survey config
# - custom.yaml - Your own custom configuration

python summarize_model_run.py "C:/path/to/ctramp_output" --config my_custom_config.yaml
```

**The config file determines:**

- **Metadata**: Model type (TM1/TM2/survey), version, description
- **File patterns**: How to find files (e.g., `personData_{iteration}.csv` vs `personData.csv`)
- **Geography system**: TAZ (TM1) vs MGRA (TM2)
- **Time representation**: Hour (TM1) vs period (TM2)
- **Mode definitions**: 21 modes (TM1) vs 17 modes (TM2)
- **Available summaries**: Which summaries can be generated

### 4. Combine Options

```bash
# TM2 model with custom output directory
python summarize_model_run.py "C:/path/to/tm2_output" --config data_model/tm2_data_model.yaml --output "results/tm2_summaries"
```

---

## Expected Input Files

The system looks for these files in the CTRAMP output directory:

### Required Files

| File Pattern | Description | Example |
|-------------|-------------|---------|
| `householdData_*.csv` | Household data | `householdData_3.csv` |
| `personData_*.csv` | Person data | `personData_3.csv` |
| `indivTourData_*.csv` | Individual tours | `indivTourData_3.csv` |
| `indivTripData_*.csv` | Individual trips | `indivTripData_3.csv` |

### Optional Files

| File Pattern | Description | Used For |
|-------------|-------------|----------|
| `wsLocResults.csv` | Work/school location | Commute summaries |
| `jointTourData_*.csv` | Joint tours | Joint tour summaries |

**Note:** The tool automatically detects the iteration number (e.g., `_1.csv`, `_3.csv`).

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
---

## What Gets Generated

The tool creates **30 individual CSV files**, one for each summary. Each file contains aggregated statistics ready for analysis.

### Example Output Files

```
outputs/
├── auto_ownership_regional.csv
├── auto_ownership_by_income.csv
├── auto_ownership_by_household_size.csv
├── person_type_distribution.csv
├── age_distribution.csv
├── cdap_by_person_type.csv
├── cdap_regional.csv
├── tour_frequency_by_purpose.csv
├── tour_mode_choice.csv
├── tour_distance_distribution.csv
├── trip_mode_choice.csv
├── trip_distance_distribution.csv
├── time_of_day_tours.csv
└── ... (30 total)
```

### Example CSV Structure

**Simple distribution** (`auto_ownership_regional.csv`):

```csv
num_vehicles,households,share
0,150234.5,0.054
1,823456.2,0.298
2,1245678.3,0.450
3,445632.1,0.161
4+,102026.9,0.037
```

**Cross-tabulation** (`auto_ownership_by_income.csv`):

```csv
income_category_bin,num_vehicles,households,share
<30K,0,45623.2,0.421
<30K,1,52341.6,0.483
<30K,2,9234.5,0.085
30-60K,0,32456.7,0.156
30-60K,1,98234.5,0.472
30-60K,2,65432.1,0.314
...
```

**With aggregations** (`trip_distance_distribution.csv`):

```csv
trip_distance_bin,trips,share,mean_distance
<1mi,8234567.2,0.342,0.45
1-3mi,5632451.3,0.234,2.12
3-5mi,3456234.1,0.143,4.03
5-10mi,2345678.9,0.097,7.24
10+mi,1987654.0,0.082,18.45
```

---

## Pre-Configured Summaries

The system includes **30 pre-configured summaries** defined in `data_model/ctramp_data_model.yaml`:

### Household Summaries (3)

- Auto ownership (regional, by income, by household size)

### Person & Activity Summaries (4)

- Person type distribution
- Age distribution
- CDAP by person type
- CDAP regional

### Tour Summaries (9)

- Tour frequency by purpose
- Tour mode choice (overall and by purpose)
- Tour distance distributions
- Time of day patterns
- Tour start/end times

### Trip Summaries (8)

- Trip mode choice (overall and by purpose)
- Trip purpose distribution
- Trip distance distributions
- Trip duration distributions

### Work/School Location (6)

- Average commute distance
- Work distance by county
- Workplace destinations
- Work location patterns

See `data_model/ctramp_data_model.yaml` for complete list with full definitions.

---

## Sample Expansion (Weighting)

Most summaries are **automatically weighted** by household sample rate.

**How it works:**

1. System reads sample rate from household data (typically 0.01 to 1.0)
2. Applies expansion factor = `1 / sample_rate`
3. Each household/person/tour/trip is counted with its weight
4. Final counts represent full population estimates

**Example:**
- Sample rate: 0.5 (50% sample)
- Expansion factor: 2.0
- Each record represents 2 households in the full population
---

## Understanding Output Columns

### Count Columns

Summaries include weighted counts appropriate to the data source:

| Data Source | Count Column Name | Example Value |
|------------|------------------|---------------|
| households | `households` | 2,768,027 |
| persons | `persons` | 7,442,845 |
| individual_tours | `tours` | 12,345,678 |
| individual_trips | `trips` | 25,678,901 |

### Share Columns

Most summaries include a `share` column showing the proportion within each group:

```csv
tour_mode_name,tours,share
Drive Alone,5234567,0.425
Carpool 2,1987654,0.161
Walk-Transit-Walk,987654,0.080
...
```

Shares sum to 1.0 (or 100%) within each grouping level.

### Aggregation Columns

Some summaries include calculated statistics:

```csv
trip_distance_bin,trips,share,mean_distance,total_distance
<1mi,8234567,0.342,0.45,3705555
1-3mi,5632451,0.234,2.12,11940396
3-5mi,3456234,0.143,4.03,13928622
...
```

---

## Command Line Options

```bash
python summarize_model_run.py <ctramp_dir> [OPTIONS]
```

### Arguments

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `ctramp_dir` | Path to CTRAMP output directory | _(required)_ | `"A:/2015-tm22-dev/ctramp_output"` |
| `--output DIR` | Output directory for summaries | `outputs/` | `--output "my_results"` |
| `--strict` | Treat validation warnings as errors | `False` | `--strict` |

### Examples

```bash
# Basic usage
python summarize_model_run.py "C:/model_run/ctramp_output"

# Custom output location
python summarize_model_run.py "C:/model_run/ctramp_output" --output "results_2024"

# Strict validation mode
python summarize_model_run.py "C:/model_run/ctramp_output" --strict
```

---

## Validation

The tool automatically validates all summaries after generation. Validation checks for:

1. **Negative values** - Flags negative counts in non-negative fields
2. **Share totals** - Verifies shares sum to ~1.0 within groups (±0.5%)
3. **Zero totals** - Warns about suspiciously small totals (< 100)
4. **Statistical outliers** - Identifies extreme values using IQR method
5. **Logical consistency** - Domain-specific checks:
   - Auto ownership > 10 vehicles
   - Invalid time periods
   - Household size = 0 or > 15
   - Missing expected categories (age bins, etc.)

### Example Validation Output

```
VALIDATION SUMMARY
================================================================================
  Checked 30 summaries
  
  ✓ 25 summaries passed all checks
  ⚠ 5 summaries have warnings:
    - tour_distance_distribution: 2 outliers detected (expected in large datasets)
    - household_size_distribution: Maximum household size is 18 (valid but unusual)
    - trip_mode_by_purpose: 12 groups have shares not summing to 1.0 (rounding)
    
[OK] Validation passed with 5 warnings
```

Use `--strict` flag to fail on warnings:

```bash
python summarize_model_run.py "path/to/ctramp" --strict
# Exit code 1 if any warnings found
```

---

## Adding Custom Summaries

To add a new summary, edit `data_model/ctramp_data_model.yaml` and add to the `summaries:` section.

### Example: Trip Mode by Income

```yaml
summaries:
  # ... existing summaries ...
  
  trip_mode_by_income:
    description: "Trip mode distribution by income category"
    data_source: "individual_trips"
    group_by:
      - "income_category_bin"
      - "trip_mode_name"
    aggregations:
      trips:
        column: "trip_id"
        agg: "count"
```

Then run:

```bash
python summarize_model_run.py "path/to/ctramp_output"
```

The new summary `trip_mode_by_income.csv` will be generated automatically.

See [User Guide](user-guide.md) for detailed examples.

---

## Execution Log

The script provides detailed logging:

```
================================================================================
STEP 1: Loading Data Model Configuration
================================================================================
Reading: data_model/ctramp_data_model.yaml
[OK] Loaded configuration with 30 summary definitions

================================================================================
STEP 2: Loading CTRAMP Output Files
================================================================================
Source directory: A:\2015-tm22-dev-sprint-04\ctramp_output

Loading persons...
  File: personData_3.csv
  Rows: 7,442,845
  Columns: 21
  [OK] Loaded and standardized

Loading households...
  File: householdData_3.csv
  Rows: 2,768,027
  Columns: 12
  [OK] Loaded and standardized

================================================================================
STEP 3: Applying Value Labels
================================================================================
Processing persons:
  [OK] Labeled 'person_type' -> 'person_type_name' (8 values)
  [OK] Labeled 'cdap_activity' -> 'cdap_activity_name' (3 values)

================================================================================
STEP 4: Creating Aggregated Categories
================================================================================
Processing persons:
  [OK] Aggregated 'age' -> 'age_bin' (8 categories)

================================================================================
STEP 5: Binning Continuous Variables
================================================================================
Processing persons:
  [OK] Binned 'age' -> 'age_bin' (8 bins)

================================================================================
STEP 6: Generating Summaries
================================================================================
[1] auto_ownership_regional
    Source: households (2,768,027 rows)
  [OK] Saved: auto_ownership_regional.csv

[2] auto_ownership_by_income
    Source: households (2,768,027 rows)
  [OK] Saved: auto_ownership_by_income.csv

... (28 more summaries)

[OK] Generated 30 summaries in outputs/

================================================================================
STEP 7: Validation
================================================================================

VALIDATION SUMMARY
================================================================================
  Checked 30 summaries
  ✓ 25 summaries passed all checks
  ⚠ 5 summaries have warnings (outliers expected)
  
[OK] Validation passed with 5 warnings
```

---

## Troubleshooting

### File Not Found

```
[WARN] File not found matching pattern: wsLocResults.csv
```

**Cause:** Optional file missing (work/school location data)

**Solution:** This is normal if your model run doesn't include work location choice. Related summaries will be skipped.

### Column Not Found

```
KeyError: 'trip_mode'
```

**Cause:** Expected column missing from CTRAMP output

**Solutions:**
1. Check that files match expected CTRAMP format
2. Review column mappings in `data_model/ctramp_data_model.yaml`
3. Update YAML if your model uses different column names

### Empty Summaries

```
[WARN] person_type_distribution.csv: 0 rows (empty)
```

**Causes:**
- Missing required columns
- Data type mismatch (text vs. numeric)
- All values filtered out

**Solutions:**
1. Check validation output for specific errors
2. Verify data contains expected values
3. Review filter conditions in summary definition

### Memory Errors

For very large model runs (>10M persons):

**Solutions:**
1. Run on machine with more RAM (minimum 8 GB recommended)
2. Close other applications
3. Comment out some summaries in YAML to process fewer at once

### Unicode/Encoding Errors

The tool uses ASCII-safe symbols and should work on all Windows terminals. If you see encoding errors, check that your terminal supports UTF-8.

---

## Performance

**Typical runtime** for full Bay Area model (7.4M persons, 2.8M households):

- Loading data: ~2-3 minutes
- Labeling & preprocessing: ~1-2 minutes
- Generating summaries: ~3-5 minutes
- Validation: ~30 seconds
- **Total: ~7-11 minutes**

**Memory usage:** ~2-4 GB

**Tips to speed up:**
1. Use SSD storage for CTRAMP output files
2. Run with sufficient RAM (8+ GB recommended)
3. Comment out unneeded summaries in YAML

---

## Next Steps

- **Analyze summaries:** Use Excel, Python pandas, R, or BI tools
- **Analyze results:** Load CSVs into Excel, Python, R, or other tools for analysis
- **Add custom summaries:** Edit `ctramp_data_model.yaml` to add new analyses
- **Validate data quality:** Review validation warnings and investigate issues

See also:
- [User Guide](user-guide.md) - Detailed user guide
- [README.md](../summary/validation/README.md) - Toolkit overview
- [PREPROCESSING_NOTES.md](../summary/validation/PREPROCESSING_NOTES.md) - Advanced summaries requiring preprocessing

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
