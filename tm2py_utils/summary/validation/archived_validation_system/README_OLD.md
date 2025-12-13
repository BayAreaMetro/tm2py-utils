# TM2.2 Validation System

A flexible framework for generating validation summaries and interactive dashboards comparing multiple TM2.2 model runs.

## 🎯 Quick Start

```bash
# 1. Check configuration
python check_config.py

# 2. Generate summaries and deploy dashboard files
python run_and_deploy_dashboard.py --config validation_config.yaml

# 3. Validate dashboards (optional - checks for missing files)
python check_dashboards.py

# 4. Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
```

Visit http://localhost:8501

## 📖 Full Documentation

**Complete guide:** [Validation System Documentation](../../docs/validation-system.md)

The full documentation covers:
- Adding new model runs and datasets
- Creating custom summaries
- Dashboard configuration
- Troubleshooting and known limitations

## 📁 Directory Structure

```
validation/
├── README.md                      # This file - start here!
├── validation_config.yaml         # Configure datasets and summaries
├── check_config.py                # Quick validation check (run before generating)
├── run_and_deploy_dashboard.py   # Main workflow - generates summaries + deploys
│
├── summaries/                     # Summary generation code
│   ├── run_all.py                 # Core summary generation engine
│   ├── household_summary.py       # Household & auto ownership summaries
│   ├── tour_summary.py            # Tour frequency, mode, timing summaries
│   ├── trip_summary.py            # Trip mode, purpose, timing summaries
│   └── summary_utils.py           # Shared utility functions
│
├── data_model/                    # Data model configuration
│   ├── ctramp_data_model.yaml     # Column mappings, value mappings, binning
│   ├── ctramp_data_model_loader.py
│   └── variable_labels.yaml       # Display labels for dashboard
│
├── dashboard/                     # Dashboard configuration
│   ├── dashboard_app.py           # Streamlit application
│   ├── dashboard-*.yaml           # Dashboard tab configurations (8 tabs)
│   └── validation-app-banner.PNG  # Dashboard header image
│
└── outputs/                       # Generated files
    ├── *.csv                      # Per-dataset summary files
    ├── summary_index.csv          # Catalog of all generated summaries
    └── dashboard/                 # Dashboard-ready files
        ├── *.csv                  # Combined summary files (for multi-run comparison)
        └── dashboard-*.yaml       # Dashboard configs (copied here)
```

## 🔧 Key Files

### Configuration Files

- **validation_config.yaml** - Main configuration
  - `input_directories`: Model run paths
  - `custom_summaries`: List of summaries to generate (29 active)
  - Some summaries commented out due to missing columns (see docs)

- **dashboard-*.yaml** (8 files) - Dashboard tab configurations
  - dashboard-population.yaml
  - dashboard-households.yaml  
  - dashboard-activity-patterns.yaml
  - dashboard-tours.yaml
  - dashboard-trips.yaml
  - dashboard-commute.yaml ⚠️ (Coming soon - needs workplace_school data)
  - dashboard-time-of-day.yaml
  - dashboard-trip-characteristics.yaml

### Scripts

- **check_config.py** - Quick validation check
  - Verifies input directories exist
  - Checks YAML syntax
  - Counts configured summaries
  - Fast pre-flight check before running

- **check_dashboards.py** - Dashboard validation
  - Checks all dashboard YAML files are valid
  - Verifies all referenced CSV files exist
  - Detects missing columns in charts
  - Run after summary generation to catch issues

- **run_and_deploy_dashboard.py** - Main workflow
  - Calls `summaries/run_all.py` to generate all summaries
  - Creates both per-dataset AND combined CSV files
  - Copies files to `outputs/dashboard/`
  - Optional: `--launch-dashboard` to start Streamlit automatically

## 📊 How Summary Generation Works

The refactored architecture (as of Dec 2024) works as follows:

1. **Read data** from each configured input directory
2. **Generate summaries** for each dataset individually
3. **Save per-dataset files**: `summary_name_dataset_label.csv`
4. **Automatically combine** summaries across datasets
5. **Save combined files**: `summary_name.csv` (with `dataset` column)
6. **Copy all files** to `outputs/dashboard/` for dashboard use

### Example Output

```
outputs/
  cdap_by_share_2023 TM2.2 v05.csv       # Per-dataset file
  cdap_by_share_2015 TM2.2 Sprint 04.csv # Per-dataset file
  cdap_by_share.csv                      # Combined file (used by dashboard)
  
outputs/dashboard/
  (same files copied here for dashboard)
```

