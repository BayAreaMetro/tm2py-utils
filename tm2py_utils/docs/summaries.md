# Summary Generation System

The tm2py-utils summary system generates aggregated statistics from CTRAMP model outputs for validation.

## Overview

The system provides:
- **30 configured summaries** - All defined in `ctramp_data_model.yaml`
- **Config-driven** - Add summaries by editing YAML, no Python coding required
- **Simple & transparent** - One tool, clear logging, easy to understand
- **Automatic validation** - Built-in quality checks for data issues

## Quick Start

### Generate Summaries for One Model Run

```bash
cd tm2py_utils/summary/validation
python summarize_model_run.py "C:/path/to/ctramp_output"
```

This creates CSV summaries in `outputs/` and automatically validates them.

### Specify Custom Output Directory

```bash
python summarize_model_run.py "C:/path/to/ctramp_output" --output "my_results"
```

### View Available Summaries

Check `data_model/ctramp_data_model.yaml` to see all 30 summary definitions with documentation.

## Summary Types

**Household Summaries:**
- Auto ownership (regional, by income, by household size)

**Person & Activity Patterns:**
- Person type distribution
- Age distribution
- CDAP patterns (by person type, regional)

**Tour Summaries:**
- Tour frequency by purpose
- Tour mode choice (overall and by purpose)
- Tour distance distributions
- Time of day patterns

**Trip Summaries:**
- Trip mode choice (overall and by purpose)
- Trip purpose distribution
- Trip distance and duration distributions

**Work/School Location:**
- Average commute distance
- Journey to work patterns

See `data_model/ctramp_data_model.yaml` for complete list and definitions.

## Adding Custom Summaries

Edit `data_model/ctramp_data_model.yaml` and add to the `summaries:` section:

```yaml
custom_summaries:
  - name: "my_new_summary"
    summary_type: "validation"  # or "core"
    description: "What this summarizes"
    data_source: "individual_trips"  # or households, tours, persons, etc.
    group_by: ["trip_mode", "tour_purpose"]
    weight_field: "sample_rate"
    count_name: "trips"
    share_within: "tour_purpose"  # Calculate shares within groups
```

### Available Data Sources

- `households` - Household-level data
- `persons` - Person-level data
- `individual_tours` - Tour-level data
- `individual_trips` - Trip-level data
- `workplace_school` - Work/school location choice

### Aggregation Options

**Simple count:**
```yaml
group_by: "trip_mode"
count_name: "trips"
```

**Multiple aggregations:**
```yaml
group_by: ["income_category_bin", "trip_mode"]
aggregations:
  trips: "count"
  avg_distance: {"column": "trip_distance_miles", "agg": "mean"}
  total_time: {"column": "trip_time_minutes", "agg": "sum"}
```

**Share calculations:**
```yaml
group_by: ["tour_purpose", "tour_mode"]
share_within: "tour_purpose"  # Each purpose sums to 100%
```

### Binning Continuous Variables

```yaml
group_by: ["income_category_bin", "trip_mode"]
bins:
  income_category:
    breaks: [0, 30000, 60000, 100000, 150000, 1000000000]
    labels: ['<30K', '30-60K', '60-100K', '100-150K', '150K+']
```

## Output Files

Summaries are written to the specified output directory (default: `outputs/`):

```
outputs/
├── auto_ownership_regional.csv
├── tour_mode_choice.csv
├── trip_distance_distribution.csv
├── person_type_distribution.csv
└── ...
```

### CSV Format

Example `tour_mode_choice.csv`:

```csv
tour_mode_name,tours,share
Drive Alone,450000,0.425
Carpool 2,180000,0.170
Walk-Transit-Walk,95000,0.090
...
```

## Validation

Summaries are automatically validated after generation. The validator checks for:

- **Negative values** in count/share fields
- **Share totals** not summing to ~1.0 within groups
- **Zero or very small totals** (< 100)
- **Statistical outliers** using IQR method
- **Logical consistency** (invalid time periods, impossible household sizes, etc.)

Results are displayed at the end of the run:

