# Summary Generation System

The tm2py-utils summary system generates aggregated statistics from CTRAMP model outputs for validation and comparison.

## Overview

The system provides:
- **34 configured summaries** (21 core + 13 validation)
- **Config-driven** - Add summaries via YAML, no Python coding
- **Flexible filtering** - Generate core, validation, or all summaries
- **Multiple output formats** - CSV, Parquet

## Quick Start

### View Configured Summaries

```bash
cd tm2py_utils/summary/validation
python list_summaries.py
```

### Generate All Summaries

```bash
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml
```

### Generate Core Summaries Only

Edit `validation_config.yaml`:
```yaml
generate_summaries: "core"
```

Then run:
```bash
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml
```

## Summary Types

### Core Summaries (21)
Essential analysis matching legacy `core_summaries.py` outputs:

**Households:**
- Auto ownership (regional, by income)

**Activity Patterns (CDAP):**
- Overall distribution
- By person type, age, county, auto ownership

**Tours:**
- Frequency by purpose
- Mode choice (overall and by purpose)
- Start/end times

**Trips:**
- Mode choice (overall and by purpose)
- Purpose distribution
- Mode by time period
- Distance and travel time (detailed)

**Commute:**
- Journey to work (distance/time by OD)
- Journey to work by mode

### Validation Summaries (13)
Extended analysis for detailed validation and dashboard:

**Households:**
- Auto ownership by household size
- Auto ownership by household size (ACS-comparable)
- Auto ownership by county

**Tours:**
- Mode choice (aggregated categories)
- Mode by purpose (aggregated)
- Distance distribution (binned)
- Duration distribution (binned)

**Trips:**
- Mode choice (aggregated categories)
- Mode by purpose (aggregated)
- Departure time distribution
- Distance distribution (binned)
- Duration distribution (binned)

## Configuration

### Setting Summary Filter

Edit `validation_config.yaml`:

```yaml
# Options: "all", "core", "validation"
generate_summaries: "core"
```

### Adding Custom Summaries

Add to `custom_summaries` section in `validation_config.yaml`:

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

Summaries are written to `outputs/` directory:

```
outputs/
├── auto_ownership_regional.csv
├── tour_mode_choice.csv
├── trip_distance.csv
└── ...
```

### CSV Format

Example output:

```csv
tour_mode,tours,share,dataset
Drive Alone,450000,42.5,2023 TM2.2 v05
Carpool,180000,17.0,2023 TM2.2 v05
Transit,95000,9.0,2023 TM2.2 v05
...
```

## Deployment Workflow

### Using the Deployment Script

```bash
cd tm2py_utils/summary/validation

# Generate all summaries and copy to dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml

# Generate only core summaries
python run_and_deploy_dashboard.py --config validation_config.yaml --summaries core

# Generate and launch dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
```

### Using Batch Script (Windows)

Double-click `deploy_dashboard.bat` for interactive menu:

1. Generate ALL summaries
2. Generate CORE summaries only
3. Generate VALIDATION summaries only
4. Copy existing summaries (skip generation)
5. Generate and LAUNCH dashboard

### Manual Steps

```bash
# 1. Generate summaries
python -m tm2py_utils.summary.validation.summaries.run_all \
  --config validation_config.yaml

# 2. Copy to dashboard folder
cp outputs/*.csv outputs/dashboard/

# 3. Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
```

## Data Model

Column mappings are defined in `data_model/ctramp_data_model.yaml`:

```yaml
individual_trips:
  file_pattern: "indivTripData_{iteration}.csv"
  columns:
    trip_mode: "trip_mode"
    tour_purpose: "tour_purpose"
    trip_distance: "trip_distance_miles"
    depart_period: "depart_period"
```

Variable labels in `variable_labels.yaml`:

```yaml
trip_mode: "Trip Mode"
tour_purpose: "Tour Purpose"
income_category_bin: "Income Category"
```

## Performance

Typical runtimes on a standard laptop:

- **Core summaries only**: ~5-10 minutes
- **All summaries**: ~15-20 minutes
- **Memory usage**: ~2-4 GB

For large model runs, consider:
- Generating core summaries only for quick checks
- Running full validation suite overnight

## Troubleshooting

### No summaries generated

Check that input directories in `validation_config.yaml` exist and contain CTRAMP output files:
- `indivTripData_1.csv`
- `householdData_1.csv`
- `indivTourData_1.csv`
- etc.

### Column not found errors

Check `ctramp_data_model.yaml` for correct column mappings.

### Memory errors

Reduce the number of input directories or process one at a time.

### Wrong summaries generated

Run `python list_summaries.py` to see what will be generated based on current config.

## Next Steps

- [Configure Dashboard](dashboard.md) to visualize summaries
- [Customize Configuration](configuration.md) for your analysis needs
- See [Consolidation Proposal](../summary/CONSOLIDATION_PROPOSAL.md) for system architecture