The **combined files** have a `dataset` column that the dashboard uses to create side-by-side comparisons.

## ⚙️ Architecture Changes (Recent)

**Major refactoring completed Dec 2024:**

- ✅ **Centralized combination logic** - Now happens in `save_summaries()` function
- ✅ **Removed dashboard categorization** - No more household/worker/tour/trip splits
- ✅ **Always generate combined files** - Both per-dataset and combined files created
- ✅ **Simplified dashboard** - References combined files directly

**Impact:**
- Cleaner code, less duplication
- Easier to add new summaries
- Dashboard configs simpler (just reference `summary_name.csv`)

## ⚠️ Known Limitations

Some summaries are commented out in `validation_config.yaml`:

| Summary | Issue | Required Fix |
|---------|-------|--------------|
| `cdap_by_age` | Needs `age_category` | Derive from `age` column |
| `cdap_by_home_county` | Needs `county_name` | Add household geography join |
| `cdap_by_auto_ownership` | Needs `num_vehicles` | Join household to person data |
| `journey_to_work` | `workplace_school` not loading | Fix wsLocResults.csv processing |
| `journey_to_work_by_mode` | `workplace_school` not loading | Fix wsLocResults.csv processing |

See [Troubleshooting](../../docs/validation-system.md#troubleshooting) in full docs for details.

## 🐛 Troubleshooting

### Dashboard shows "No data"

1. **Check if CSV exists:**
   ```bash
   ls outputs/dashboard/summary_name.csv
   ```

2. **Check CSV structure:**
   ```bash
   python -c "import pandas as pd; print(pd.read_csv('outputs/dashboard/summary_name.csv').columns)"
   ```

3. **Verify dashboard references correct file:**
   - Should reference combined file: `summary_name.csv`
   - NOT per-dataset file: `summary_name_2023 TM2.2 v05.csv`

4. **Run dashboard validation:**
   ```bash
   python check_dashboards.py
   ```

### Summary not generating

1. **Run validation check:**
   ```bash
   python check_config.py
   ```

2. **Check for missing columns:**
   - Review commented-out summaries in `validation_config.yaml`
   - Each has explanation of what's needed

3. **Check summary_index.csv:**
   ```bash
   cat outputs/dashboard/summary_index.csv | grep "summary_name"
   ```

## 🚀 Next Steps

1. **Review full documentation:** [validation-system.md](../../docs/validation-system.md)
2. **Understand configuration:** See examples in `validation_config.yaml`
3. **Add custom summaries:** Use template in `examples/custom_summary_template.yaml`
4. **Explore dashboard configs:** Look at `dashboard/dashboard-*.yaml` files

## 📧 Support

- **Issues:** https://github.com/BayAreaMetro/tm2py-utils/issues
- **Docs:** https://bayareametro.github.io/tm2py-utils/
- **Email:** modeling@bayareametro.gov
    iteration: 1
  
```

### Loading Pre-Aggregated Observed Data (Survey/ACS)

If you have **pre-aggregated summary tables** from surveys (ACS, BATS, CTPP) instead of raw records, use `observed_summaries`:

```yaml
observed_summaries:
  # ACS 2019 household data
  - name: "acs_2019"
    display_name: "ACS 2019"
    summaries:
      # Auto ownership summary
      auto_ownership_regional:
        file: "C:\\Data\\ACS_2019\\auto_ownership.csv"
        columns:
          num_vehicles: "Vehicles"      # Map CSV column "Vehicles" to standard "num_vehicles"
          households: "Households"
          share: "Percentage"
      
      # Household size summary  
      household_size_regional:
        file: "C:\\Data\\ACS_2019\\household_size.csv"
        columns:
          household_size: "HH_Size"
          households: "Count"
          share: "Pct"
  
  # BATS 2018 travel survey
  - name: "bats_2018"
    display_name: "BATS 2018"
    summaries:
      trip_mode_choice:
        file: "C:\\Data\\BATS_2018\\trip_modes.csv"
        columns:
          trip_mode: "Mode"
          trips: "Count"
          share: "Share"
```

**Key points:**
- Each summary file is a CSV with columns matching the standard summary output
- Use `columns` mapping to rename CSV columns to match expected names (e.g., `Vehicles` → `num_vehicles`)
- Summary names (e.g., `auto_ownership_regional`) must match model-generated summary names to appear on same chart
- The framework automatically adds the dataset identifier to enable model vs observed comparisons

**Required CSV format:**
- Pre-aggregated data (one row per category)
- Standard columns: group_by columns (e.g., `num_vehicles`, `trip_mode`), count columns (e.g., `households`, `trips`), `share` column
- No need for individual records or sample rates - data is already aggregated

### 2. Generate Summaries

```powershell
cd C:\GitHub\tm2py-utils
conda activate tm2py-utils
python -m tm2py_utils.summary.validation.summaries.run_all --config tm2py_utils\summary\validation\validation_config.yaml
```

This will:
- Load data from all configured datasets
- Apply sample rate weighting (expansion factors)
- Generate household, tour, and trip summaries
- Create dashboard-ready CSV files in `outputs/dashboard/`
- Generate dashboard YAML configurations

### 3. View Dashboard

```powershell
python -m tm2py_utils.summary.validation.dashboard.run_dashboard
```

Opens at http://localhost:8501

## 📊 Adding a New Summary

**✨ All summaries are configuration-driven - no Python coding required!**

### Add Summaries via YAML Configuration

All summaries (household, tour, trip, worker) are now defined in `validation_config.yaml` under `custom_summaries`. Simply add a new entry:

```yaml
custom_summaries:
  # Example 1: Simple distribution
  - name: "trips_by_origin_purpose"
    description: "Trip distribution by origin purpose"
    data_source: "individual_trips"  # households, individual_tours, individual_trips
    group_by: "orig_purpose"
    weight_field: "sample_rate"
    count_name: "trips"
  
  # Example 2: Cross-tab with within-group shares
  - name: "tours_by_purpose_and_mode"
    description: "Tour mode choice by purpose"
    data_source: "individual_tours"
    group_by: ["tour_purpose", "tour_mode"]
    weight_field: "sample_rate"
    count_name: "tours"
    share_within: "tour_purpose"  # Calculate % of each purpose using each mode
  
  # Example 3: Filtered analysis
  - name: "work_tours_by_start_hour"
    description: "Work tour departure time"
    data_source: "individual_tours"
    filter: "tour_purpose == 1"  # Work tours only
    group_by: "start_hour"
    weight_field: "sample_rate"
    count_name: "tours"
  
  # Example 4: Custom binning
  - name: "trips_by_distance_category"
    description: "Trip length distribution"
    data_source: "individual_trips"
    group_by: "trip_distance"
    weight_field: "sample_rate"
    count_name: "trips"
    bins:
      trip_distance:
        breaks: [0, 2, 5, 10, 20, 50, 999]
        labels: ["0-2mi", "2-5mi", "5-10mi", "10-20mi", "20-50mi", "50+mi"]
```

**Configuration Fields:**
- `name`: Unique identifier for the summary
- `description`: Human-readable description (shown in dashboard)
- `data_source`: Which table to use (`households`, `individual_tours`, `individual_trips`)
- `group_by`: Column(s) to group by (string or list)
- `weight_field`: Column containing expansion weights (e.g., `sample_rate`)
- `count_name`: Name for count column in output (e.g., `trips`, `tours`, `households`)
- `share_within`: (Optional) Calculate shares within groups for cross-tabs
- `filter`: (Optional) Python expression to filter data (e.g., `"tour_purpose == 1"`)
- `bins`: (Optional) Custom binning for continuous variables

**Benefits:**
- ✅ No Python coding required
- ✅ Fast to add new summaries
- ✅ Self-documenting
- ✅ Easy to version control
- ✅ Automatically generates CSV and dashboard configs
- ✅ **Automatic label mapping** - categorical codes (mode IDs, person types) are automatically converted to human-readable labels

**Current Configured Summaries (validation_config.yaml):**
- **Household**: auto ownership (regional, by income, by size), household size, income distribution
- **Tour**: frequency by purpose, mode choice, mode by purpose, start/end time, distance, duration
- **Trip**: mode choice, purpose, mode by purpose, departure time, distance, duration
- **Worker**: work location, telecommute frequency

**To modify or remove** existing summaries, edit the `custom_summaries` section in `validation_config.yaml`.

### Advanced: Custom Python Summaries

For complex aggregations not supported by config (e.g., calculated fields, complex joins):

1. Add function to `summaries/household_summary.py`, `tour_summary.py`, or `trip_summary.py`
2. Use `calculate_weighted_summary()` utility
3. Call from main generator function

But try config-driven first - it supports filtering, binning, cross-tabs, and within-group shares!

## 🎨 Customizing the Dashboard

### Add a New Chart

1. **Find the dashboard YAML:** `outputs/dashboard/dashboard-3-tours.yaml` (or relevant file)

2. **Add chart configuration:**
   ```yaml
   my_section:
     - type: bar
       title: My New Chart Title
       props:
         dataset: my_summary.csv      # CSV file name
         x: my_column                 # X-axis column
         y: count                     # Y-axis column
         groupBy: dataset             # Group/color by dataset
         stacked: true                # Optional: stack bars
       description: 'Description of what this shows'
   ```

3. **Supported chart properties:**
   - `dataset`: CSV filename in outputs/dashboard/
   - `x`: Column for x-axis
   - `y`: Column for y-axis (counts or shares)
   - `columns`: Column to use for colors/stacking
   - `groupBy`: Column to group by (usually 'dataset')
   - `stacked`: true/false for stacked bars
   - `facet_col`: Column to create subplots

4. **Refresh dashboard** - it will auto-detect new YAML configurations

### Customize Chart Labels

Edit `data_model/variable_labels.yaml`:

```yaml
# Variable display names
my_column: "My Column Display Name"
my_other_column: "Another Display Name"

# Category ordering
categorical_order:
  my_column:
    - "Category 1"
    - "Category 2"
    - "Category 3"
```

## 🔧 Configuration Files

### validation_config.yaml
- **datasets**: Define datasets to analyze (model outputs, observed data, or survey data)
- **dataset_order**: Control order in dashboard
- **output_directory**: Where to save summaries (default: outputs/)
- **enabled_summaries**: Which summaries to generate

### data_model/ctramp_data_model.yaml

**Core configuration for data structure and value mappings.**

- **input_schema**: Define expected CSV columns and data types for your data
- **column_mappings**: Map CSV column names to standard names
- **value_mappings**: Map coded values to labels (e.g., 1→"Work", 2→"School")
  - 🎯 **Automatic Label Application**: All summaries automatically convert numeric codes to human-readable labels
  - Works for: `tour_mode`, `trip_mode`, `person_type`, `gender`, `tour_purpose`, etc.
  - See section below on "Adding Value Labels for Categorical Variables"
- **weight_fields**: Define which columns contain sample rates/weights
- **binning_specs**: Define how to bin continuous variables

### data_model/variable_labels.yaml

- **Variable labels**: Human-readable names for dashboard
- **Categorical ordering**: Control order of categories in charts

## 💡 Common Tasks

### Change Sample Rate or Expansion Factor
Edit `data_model/ctramp_data_model.yaml` to specify the weight field:
```yaml
weight_fields:
  individual_tours:
    field: sample_rate  # Can be sample_rate, expansion_factor, survey_weight, etc.
    invert: true  # Set true to invert (sample_rate → expansion_factor)
```

### Adding Value Labels for Categorical Variables

**🎯 Automatic System**: The validation framework automatically converts numeric codes to human-readable labels for ALL summaries.

**How it works:**
1. Value mappings are defined centrally in `data_model/ctramp_data_model.yaml` under `value_mappings`
2. When summaries are generated, the system automatically:
   - Detects columns with defined mappings (e.g., `tour_mode`, `trip_mode`, `person_type`)
   - Creates temporary labeled columns (e.g., `tour_mode_name`)
   - Groups by the labeled values
   - Outputs human-readable labels in the final CSV

**To add/modify labels for any categorical variable:**

Edit `data_model/ctramp_data_model.yaml`:

```yaml
value_mappings:
  # Transportation modes (used for BOTH tour_mode and trip_mode)
  transportation_mode:
    type: categorical
    values:
      1: "SOV_GP - Single Occupant Vehicle (General Purpose)"
      2: "SOV_PAY - Single Occupant Vehicle (Express/Toll)"
      3: "SR2_GP - Shared Ride 2 (General Purpose)"
      # ... add your custom modes
      18: "My Custom Mode - Description"
  
  # Person types
  person_type:
    type: categorical
    values:
      1: "Full-time worker"
      2: "Part-time worker"
      # ... etc
  
  # Tour purposes (if using numeric codes instead of text)
  tour_purpose:
    type: categorical
    text_values:  # For text-based values
      - "Work"
      - "School"
      # ... etc
```

**What gets labeled automatically:**
- ✅ `tour_mode` → Uses `transportation_mode` mapping
- ✅ `trip_mode` → Uses `transportation_mode` mapping  
- ✅ `person_type` → Uses `person_type` mapping
- ✅ `gender` → Uses `gender` mapping
- ✅ Any column with a matching entry in `value_mappings`

**Benefits:**
- No need to modify Python code
- Labels applied consistently across ALL summaries
- Single source of truth for categorical mappings
- Easy to update labels without touching code

### Aggregating Categorical Variables (Simplifying Mode Choice)

**Problem:** The 17-mode transportation dictionary is too detailed for high-level analysis. You want to see "Auto" vs "Transit" vs "Active" instead of 17 separate categories.

**Solution:** Use `aggregation_specs` in `data_model/ctramp_data_model.yaml` to group detailed categories into broader groups:

```yaml
aggregation_specs:
  # Aggregate 17 transportation modes into simpler categories
  transportation_mode:
    mapping:
      1: "Auto - SOV"           # SOV_GP
      2: "Auto - SOV"           # SOV_PAY
      3: "Auto - Shared"        # SR2_GP
      4: "Auto - Shared"        # SR2_HOV
      5: "Auto - Shared"        # SR2_PAY
      6: "Auto - Shared"        # SR3_GP
      7: "Auto - Shared"        # SR3_HOV
      8: "Auto - Shared"        # SR3_PAY
      9: "Active"               # WALK
      10: "Active"              # BIKE
      11: "Transit"             # WLK_TRN
      12: "Transit"             # PNR_TRN
      13: "Transit"             # KNRPRV_TRN
      14: "Transit"             # KNRTNC_TRN
      15: "TNC/Taxi"            # TAXI
      16: "TNC/Taxi"            # TNC
      17: "School Bus"          # SCHLBUS
    apply_to:
      - tour_mode
      - trip_mode
```

**How it works:**
1. Aggregation specs are defined in the data model YAML
2. Each spec has a `mapping` (value → aggregated category) and `apply_to` (which columns)
3. System automatically creates new columns with `_agg` suffix (e.g., `tour_mode_agg`, `trip_mode_agg`)
4. Use the aggregated columns in your summary configurations

**Using aggregated modes in summaries:**

```yaml
custom_summaries:
  - name: "tour_mode_choice_aggregated"
    description: "Tour mode choice (simplified categories)"
    data_source: "individual_tours"
    group_by: "tour_mode_agg"  # Use the _agg column
    weight_field: "sample_rate"
    count_name: "tours"
```

**Benefits:**
- Reduces visual clutter in dashboards
- Easier to compare high-level mode shares
- No Python coding required
- Can define multiple aggregation levels (detailed vs high-level)
- Original detailed data still available if needed

### Filter Data Before Summarizing

Use the `filter` field in your summary configuration:

```yaml
# In any summary function
filtered_data = tour_data[tour_data['tour_purpose'] == 'Work']
summary = calculate_weighted_summary(filtered_data, ...)
```

### Create Crosstab Summary
```python
summary = calculate_weighted_summary(
    data,
    group_cols=['dimension1', 'dimension2'],  # Creates crosstab
    weight_col=weight_col,
    count_col_name='count',
    share_group_cols='dimension1'  # Share within dimension1 groups
)
```

## 📦 Dependencies

Install with:
```powershell
pip install pandas numpy pyyaml pydantic streamlit plotly
```

Or:
```powershell
pip install -r requirements.txt
```

## 🌐 Deployment

Dashboard is deployed to Streamlit Cloud at:
https://your-dashboard-url.streamlit.app

Pushes to `main` branch automatically trigger redeployment.

**Note:** Streamlit Cloud uses `dashboard/dashboard_app.py` as entry point.

## 🐛 Troubleshooting

### "Weight column not found"
- Check `data_model/ctramp_data_model.yaml` weight_fields configuration
- Ensure table names match (use `individual_tours`, not `tours`)
- Verify CSV has `sampleRate` or configured weight column

### "No dashboard files found"
- Run summary generation first
- Check `outputs/dashboard/` contains CSV and YAML files
- Verify `validation_config.yaml` output_directory setting

### Import errors after reorganization
- Make sure `__init__.py` exists in summaries folder
- Check import paths use relative imports (`.` for same folder, `..` for parent)
- Verify all modules moved to correct subdirectories

### Charts show wrong colors/labels
- Update `data_model/variable_labels.yaml` for display names
- Check `categorical_order` in variable_labels.yaml
- Ensure value_mappings applied in ctramp_data_model.yaml

## 📚 Additional Documentation

- `DEPLOYMENT.md` - Streamlit Cloud deployment guide
- `DASHBOARD_PATTERN.md` - Dashboard configuration patterns
- `summaries/run_all.py` - Main script with detailed docstrings

## 🤝 Contributing

When adding new features:
1. Keep summary logic in `summaries/` folder
2. Keep data model config in `data_model/` folder  
3. Keep dashboard code in `dashboard/` folder
4. Update this README with new instructions
5. Add examples for common use cases

---

**Questions?** Check existing summary files for examples or reach out to the team!
