# How to Summarize a Model Run

This guide explains how to generate validation summaries from a CTRAMP model run output directory.

## Quick Start

Run one command pointing to your CTRAMP output directory:

```bash
python summarize_model_run.py "C:/model_runs/2015_base/ctramp_output"
```

This creates a `summaries/` directory with CSV files for each summary (auto ownership, tour mode, trip distance, etc.).

## What You Need

1. **CTRAMP Output Directory** - Contains CSV files from your model run:
   - `householdData_1.csv` (or `_2.csv`, `_3.csv` for later iterations)
   - `personData_1.csv`
   - `indivTourData_1.csv`
   - `indivTripData_1.csv`

2. **Python Environment** with pandas and PyYAML installed

The tool automatically finds the highest iteration number if you have multiple (`_1.csv`, `_2.csv`, `_3.csv`).

## Command-Line Options

### Basic Usage

```bash
python summarize_model_run.py <ctramp_dir>
```

Example:
```bash
python summarize_model_run.py "A:/2023-tm22-dev-version-05/ctramp_output"
```

### Specify Output Directory

```bash
python summarize_model_run.py <ctramp_dir> --output <output_dir>
```

Example:
```bash
python summarize_model_run.py "A:/2023-tm22-dev-version-05/ctramp_output" --output "C:/summaries/2023_v05"
```

### Specify Data Model Configuration

```bash
python summarize_model_run.py <ctramp_dir> --config <config_file>
```

**Use this when you need a different data model:**

```bash
# TM1 model or BATS survey (default - no flag needed)
python summarize_model_run.py "M:/Model_One/OUTPUT/ctramp_csv"

# TM2 model (requires explicit config)
python summarize_model_run.py "M:/Model_Two/OUTPUT/ctramp" --config data_model/tm2_data_model.yaml

# Custom config for specialized analysis
python summarize_model_run.py "E:/my_model/output" --config my_custom_config.yaml
```

**Available configs:**
- `ctramp_data_model.yaml` (default) - TM1 format, also works for BATS survey data
- `tm2_data_model.yaml` - TM2 format (when created)
- `survey_data_model.yaml` - Specialized survey config (when needed)

**The config file determines:**
- File naming patterns (e.g., `personData_1.csv` vs `personData.csv`)
- Geography system (TAZ vs MGRA)
- Time representation (hour vs period)
- Mode definitions (17 vs 21 modes)
- Available summaries

## What Happens When You Run It

The tool executes a simple 6-step pipeline with transparent logging:

### Step 1: Load Data Model Configuration
Reads the config file (default: `data_model/ctramp_data_model.yaml`, or specify with `--config`) which defines:
- **Metadata**: Model type (TM1/TM2/survey), version, description
- **File patterns**: How to find files (e.g., `personData_{iteration}.csv` vs `personData.csv`)
- **Column mappings**: Standardize column names (e.g., `hh_id` → `household_id`)
- **Value labels**: Human-readable labels (e.g., mode 1 → "SOV_GP")
- **Binning specs**: Group continuous variables (e.g., age → age groups)
- **Summary definitions**: What to calculate (30 summaries defined)

Example output:
```
Config File: ctramp_data_model.yaml
Data Model Type: tm1
Version: 1.0
Description: TM1 (Travel Model One) CTRAMP output format - also compatible with BATS survey data
```

### Step 2: Load CTRAMP Output Files
- Finds files matching patterns in your directory
- Uses highest iteration number if multiple exist
- Loads CSVs into memory
- Renames columns to standardized names

Example output:
```
Loading households...
  File: householdData_1.csv
  Rows: 2,611,046
  Columns: 15
  ✓ Loaded and standardized
```

### Step 3: Apply Value Labels
Creates human-readable columns (e.g., `person_type_name` from `person_type` codes):
- 1 → "Full-time worker"
- 2 → "Part-time worker"
- etc.

Example output:
```
persons:
  ✓ Labeled 'person_type' → 'person_type_name' (8 values)
  ✓ Labeled 'gender' → 'gender_name' (2 values)
```

### Step 4: Create Aggregated Categories
Simplifies detailed categories into broader groups:
- 17 transportation modes → 5 major categories (Auto-SOV, Auto-Shared, Transit, Active, TNC/Taxi, School Bus)
- Detailed household sizes → ACS-compatible categories (1, 2, 3, 4+)

