# CTRAMP Model Validation Toolkit

Simple, transparent tools for summarizing and validating activity-based travel model (CTRAMP) outputs.

## Quick Start

**Summarize a model run in one command:**

```bash
python summarize_model_run.py "C:/model_runs/2015_base/ctramp_output"
```

This generates CSV summaries (auto ownership, tour mode, trip distance, etc.) from your CTRAMP output directory.

## What's Here

| File/Directory | Purpose |
|----------------|---------|
| **summarize_model_run.py** | **Main tool** - Generates validation summaries for one model run |
| **HOW_TO_SUMMARIZE.md** | **User guide** - Detailed instructions and examples |
| **data_model/** | YAML configuration files |
| ├── ctramp_data_model.yaml | **Summary definitions** - Edit this to add new summaries |
| ├── variable_labels.yaml | Display names for dashboard |
| └── ctramp_data_model_loader.py | Helper functions |
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
5. **Junior Analyst Friendly** - Easy to understand, easy to modify

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
- 23 standard summaries as separate CSV files
- Easy to load in Excel, pandas, R, or dashboard tools
- Simple format: columns for categories, counts, and shares

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
```

No Python code needed! The tool automatically picks up new summary definitions.

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
- `load_ctramp_data()` - Load CSV files
- `apply_value_labels()` - Create human-readable labels
- `apply_aggregations()` - Create simplified categories  
- `apply_bins()` - Bin continuous variables
- `generate_summary()` - Create one summary
- `generate_all_summaries()` - Loop through all summaries

Total: ~350 lines with extensive logging and comments.

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
2. **Check example summaries:** See `data_model/ctramp_data_model.yaml`
3. **Run with verbose logging:** The tool shows exactly what it's doing at each step
4. **Inspect the code:** Only ~350 lines, written to be readable

## Requirements

- Python 3.8+
- pandas
- PyYAML

```bash
pip install pandas pyyaml
```

## License

MIT License - Feel free to use, modify, and share.
