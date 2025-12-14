# Configuration Reference

Complete reference for `ctramp_data_model.yaml` and related configuration files used by the new validation toolkit.

## Overview

The new validation system uses **YAML configuration files** to define:
- Data file patterns and column mappings
- Value labels (mode codes → mode names)
- Aggregation rules (17 modes → 5 categories)
- Binning specifications (age → age groups)
- Summary definitions (what to generate)

**Main configuration file:** `data_model/ctramp_data_model.yaml`

No Python coding required - just edit YAML to customize summaries.

---

## ctramp_data_model.yaml

Location: `tm2py_utils/summary/validation/data_model/ctramp_data_model.yaml`

### File Structure

```yaml
# 1. Data source definitions
data_sources:
  persons:
    file_pattern: "personData_{iteration}.csv"
    columns:
      person_id: "person_id"
      household_id: "hh_id"
      # ... more columns

# 2. Value mappings (codes to labels)
value_mappings:
  trip_mode:
    type: categorical
    values:
      1: "SOV_GP"
      2: "SOV_PAY"
      # ... more values

# 3. Aggregation rules
aggregation_specs:
  trip_mode_agg:
    source_column: "trip_mode"
    mapping:
      "SOV_GP": "Auto"
      "SOV_PAY": "Auto"
      # ... more mappings

# 4. Binning specifications
binning_specs:
  age:
    breaks: [0, 5, 18, 25, 35, 45, 55, 65, 120]
    labels: ['0-4', '5-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']

# 5. Summary definitions
summaries:
  auto_ownership_regional:
    description: "Regional auto ownership distribution"
    data_source: "households"
    # ... more settings
```

---

## Data Sources

Define how to find and load CTRAMP output files.

### Structure

```yaml
data_sources:
  source_name:
    file_pattern: "fileName_{iteration}.csv"
    columns:
      standardized_name: "ctramp_column_name"
```

### Example

```yaml
data_sources:
  individual_trips:
    file_pattern: "indivTripData_{iteration}.csv"
    columns:
      trip_id: "trip_id"
      trip_mode: "trip_mode"
      tour_purpose: "tour_purpose"
      trip_distance_miles: "trip_distance_miles"
      depart_period: "depart_period"
```

The `{iteration}` placeholder is replaced automatically (e.g., `_1`, `_3`).

### Available Data Sources

| Source Name | File Pattern | Description |
|------------|-------------|-------------|
| `persons` | `personData_{iteration}.csv` | Person-level data |
| `households` | `householdData_{iteration}.csv` | Household-level data |
| `individual_tours` | `indivTourData_{iteration}.csv` | Individual tour data |
| `individual_trips` | `indivTripData_{iteration}.csv` | Individual trip data |
| `joint_tours` | `jointTourData_{iteration}.csv` | Joint tour data |
| `workplace_school_location` | `wsLocResults.csv` | Work/school location |

---

## Value Mappings

Map numeric codes to human-readable labels.

### Categorical Mappings

**Numeric to text:**
```yaml
value_mappings:
  trip_mode:
    type: categorical
    values:
      1: "SOV_GP"      # Drive alone, general purpose lanes
      2: "SOV_PAY"     # Drive alone, toll lanes
      3: "SR2_GP"      # Carpool 2, general purpose
      4: "SR2_HOV"     # Carpool 2, HOV lanes
      5: "SR2_PAY"     # Carpool 2, toll lanes
      # ... more values
```

**Text values (already labeled):**

```yaml
value_mappings:
  person_type:
    type: categorical
    text_values:
      - "Full-time worker"
      - "Part-time worker"
      - "University student"
      - "Non-worker"
      # ... more values
```

The system auto-detects numeric vs. text and applies the appropriate mapping.

### Common Value Mappings

**Trip/Tour Modes:**
- 1-17: Different mode combinations (SOV, HOV, Transit, Walk, Bike, etc.)

**Tour Purpose:**
- Work, University, School, Escort, Shopping, Maintenance, Eating Out, Visiting, Discretionary, Work-Based

**Person Type:**
- Full-time worker, Part-time worker, University student, Non-worker, Retired, Student (high school), Student (grade school), Pre-school

**CDAP Activity:**
- Mandatory, Non-mandatory, Home

---

## Aggregation Specs

Group detailed categories into broader categories.

### Structure

```yaml
aggregation_specs:
  new_column_name:
    source_column: "original_column"
    mapping:
      "original_value_1": "new_category"
      "original_value_2": "new_category"
      "original_value_3": "different_category"
```

### Example: Mode Aggregation

```yaml
aggregation_specs:
  trip_mode_agg:
    source_column: "trip_mode_name"
    mapping:
      "SOV_GP": "Auto"
      "SOV_PAY": "Auto"
      "SR2_GP": "Auto"
      "SR2_HOV": "Auto"
      "SR2_PAY": "Auto"
      "SR3_GP": "Auto"
      "SR3_HOV": "Auto"
      "SR3_PAY": "Auto"
      "Walk-Transit-Walk": "Transit"
      "Walk-Transit-Drive": "Transit"
      "Drive-Transit-Walk": "Transit"
      "Drive-Transit-Drive": "Transit"
      "Walk": "Active"
      "Bike": "Active"
      "School Bus": "School Bus"
```

This creates a new column `trip_mode_agg` with 5 categories instead of 17.

---

## Binning Specs

Convert continuous variables into categorical bins.

### Structure