Example output:
```
individual_tours:
  ✓ Aggregated 'tour_mode' → 'tour_mode_agg' (5 categories)
```

### Step 5: Create Binned Variables
Converts continuous variables to categorical bins:
- Age → age groups (0-4, 5-17, 18-24, 25-34, ...)
- Distance → distance bands (0-5mi, 5-10mi, 10-20mi, ...)
- Income → income categories (<30K, 30-60K, 60-100K, ...)

Example output:
```
persons:
  ✓ Binned 'age' → 'age_bin' (8 bins)
individual_tours:
  ✓ Binned 'tour_distance' → 'tour_distance_bin' (5 bins)
```

### Step 6: Generate Summaries
Creates weighted frequency tables and saves as CSV files.

Example output:
```
[1] auto_ownership_regional
  Source: households (2,611,046 rows)
  Result: 7 rows × 2 columns
  ✓ Saved: auto_ownership_regional.csv

[2] tour_mode_distribution
  Source: individual_tours (11,234,982 rows)
  Result: 17 rows × 2 columns
  ✓ Saved: tour_mode_distribution.csv

Generated 23 summaries
```

## Output Files

Each summary is saved as a separate CSV file in the output directory.

Example outputs:

**auto_ownership_regional.csv:**
```csv
num_vehicles,households
0,423156.8
1,892341.2
2,945623.1
3,289432.7
4,52108.4
5,7284.2
6,1099.6
```

**tour_mode_by_purpose.csv:**
```csv
tour_purpose,tour_mode_name,tours,share
Work,SOV_GP - Single Occupant Vehicle (General Purpose),1823441.5,0.524
Work,SR2_GP - Shared Ride 2 (General Purpose),456782.3,0.131
Work,WLK_TRN - Walk to Transit,328901.2,0.094
...
```

## What Summaries Are Generated

The tool generates 23 standard summaries organized by category:

### Household Summaries
- `auto_ownership_regional.csv` - Vehicle ownership distribution
- `auto_ownership_by_income.csv` - Vehicles by income category
- `auto_ownership_by_household_size.csv` - Vehicles by household size
- `household_size_distribution.csv` - Household size distribution
- `worker_distribution.csv` - Workers per household

### Person Summaries
- `person_type_distribution.csv` - Person type distribution
- `age_distribution.csv` - Age distribution (binned)
- `cdap_by_person_type.csv` - Daily activity pattern by person type
- `cdap_regional.csv` - Regional daily activity patterns

### Tour Summaries
- `tour_frequency_by_purpose.csv` - Tours by purpose
- `tour_mode_distribution.csv` - Tour mode (all 17 modes)
- `tour_mode_aggregated.csv` - Tour mode (5 major categories)
- `tour_mode_by_purpose.csv` - Mode × Purpose cross-tab
- `tour_start_time.csv` - Departure time distribution
- `tour_end_time.csv` - Arrival time distribution
- `tour_distance_distribution.csv` - Distance distribution (binned)

### Trip Summaries
- `trip_purpose_distribution.csv` - Trip destination purposes
- `trip_mode_distribution.csv` - Trip mode (all 17 modes)
- `trip_mode_aggregated.csv` - Trip mode (5 major categories)
- `trip_mode_by_purpose.csv` - Mode × Purpose cross-tab
- `trip_distance_distribution.csv` - Distance distribution (binned)

## Adding New Summaries

You don't need to write Python code to add summaries! Just edit the YAML configuration.

### Example: Add a new summary for tours by person type

Edit `data_model/ctramp_data_model.yaml` and add to the `summaries:` section:

```yaml
summaries:
  # ... existing summaries ...
  
  tours_by_person_type:
    description: "Number of tours by person type"
    data_source: "individual_tours"
    group_by: "person_type_name"
    weight_field: "sample_rate"
    count_name: "tours"
```

That's it! Next time you run the tool, it will generate `tours_by_person_type.csv`.

### Example: Add filtered summary (work tours only)

```yaml
  work_tour_modes:
    description: "Mode choice for work tours only"
    data_source: "individual_tours"
    filter: "tour_purpose == 'Work'"
    group_by: "tour_mode_name"
    weight_field: "sample_rate"
    count_name: "tours"
```

### Example: Calculate shares within categories

```yaml
  mode_by_income:
    description: "Tour mode choice by household income (with shares)"
    data_source: "individual_tours"
    group_by: ["income_category_bin", "tour_mode_agg"]
    weight_field: "sample_rate"
    count_name: "tours"
    share_within: "income_category_bin"  # This adds a 'share' column
```