```
VALIDATION SUMMARY
================================================================================
  ✓ 25 summaries passed all checks
  ⚠ 5 summaries have warnings (outliers expected in large datasets)
  
[OK] Validation passed with 5 warnings
```

Use `--strict` mode to treat warnings as errors:

```bash
python summarize_model_run.py "C:/path/to/ctramp_output" --strict
```

### Available Data Sources

Check `data_model/ctramp_data_model.yaml` for complete list:
- `households` - Household-level data
- `persons` - Person-level data  
- `individual_tours` - Tour-level data
- `individual_trips` - Trip-level data
- `joint_tours` - Joint tour data
- `workplace_school_location` - Work/school location choice

### Aggregation Examples

**Simple count:**
```yaml
auto_ownership_regional:
  description: "Regional auto ownership"
  data_source: "households"
  group_by: "num_vehicles"
  aggregations:
    households:
      column: "household_id"
      agg: "count"
```

**Multiple aggregations with mean/sum:**
```yaml
trip_distance_by_mode:
  description: "Trip distance statistics by mode"
  data_source: "individual_trips"
  group_by: "trip_mode_name"
  aggregations:
    trips:
      column: "trip_id"
      agg: "count"
    mean_distance:
      column: "trip_distance_miles"
      agg: "mean"
    total_distance:
      column: "trip_distance_miles"
      agg: "sum"
```

## Data Model

The system uses `data_model/ctramp_data_model.yaml` which defines:

1. **File patterns** - How to find CTRAMP output files
2. **Column mappings** - Standardized column names
3. **Value labels** - Mode 1 → "SOV_GP", etc.
4. **Aggregations** - Group modes into categories
5. **Binning specs** - Age groups, distance bins, etc.
6. **Summary definitions** - All 30 summaries

Example column mapping:

```yaml
individual_trips:
  file_pattern: "indivTripData_{iteration}.csv"
  columns:
    trip_mode: "trip_mode"
    tour_purpose: "tour_purpose"
    trip_distance_miles: "trip_distance_miles"
    depart_period: "depart_period"
```

Example value mapping:

```yaml
value_mappings:
  trip_mode:
    type: categorical
    values:
      1: "SOV_GP"
      2: "SOV_PAY"
      3: "SR2_GP"
      # ... etc
```

## Performance

Typical runtime for a full model run (7.4M persons, 2.8M households):

- **Loading data**: ~2-3 minutes
- **Labeling & preprocessing**: ~1-2 minutes  
- **Generating summaries**: ~3-5 minutes
- **Validation**: ~30 seconds
- **Total**: ~7-11 minutes

Memory usage: ~2-4 GB

## Troubleshooting

### File not found errors

Check that your CTRAMP output directory contains the expected files:
- `personData_3.csv` (or `personData_1.csv` depending on iteration)
- `householdData_3.csv`
- `indivTourData_3.csv`
- `indivTripData_3.csv`

### Column not found errors

Check `data_model/ctramp_data_model.yaml` for correct column mappings. If your model uses different column names, update the YAML.

### Empty summaries

Check validation output - this usually means:
- Incorrect filter conditions
- Missing required columns
- Data type mismatches (text vs. numeric)

### Memory errors

For very large model runs (> 10M persons), consider:
- Processing on a machine with more RAM
- Closing other applications
- Running fewer summaries at once (comment out some in YAML)

## Comparing Multiple Runs

To analyze multiple model runs:

1. Generate summaries for each run in separate output directories:
   ```bash
   python summarize_model_run.py "run1/ctramp_output" --output "outputs/run1"
   python summarize_model_run.py "run2/ctramp_output" --output "outputs/run2"
   ```

2. Load and analyze the CSVs using Excel, Python (pandas), R, or other analysis tools

## Next Steps

- See [HOW_TO_SUMMARIZE.md](../summary/validation/HOW_TO_SUMMARIZE.md) for detailed user guide
- Check [README.md](../summary/validation/README.md) for toolkit overview
- Review [data_model/ctramp_data_model.yaml](../summary/validation/data_model/ctramp_data_model.yaml) for all summary definitions
