# CTRAMP Model Validation Toolkit

Simple, transparent tools for summarizing and validating activity-based travel model (CTRAMP) outputs.

## Quick Start

**Summarize a model run in one command:**

```bash
# TM1 model or BATS survey (uses default config)
python summarize_model_run.py "C:/model_runs/2015_base/ctramp_output"

# TM2 model (specify TM2 config)
python summarize_model_run.py "C:/model_runs/2023_tm2/ctramp_output" --config data_model/tm2_data_model.yaml
```

This generates CSV summaries (auto ownership, tour mode, trip distance, etc.) from your CTRAMP output directory.

**Which config to use?**
- **TM1 Model** or **BATS Survey**: Use default (no `--config` needed) - uses `ctramp_data_model.yaml` (TM1 format)
- **TM2 Model**: Add `--config data_model/tm2_data_model.yaml`
- **Custom**: Create your own YAML config and specify with `--config`

**Automatic validation** runs after summarization to check for:
- Shares that don't sum to 1.0
- Negative values in count fields
- Missing data or zero totals
- Statistical outliers
- Logical inconsistencies (e.g., invalid time periods, impossible household sizes)

**Manual validation** of existing summaries:

```bash
python validate_summaries.py "outputs/my_summaries"
```

## What's Here

| File/Directory | Purpose |
|----------------|---------|
| **summarize_model_run.py** | **Main tool** - Generates validation summaries for one model run |
| **validate_summaries.py** | **Quality checker** - Validates summaries for errors and outliers |
| **HOW_TO_SUMMARIZE.md** | **User guide** - Detailed instructions and examples |
| **PREPROCESSING_NOTES.md** | **Implementation guide** - Preprocessing needed for advanced summaries |
| **data_model/** | YAML configuration files |
| ├── ctramp_data_model.yaml | **Summary definitions** - Edit this to add new summaries (30 summaries defined) |
| ├── variable_labels.yaml | Display names for dashboard |
| └── ctramp_data_model_loader.py | Helper functions |
| **observed_data_processing/** | Tools for processing ACS and survey data |
| **archived_validation_system/** | Old multi-dataset comparison system (archived) |
| **validation_config.yaml** | Legacy config (not used by new simple tool) |
| **outputs/** | Generated summary CSV files |

## Documentation

- **[How to Summarize a Model Run](HOW_TO_SUMMARIZE.md)** - Complete user guide with examples
- **Adding New Summaries** - Just edit `data_model/ctramp_data_model.yaml` (no code needed!)

## Design Philosophy

The new toolkit follows these principles:

1. **One Tool, One Job** - `summarize_model_run.py` does ONE thing: summarize ONE model run
2. **Transparent Logging** - Clear output showing every processing step
3. **Configuration Over Code** - Add summaries by editing YAML, not writing Python
4. **Simple Is Better** - ~350 lines of straightforward code, minimal classes
5. **Easy to Understand** - Clear code structure, easy to modify and extend

## What It Does

### Input
- CTRAMP output directory with CSV files:
  - `householdData_1.csv`
  - `personData_1.csv`
  - `indivTourData_1.csv`
  - `indivTripData_1.csv`

### Processing
1. Load data with standardized column names
2. Apply value labels (mode 1 → "SOV_GP")
3. Create aggregated categories (17 modes → 5 major groups)
4. Bin continuous variables (age → age groups)
5. Generate weighted frequency tables
6. Save individual CSV files

### Output
- **30 summaries** as separate CSV files:
  - 21 core validation summaries (always work)
  - 9 enhanced summaries (some require preprocessing - see PREPROCESSING_NOTES.md)
- Easy to load in Excel, pandas, R, or dashboard tools
- Simple format: columns for categories, counts, and shares
- Summaries with aggregations include mean/sum calculations (e.g., mean_trip_distance)

## Example Summaries

**Auto Ownership by Household Size:**
```csv
num_persons,num_vehicles,households,share
1,0,156823.4,0.382
1,1,234567.2,0.571
1,2,18923.1,0.046
2,0,89234.5,0.098
2,1,423567.8,0.465
2,2,345678.9,0.379
...
```

**Tour Mode by Purpose:**
```csv
tour_purpose,tour_mode_name,tours,share
Work,SOV_GP - Single Occupant Vehicle (General Purpose),1823441.5,0.524
Work,SR2_GP - Shared Ride 2 (General Purpose),456782.3,0.131
Work,WLK_TRN - Walk to Transit,328901.2,0.094
School,SOV_GP - Single Occupant Vehicle (General Purpose),234567.1,0.287
School,WALK - Walk,156789.3,0.192
School,SCHLBUS - School Bus,98234.5,0.120
...
```

## Adding New Summaries

Edit `data_model/ctramp_data_model.yaml` and add to the `summaries:` section:

```yaml
summaries:
  # Your new summary
  work_tours_by_income:
    description: "Work tours by income category"
    data_source: "individual_tours"
    filter: "tour_purpose == 'Work'"
    group_by: "income_category_bin"
    weight_field: "sample_rate"
    count_name: "tours"
    aggregations:                    # Optional: calculate means/sums
      mean_distance: "tour_distance"
```

No Python code needed! The tool automatically picks up new summary definitions.

**Note:** Some columns require preprocessing (geography joins, calculated fields). See `PREPROCESSING_NOTES.md` for details on what's available and what needs additional work.

## What About Comparison and Visualization?

The old system tried to do everything: summarize multiple runs, compare them, integrate external data, and deploy dashboards.

**New approach:**
1. **Summarize** - Use `summarize_model_run.py` (this tool) for each model run
2. **Compare** - Write simple pandas scripts to compare CSV files from different runs
3. **Visualize** - Create plots/dashboards as needed using your preferred tools

This separation makes each step simpler, more transparent, and easier to customize.

## Old System (Archived)

The previous validation system is archived in `archived_validation_system/` for reference.

It was complex because it tried to handle:
- Multiple model runs simultaneously
- Cross-scenario comparison
- External data integration
- Dashboard deployment
- All in one monolithic orchestrator

The new simple tool focuses on ONE job: summarize ONE model run clearly and transparently.

## For Developers

**Code Structure:**

The main tool (`summarize_model_run.py`) is organized as simple functions:
- `load_data_model()` - Read YAML config
- `find_latest_iteration_file()` - Auto-detect highest iteration number
- `load_ctramp_data()` - Load CSV files with standardized column names
- `apply_value_labels()` - Create human-readable labels (e.g., mode codes → mode names)
- `apply_aggregations()` - Create simplified categories (e.g., 17 modes → 6 groups)
- `apply_bins()` - Bin continuous variables (e.g., age → age groups)
- `generate_summary()` - Create one summary with counts, shares, and aggregations
- `expand_time_periods_summary()` - Special handler for time-of-day analysis
- `generate_all_summaries()` - Loop through all summary definitions

Total: ~550 lines with extensive logging and comments.

**Configuration Files:**

All configuration is in `data_model/ctramp_data_model.yaml`:
- Input schema (file patterns, column mappings)
- Value mappings (codes → labels)
- Aggregation specs (detailed → simplified)
- Binning specs (continuous → categorical)
- Summary definitions (what to calculate)

**Philosophy:**
- Favor clarity over abstraction
- Log every step transparently
- Make it easy for junior analysts to understand and modify
- Configuration changes should not require code changes

## Getting Help

1. **Read the user guide:** [HOW_TO_SUMMARIZE.md](HOW_TO_SUMMARIZE.md)
2. **Check preprocessing notes:** [PREPROCESSING_NOTES.md](PREPROCESSING_NOTES.md) - What columns are available and what needs preprocessing
3. **Check example summaries:** See `data_model/ctramp_data_model.yaml` - 30 summary definitions with comments
4. **Run with verbose logging:** The tool shows exactly what it's doing at each step
5. **Inspect the code:** ~550 lines, written to be readable and well-commented

## Requirements

- Python 3.8+
- pandas
- PyYAML

```bash
pip install pandas pyyaml
```

## License

MIT License - Feel free to use, modify, and share.