## Summary Configuration Reference

Each summary definition supports these fields:

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `description` | No | Human-readable description | `"Vehicle ownership by income"` |
| `data_source` | Yes | Which table to use | `"households"`, `"persons"`, `"individual_tours"`, `"individual_trips"` |
| `group_by` | Yes | Column(s) to group by | `"num_vehicles"` or `["income_category", "num_vehicles"]` |
| `weight_field` | No | Column with sampling weights | `"sample_rate"` |
| `count_name` | No | Name for count column in output | `"households"`, `"tours"`, `"trips"` (default: `"count"`) |
| `share_within` | No | Calculate shares within these groups | `"income_category"` or `["county", "income"]` |
| `filter` | No | Pandas query to filter data | `"tour_purpose == 'Work'"` or `"age >= 18"` |

## Understanding the Data Flow

```
CTRAMP CSV Files
       ↓
   Load Data (Step 2)
       ↓
householdData_1.csv  →  households dataframe (standardized columns)
personData_1.csv     →  persons dataframe
indivTourData_1.csv  →  individual_tours dataframe
indivTripData_1.csv  →  individual_trips dataframe
       ↓
   Apply Value Labels (Step 3)
       ↓
person_type: 1,2,3... → person_type_name: "Full-time worker", "Part-time worker", ...
tour_mode: 1,2,3...   → tour_mode_name: "SOV_GP", "SR2_GP", "WALK", ...
       ↓
   Apply Aggregations (Step 4)
       ↓
tour_mode_name: 17 categories → tour_mode_agg: "Auto-SOV", "Auto-Shared", "Transit", ...
num_persons: 1,2,3,4,5,6...   → num_persons_agg: "1", "2", "3", "4+"
       ↓
   Apply Binning (Step 5)
       ↓
age: 0-100          → age_bin: "0-4", "5-17", "18-24", "25-34", ...
tour_distance: 0-50 → tour_distance_bin: "0-5mi", "5-10mi", "10-20mi", ...
       ↓
   Generate Summaries (Step 6)
       ↓
For each summary definition:
  - Filter data if specified
  - Group by specified columns
  - Apply sample_rate weights
  - Calculate shares if requested
  - Save to CSV
       ↓
Individual CSV Files (one per summary)
```

## Troubleshooting

### File Not Found Errors

**Problem:** `File not found matching pattern: personData_{iteration}.csv`

**Solution:** 
- Check that your CTRAMP directory path is correct
- Verify files exist: `ls <ctramp_dir>/*.csv`
- Check file naming - should be `personData_1.csv` (or `_2.csv`, `_3.csv`)

### Column Not Found Errors

**Problem:** `KeyError: 'tour_mode_agg'`

**Solution:** This column is created in Step 4 (aggregations). Make sure:
- The data model has the aggregation defined
- The source column (`tour_mode`) exists in the data
- The aggregation mapping is valid

### Empty Output

**Problem:** Summary CSV files are created but have no data

**Solution:**
- Check if filter is too restrictive (`filter: "tour_purpose == 'InvalidValue'"`)
- Verify group_by columns exist in the data
- Check if weight_field exists (if specified)

### Memory Errors

**Problem:** `MemoryError` when loading large files

**Solution:**
- Process data in chunks (would require code modification)
- Use a machine with more RAM
- Sample the data first for testing

## For Developers

If you need to modify the tool's behavior, see `summarize_model_run.py`.

The code is structured as simple functions in a clear sequence:
1. `load_data_model()` - Read YAML config
2. `load_ctramp_data()` - Load and standardize CSV files
3. `apply_value_labels()` - Create _name columns
4. `apply_aggregations()` - Create _agg columns
5. `apply_bins()` - Create _bin columns
6. `generate_summary()` - Group, weight, calculate shares
7. `generate_all_summaries()` - Loop through all summary configs

Total code: ~350 lines with extensive comments and logging.

## Next Steps

After generating summaries:

1. **Inspect the CSVs** - Open in Excel or pandas to verify results
2. **Compare across scenarios** - Use simple pandas scripts to compare CSVs from different runs
3. **Visualize** - Create plots, dashboards, or reports from the summary CSVs
4. **Validate** - Compare to observed data (ACS, surveys, etc.)

The summaries are simple CSV files - use them however you like!