```yaml
binning_specs:
  column_name:
    breaks: [0, 10, 20, 30, 100]     # Bin edges
    labels: ['0-10', '10-20', '20-30', '30+']  # Bin labels
```

### Example: Age Bins

```yaml
binning_specs:
  age:
    breaks: [0, 5, 18, 25, 35, 45, 55, 65, 120]
    labels: ['0-4', '5-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']
```

Creates a new column `age_bin` with 8 age groups.

### Example: Distance Bins

```yaml
binning_specs:
  trip_distance_miles:
    breaks: [0, 1, 3, 5, 10, 50, 1000]
    labels: ['<1mi', '1-3mi', '3-5mi', '5-10mi', '10-50mi', '50+mi']
```

**Note:** Number of labels must equal number of breaks minus 1.

---

## Summary Definitions

Define what summaries to generate.

### Basic Structure

```yaml
summaries:
  summary_name:
    description: "What this summary shows"
    data_source: "individual_trips"   # Which data table
    group_by: "trip_mode_name"        # Column(s) to group by
    aggregations:                      # What to calculate
      trips:
        column: "trip_id"
        agg: "count"
```

### Examples

**Simple count:**

```yaml
summaries:
  auto_ownership_regional:
    description: "Regional auto ownership distribution"
    data_source: "households"
    group_by: "num_vehicles"
    aggregations:
      households:
        column: "household_id"
        agg: "count"
```

**Cross-tabulation:**

```yaml
summaries:
  auto_ownership_by_income:
    description: "Auto ownership by income category"
    data_source: "households"
    group_by:
      - "income_category_bin"
      - "num_vehicles"
    aggregations:
      households:
        column: "household_id"
        agg: "count"
```

**With multiple aggregations:**

```yaml
summaries:
  trip_distance_distribution:
    description: "Trip distance statistics"
    data_source: "individual_trips"
    group_by: "trip_distance_bin"
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

**With filters:**

```yaml
summaries:
  work_tour_mode:
    description: "Work tour mode choice"
    data_source: "individual_tours"
    group_by: "tour_mode_name"
    filters:
      tour_purpose_name: ["Work"]
    aggregations:
      tours:
        column: "tour_id"
        agg: "count"
```

### Available Aggregation Functions

| Function | Description | Example Use |
|----------|-------------|-------------|
| `count` | Count rows | Number of trips/tours/households |
| `sum` | Sum values | Total distance traveled |
| `mean` | Average | Average trip distance |
| `median` | Median value | Median income |
| `min` | Minimum | Shortest trip |
| `max` | Maximum | Longest trip |
| `std` | Standard deviation | Distance variability |

---

## Command Line Usage

Generate summaries using the configured YAML:

```bash
cd tm2py_utils/summary/validation
python summarize_model_run.py "C:/path/to/ctramp_output"
```

Options:

```bash
python summarize_model_run.py <ctramp_dir> [--output DIR] [--strict]
```

| Option | Description | Default |
|--------|-------------|---------|
| `ctramp_dir` | CTRAMP output directory | _(required)_ |
| `--output DIR` | Output directory | `outputs/` |
| `--strict` | Treat warnings as errors | `False` |

---

## File Locations

```
tm2py_utils/summary/validation/
├── summarize_model_run.py          # Main tool
├── validate_summaries.py           # Validation tool
├── data_model/
│   ├── ctramp_data_model.yaml     # MAIN CONFIG - Edit this!
│   ├── variable_labels.yaml        # Display labels
│   └── ctramp_data_model_loader.py # Helper functions
├── outputs/                         # Generated summaries
│   ├── auto_ownership_regional.csv
│   ├── tour_mode_choice.csv
│   └── ...
└── HOW_TO_SUMMARIZE.md             # User guide
```

---

## Quick Reference

### Add a New Summary

1. Edit `data_model/ctramp_data_model.yaml`
2. Add to `summaries:` section:
   ```yaml
   my_new_summary:
     description: "What this shows"
     data_source: "individual_trips"
     group_by: "column_name"
     aggregations:
       trips:
         column: "trip_id"
         agg: "count"
   ```
3. Run: `python summarize_model_run.py "path/to/ctramp"`

### Add a Column Mapping

Edit `data_model/ctramp_data_model.yaml`, find the data source, add column:

```yaml
data_sources:
  individual_trips:
    columns:
      my_new_column: "ctramp_column_name"
```

### Add a Value Label

Edit `data_model/ctramp_data_model.yaml`, add to `value_mappings`:

```yaml
value_mappings:
  my_column:
    type: categorical
    values:
      1: "Label 1"
      2: "Label 2"
```

### Create an Aggregation

Edit `data_model/ctramp_data_model.yaml`, add to `aggregation_specs`:

```yaml
aggregation_specs:
  my_column_agg:
    source_column: "my_column_name"
    mapping:
      "Value 1": "Category A"
      "Value 2": "Category A"
      "Value 3": "Category B"
```

### Define Bins

Edit `data_model/ctramp_data_model.yaml`, add to `binning_specs`:

```yaml
binning_specs:
  my_numeric_column:
    breaks: [0, 10, 20, 30, 100]
    labels: ['0-10', '10-20', '20-30', '30+']
```

---

## See Also

- [HOW_TO_SUMMARIZE.md](../summary/validation/HOW_TO_SUMMARIZE.md) - Complete user guide with examples
- [README.md](../summary/validation/README.md) - Toolkit overview
- [summaries.md](summaries.md) - Summary system documentation
- [generate-summaries.md](generate-summaries.md) - Detailed generation guide
