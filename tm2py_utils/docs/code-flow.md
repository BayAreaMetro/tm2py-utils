# Code Flow and Execution Guide

Detailed technical documentation of how the validation system code executes from configuration files to final dashboard outputs.

## Table of Contents

1. [System Entry Points](#system-entry-points)
2. [Execution Flow](#execution-flow)
3. [Key Classes and Their Roles](#key-classes-and-their-roles)
4. [Data Processing Pipeline](#data-processing-pipeline)
5. [Configuration Loading](#configuration-loading)
6. [Code Module Map](#code-module-map)

---

## System Entry Points

### Primary Entry Point: `run_all.py`

**Location**: `tm2py_utils/summary/validation/summaries/run_all.py`

**Purpose**: Main orchestrator that reads configuration, loads data, generates all summaries, and writes combined CSVs.

**Usage**:
```bash
# Run all summaries defined in validation_config.yaml
python -m tm2py_utils.summary.validation.summaries.run_all \
    --config validation_config.yaml

# Or with explicit paths
python -m tm2py_utils.summary.validation.summaries.run_all \
    --input-dirs A:/model-run-1 A:/model-run-2 \
    --output-dir outputs/
```

**Command-line Arguments**:
- `--config PATH`: Path to YAML configuration file (recommended)
- `--input-dirs DIR [DIR ...]`: One or more CTRAMP output directories
- `--output-dir PATH`: Where to write summary CSVs (default: `outputs/`)
- `--summaries NAME [NAME ...]`: Specific summaries to run (default: all)
- `--validate-only`: Validate configuration without running summaries

### Secondary Entry Point: `run_and_deploy_dashboard.py`

**Location**: `tm2py_utils/summary/validation/run_and_deploy_dashboard.py`

**Purpose**: Convenience wrapper that runs summaries AND launches dashboard.

**Usage**:
```bash
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
```

**What it does**:
1. Calls `run_all.py` to generate summaries
2. Optionally launches Streamlit dashboard on completion

### Dashboard Entry Point: `streamlit_app.py`

**Location**: `tm2py_utils/summary/validation/streamlit_app.py`

**Purpose**: Streamlit web application for interactive visualization.

**Usage**:
```bash
streamlit run streamlit_app.py
```

---

## Execution Flow

### Visual Code Flow Diagram

```
USER COMMAND
     │
     ├─────────────────────────────────────────────────────────────┐
     │                                                             │
     v                                                             v
┌─────────────────────┐                              ┌─────────────────────┐
│ python -m ...       │                              │ streamlit run       │
│ run_all.py          │                              │ streamlit_app.py    │
│ --config X.yaml     │                              │                     │
└─────────────────────┘                              └─────────────────────┘
     │                                                             │
     │ main()                                                      │ main()
     v                                                             v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Parse Arguments & Load Config                                  │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ argparse.ArgumentParser()                                       │   │
│ │   - Read --config path                                          │   │
│ │   - Read --input-dirs (optional)                                │   │
│ │   - Read --output-dir (optional)                                │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ load_config(config_path)                                        │   │
│ │   - yaml.safe_load(validation_config.yaml)                      │   │
│ │   - ValidationConfig.parse_obj() → Pydantic validation          │   │
│ │   - Returns: config object with .datasets, .summaries           │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Initialize Summary Generator                                   │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ generator = SummaryGenerator(config)                            │   │
│ │   - self.config = config                                        │   │
│ │   - self.data_model = load_data_model()  ← Load summary YAMLs   │   │
│ │   - self.datasets = {}  ← Empty dict for loaded data            │   │
│ │   - Create output directories                                   │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Load All Datasets into Memory                                  │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ generator.load_datasets()                                       │   │
│ │                                                                 │   │
│ │   FOR EACH dataset in config.datasets:                         │   │
│ │   ┌───────────────────────────────────────────────────────┐   │   │
│ │   │ dataset_name = "TM22_2015"                            │   │   │
│ │   │ directory = "A:/2015.../ctramp_output"                │   │   │
│ │   │                                                       │   │   │
│ │   │ Read CSVs:                                            │   │   │
│ │   │   hh_df = pd.read_csv("householdData_1.csv")         │   │   │
│ │   │   per_df = pd.read_csv("personData_1.csv")           │   │   │
│ │   │   tour_df = pd.read_csv("indivTourData_1.csv")       │   │   │
│ │   │   trip_df = pd.read_csv("indivTripData_1.csv")       │   │   │
│ │   │                                                       │   │   │
│ │   │ Add dataset column:                                   │   │   │
│ │   │   hh_df['dataset'] = "TM22_2015"                     │   │   │
│ │   │   per_df['dataset'] = "TM22_2015"                    │   │   │
│ │   │                                                       │   │   │
│ │   │ Store in memory:                                      │   │   │
│ │   │   self.datasets["TM22_2015"] = {                     │   │   │
│ │   │     "households": hh_df,                             │   │   │
│ │   │     "persons": per_df,                               │   │   │
│ │   │     "tours": tour_df,                                │   │   │
│ │   │     "trips": trip_df                                 │   │   │
│ │   │   }                                                   │   │   │
│ │   └───────────────────────────────────────────────────────┘   │   │
│ │                                                                 │   │
│ │   Result: self.datasets = {                                    │   │
│ │     "TM22_2015": {households: DF, persons: DF, ...},           │   │
│ │     "TM22_2023": {households: DF, persons: DF, ...},           │   │
│ │     "HTS_2023": {households: DF, persons: DF, ...}             │   │
│ │   }                                                             │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Generate All Summaries (MAIN LOOP)                             │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ generator.generate_all_summaries()                              │   │
│ │                                                                 │   │
│ │   FOR EACH summary in config.summaries:                        │   │
│ │   ┌───────────────────────────────────────────────────────┐   │   │
│ │   │ summary_name = "auto_ownership_regional"              │   │   │
│ │   │                                                       │   │   │
│ │   │ ┌─────────────────────────────────────────────────┐ │   │   │
│ │   │ │ Load summary definition from data_model/        │ │   │   │
│ │   │ │ summary_def = load_summary_definition(          │ │   │   │
│ │   │ │   "data_model/summary_auto_ownership_regional   │ │   │   │
│ │   │ │    .yaml")                                       │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ Result:                                          │ │   │   │
│ │   │ │   source_table: "households"                     │ │   │   │
│ │   │ │   groupby: ["num_vehicles"]                      │ │   │   │
│ │   │ │   binning: {...}                                 │ │   │   │
│ │   │ │   aggregation: {...}                             │ │   │   │
│ │   │ └─────────────────────────────────────────────────┘ │   │   │
│ │   │                      ↓                                │   │   │
│ │   │ ┌─────────────────────────────────────────────────┐ │   │   │
│ │   │ │ Process EACH dataset for this summary           │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ dataset_results = []                             │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ FOR dataset_name in ["TM22_2015", "TM22_2023",  │ │   │   │
│ │   │ │                      "HTS_2023"]:                │ │   │   │
│ │   │ │   ┌──────────────────────────────────────┐      │ │   │   │
│ │   │ │   │ df = self.datasets[dataset_name]     │      │ │   │   │
│ │   │ │   │                ["households"]         │      │ │   │   │
│ │   │ │   │                                       │      │ │   │   │
│ │   │ │   │ APPLY TRANSFORMATIONS:                │      │ │   │   │
│ │   │ │   │ 1. apply_filters(df)                 │      │ │   │   │
│ │   │ │   │ 2. apply_binning(df)   ← continuous  │      │ │   │   │
│ │   │ │   │                          to categories│      │ │   │   │
│ │   │ │   │ 3. apply_aggregation(df) ← combine   │      │ │   │   │
│ │   │ │   │                           categories  │      │ │   │   │
│ │   │ │   │ 4. groupby(["num_vehicles"])         │      │ │   │   │
│ │   │ │   │ 5. agg(count, sum, mean)             │      │ │   │   │
│ │   │ │   │ 6. apply weights (sample_rate)       │      │ │   │   │
│ │   │ │   │ 7. calculate shares (%)              │      │ │   │   │
│ │   │ │   │                                       │      │ │   │   │
│ │   │ │   │ result_df['dataset'] = dataset_name  │      │ │   │   │
│ │   │ │   │                                       │      │ │   │   │
│ │   │ │   │ dataset_results.append(result_df)    │      │ │   │   │
│ │   │ │   └──────────────────────────────────────┘      │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ └─────────────────────────────────────────────────┘ │   │   │
│ │   │                      ↓                                │   │   │
│ │   │ ┌─────────────────────────────────────────────────┐ │   │   │
│ │   │ │ Combine all datasets for this summary           │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ combined_df = pd.concat(dataset_results,        │ │   │   │
│ │   │ │                         ignore_index=True)       │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ # Sort for consistent output                    │ │   │   │
│ │   │ │ combined_df.sort_values(                        │ │   │   │
│ │   │ │   ["num_vehicles", "dataset"])                  │ │   │   │
│ │   │ └─────────────────────────────────────────────────┘ │   │   │
│ │   │                      ↓                                │   │   │
│ │   │ ┌─────────────────────────────────────────────────┐ │   │   │
│ │   │ │ Write CSV to disk                               │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ output_file = "outputs/" +                      │ │   │   │
│ │   │ │   "auto_ownership_regional.csv"                 │ │   │   │
│ │   │ │                                                  │ │   │   │
│ │   │ │ combined_df.to_csv(output_file,                 │ │   │   │
│ │   │ │                    index=False)                  │ │   │   │
│ │   │ └─────────────────────────────────────────────────┘ │   │   │
│ │   └───────────────────────────────────────────────────────┘   │   │
│ │                                                                 │   │
│ │   REPEAT for next summary (tour_mode_by_purpose, etc.)        │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Integrate External Data (Optional)                             │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ IF config.observed_summaries exists:                            │   │
│ │                                                                 │   │
│ │   FOR EACH observed_summary:                                   │   │
│ │   ┌───────────────────────────────────────────────────────┐   │   │
│ │   │ # Load preprocessed external data                     │   │   │
│ │   │ acs_df = pd.read_csv(                                │   │   │
│ │   │   "external_data/auto_ownership_acs_2023.csv")       │   │   │
│ │   │ # Expected: same columns as model output              │   │   │
│ │   │ #   + dataset column = "ACS_2023"                    │   │   │
│ │   │                                                       │   │   │
│ │   │ # Load existing summary                               │   │   │
│ │   │ existing = pd.read_csv(                              │   │   │
│ │   │   "outputs/auto_ownership_regional.csv")             │   │   │
│ │   │                                                       │   │   │
│ │   │ # Append external data                                │   │   │
│ │   │ combined = pd.concat([existing, acs_df])             │   │   │
│ │   │                                                       │   │   │
│ │   │ # Overwrite file                                      │   │   │
│ │   │ combined.to_csv(                                     │   │   │
│ │   │   "outputs/auto_ownership_regional.csv")             │   │   │
│ │   └───────────────────────────────────────────────────────┘   │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 6: Prepare Dashboard Output                                       │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ Copy CSVs to dashboard folder:                                  │   │
│ │   shutil.copy("outputs/*.csv",                                  │   │
│ │               "outputs/dashboard/")                             │   │
│ │                                                                 │   │
│ │ Dashboard configs already exist in dashboard/*.yaml             │   │
│ └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
     │
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ DONE - Summary CSVs ready in outputs/                                  │
│                                                                         │
│ Generated files:                                                        │
│   outputs/auto_ownership_regional.csv                                  │
│   outputs/tour_mode_by_purpose.csv                                     │
│   outputs/cdap_by_household_type.csv                                   │
│   ... (25 total CSV files)                                             │
└─────────────────────────────────────────────────────────────────────────┘
     │
     │ If --launch-dashboard flag used
     v
┌─────────────────────────────────────────────────────────────────────────┐
│ DASHBOARD EXECUTION (streamlit_app.py)                                 │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ main()                                                          │   │
│ │   │                                                             │   │
│ │   ├─ Load variable_labels.yaml → Display names                 │   │
│ │   ├─ Load validation_config.yaml → Dataset order               │   │
│ │   │                                                             │   │
│ │   ├─ Scan outputs/dashboard/ for CSV files                     │   │
│ │   ├─ Scan dashboard/ for dashboard-*.yaml configs              │   │
│ │   │                                                             │   │
│ │   └─ FOR EACH dashboard tab:                                   │   │
│ │       │                                                         │   │
│ │       ├─ Read dashboard-auto-ownership.yaml                    │   │
│ │       │   → Get list of summaries for this tab                 │   │
│ │       │                                                         │   │
│ │       └─ FOR EACH summary in tab:                              │   │
│ │           │                                                     │   │
│ │           ├─ Load CSV: pd.read_csv(                            │   │
│ │           │   "outputs/dashboard/auto_ownership_regional.csv") │   │
│ │           │                                                     │   │
│ │           ├─ Create Plotly chart based on chart_type:          │   │
│ │           │   - bar: px.bar(df, x="num_vehicles",              │   │
│ │           │                 y="households",                     │   │
│ │           │                 color="dataset")                    │   │
│ │           │   - line: px.line(...)                              │   │
│ │           │   - scatter: px.scatter(...)                        │   │
│ │           │                                                     │   │
│ │           └─ st.plotly_chart(fig) → Render in browser          │   │
│ │                                                                 │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│ Browser opens: http://localhost:8501                                   │
│ User sees interactive dashboard with all charts                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### High-Level Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. START: User runs run_all.py with --config                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. CONFIGURATION LOADING (ConfigLoader class)                   │
│    • Parse validation_config.yaml                               │
│    • Validate dataset definitions                               │
│    • Validate summary configurations                            │
│    • Load data model schemas from data_model/                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. SUMMARY GENERATOR INITIALIZATION (SummaryGenerator class)    │
│    • Create output directory structure                          │
│    • Prepare for parallel processing                            │
│    • Initialize logging                                         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 4. DATA LOADING LOOP (for each dataset in config)               │
│    • Determine dataset type (model/survey/ACS/CTPP)             │
│    • Load appropriate CSV files:                                │
│      - Model: householdData_1.csv, personData_1.csv, etc.       │
│      - Survey: Same format, different source directory          │
│      - External: Preprocessed CSVs in external_data/            │
│    • Apply data model validation                                │
│    • Store in memory: {dataset_name: {table: DataFrame}}        │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 5. SUMMARY GENERATION LOOP (for each summary in config)         │
│    For each summary definition:                                 │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ 5a. Load summary configuration from data_model/        │   │
│    │     (groupby, filters, bins, aggregations)             │   │
│    └────────────────────────────────────────────────────────┘   │
│                          ↓                                       │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ 5b. For each dataset, apply processing pipeline:      │   │
│    │     • Select source table (households/persons/tours)   │   │
│    │     • Apply filters (if specified)                     │   │
│    │     • Bin continuous variables → categories            │   │
│    │     • Aggregate categories → broader groups            │   │
│    │     • Group by dimensions                              │   │
│    │     • Apply weights (sample_rate)                      │   │
│    │     • Calculate counts and shares                      │   │
│    │     • Add dataset identifier column                    │   │
│    └────────────────────────────────────────────────────────┘   │
│                          ↓                                       │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ 5c. Combine all datasets for this summary             │   │
│    │     • Concatenate DataFrames vertically                │   │
│    │     • Ensure consistent columns                        │   │
│    │     • Sort by dimensions and dataset                   │   │
│    └────────────────────────────────────────────────────────┘   │
│                          ↓                                       │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ 5d. Write combined CSV to outputs/                    │   │
│    │     Example: auto_ownership_regional.csv               │   │
│    └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 6. EXTERNAL DATA INTEGRATION (if configured)                    │
│    • Load preprocessed CSVs from external_data/                 │
│    • Append to existing summary CSVs                            │
│    • Re-write combined files                                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 7. DASHBOARD-READY OUTPUT GENERATION                            │
│    • Copy CSVs to outputs/dashboard/                            │
│    • Generate dashboard configuration YAMLs                     │
│    • Create variable_labels.yaml for display names             │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 8. END: Summary CSVs ready for analysis and visualization       │
└──────────────────────────────────────────────────────────────────┘
```

### Detailed Step-by-Step Execution

#### Step 1: Entry and Argument Parsing

```python
# In run_all.py main() function
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='Path to YAML configuration file')
    args = parser.parse_args()
    
    # Load and validate configuration
    config = load_config(args.config)
```

**What happens**:
1. Parse command-line arguments
2. Determine if config file or explicit paths provided
3. Set up logging with timestamps

#### Step 2: Configuration Loading

**File**: `validation_config.yaml`

**Pydantic Models** (in `run_all.py`):
- `ValidationConfig`: Top-level configuration container
- `DatasetConfig`: Individual dataset specifications
- `SummaryConfig`: Summary definition references
- `ObservedSummary`: External data integration specs

**Loading Process**:
```python
class ValidationConfig(BaseModel):
    datasets: List[DatasetConfig]  # Model runs, surveys
    summaries: List[SummaryConfig]  # Which summaries to generate
    observed_summaries: Optional[List[ObservedSummary]]  # ACS, CTPP
    dataset_order: List[str]  # Display order in charts
    output_dir: Path = Path("outputs")
    
# Validation happens automatically via Pydantic
config = ValidationConfig(**yaml.safe_load(config_file))
```

**What gets validated**:
- All required fields present
- Paths exist and are accessible
- Dataset names are unique
- Summary names match available summary definitions
- Data model references are valid

#### Step 3: Data Model Loading

**Location**: `tm2py_utils/summary/validation/data_model/`

**Files**:
- `variable_labels.yaml`: Human-readable display names
- `summary_*.yaml`: Individual summary configurations (25 files)

**Loading Function**:
```python
def load_data_model():
    """Load all summary definitions from YAML files."""
    summaries = {}
    for yaml_file in Path("data_model").glob("summary_*.yaml"):
        summary = SummaryDefinition(**yaml.safe_load(yaml_file))
        summaries[summary.name] = summary
    return summaries
```

**SummaryDefinition Schema**:
```yaml
name: auto_ownership_regional
description: "Household auto ownership by region"
source_table: households
filters: null  # Optional: filter to specific records
binning:
  - variable: income
    bins: [0, 30000, 60000, 100000, 999999]
    labels: ["<$30k", "$30-60k", "$60-100k", "$100k+"]
aggregation:
  num_persons:
    "4+": [4, 5, 6, 7, 8, 9]  # Combine 4+ into single category
groupby:
  - num_vehicles
  - income_category
metrics:
  - households  # Count of records
  - share  # Percentage within group
```

#### Step 4: Data Loading

**CTRAMP Files Read** (for each model dataset):
```python
def load_ctramp_dataset(directory: Path, dataset_name: str):
    """Load all CTRAMP output files for a model run."""
    data = {}
    
    # Core tables (always required)
    data['households'] = pd.read_csv(directory / "householdData_1.csv")
    data['persons'] = pd.read_csv(directory / "personData_1.csv")
    
    # Tour/trip data (if needed by summaries)
    if any(s.source_table == 'tours' for s in summaries):
        data['tours'] = pd.read_csv(directory / "indivTourData_1.csv")
    if any(s.source_table == 'trips' for s in summaries):
        data['trips'] = pd.read_csv(directory / "indivTripData_1.csv")
    
    # Add dataset identifier
    for table_name, df in data.items():
        df['dataset'] = dataset_name
    
    return data
```

**Survey Files** (same format, different directory):
```python
# Survey must be preprocessed to CTRAMP format
survey_data = load_ctramp_dataset(
    directory=Path("surveys/2023_household_travel_survey"),
    dataset_name="HTS_2023"
)
```

**External Data** (preprocessed CSVs):
```python
# Pre-aggregated to match summary output format
acs_data = pd.read_csv("external_data/auto_ownership_acs.csv")
# Expected columns: same as model output + 'dataset' = 'ACS_2023'
```

#### Step 5: Summary Generation Pipeline

**For each summary**, the system executes this pipeline:

##### 5.1 Select Source Data
```python
summary = summaries['auto_ownership_regional']
source_table = summary.source_table  # 'households'
df = datasets['TM22_2015']['households'].copy()
```

##### 5.2 Apply Filters (if specified)
```python
if summary.filters:
    for filter_spec in summary.filters:
        df = df[df[filter_spec.column].isin(filter_spec.values)]
```

##### 5.3 Binning (continuous → categorical)
```python
if summary.binning:
    for bin_spec in summary.binning:
        df[f'{bin_spec.variable}_category'] = pd.cut(
            df[bin_spec.variable],
            bins=bin_spec.bins,
            labels=bin_spec.labels,
            right=False
        )
```

##### 5.4 Aggregation (detailed → broader categories)
```python
if summary.aggregation:
    for var, mapping in summary.aggregation.items():
        # Example: {4: [4,5,6,7,8,9]} -> all 4+ become "4+"
        df[f'{var}_agg'] = df[var].apply(lambda x: 
            next((k for k, v in mapping.items() if x in v), x)
        )
```

##### 5.5 Group and Weight
```python
groupby_cols = summary.groupby
result = df.groupby(groupby_cols).agg({
    'hh_id': 'count',  # Count households
    'sample_rate': 'first'  # Expansion factor
}).reset_index()

# Apply weights
result['households'] = result['hh_id'] / result['sample_rate']

# Calculate shares within groups
if summary.share_within:
    result['share'] = result.groupby(summary.share_within)['households'].transform(
        lambda x: x / x.sum() * 100
    )
```

##### 5.6 Add Dataset Identifier
```python
result['dataset'] = dataset_name  # e.g., "TM22_2015"
```

##### 5.7 Combine All Datasets
```python
combined = pd.concat([
    process_dataset(datasets['TM22_2015'], 'TM22_2015'),
    process_dataset(datasets['TM22_2023'], 'TM22_2023'),
    process_dataset(datasets['HTS_2023'], 'HTS_2023')
], ignore_index=True)
```

##### 5.8 Write CSV
```python
output_file = output_dir / f"{summary.name}.csv"
combined.to_csv(output_file, index=False)
```

**Example Output CSV**:
```csv
num_vehicles,income_category,households,share,dataset
0,<$30k,125430,45.2,TM22_2015
0,<$30k,118920,43.8,TM22_2023
0,<$30k,142000,48.1,HTS_2023
0,<$30k,139500,47.5,ACS_2023
1,$30-60k,87500,31.5,TM22_2015
...
```

#### Step 6: External Data Integration

```python
if config.observed_summaries:
    for obs_summary in config.observed_summaries:
        # Load preprocessed external data
        external_df = pd.read_csv(obs_summary.file_path)
        
        # Load existing summary CSV
        existing = pd.read_csv(output_dir / f"{obs_summary.summary_name}.csv")
        
        # Append external data
        combined = pd.concat([existing, external_df], ignore_index=True)
        
        # Overwrite with combined data
        combined.to_csv(output_dir / f"{obs_summary.summary_name}.csv", index=False)
```

#### Step 7: Dashboard Preparation

```python
# Copy CSVs to dashboard folder
dashboard_dir = output_dir / "dashboard"
for csv_file in output_dir.glob("*.csv"):
    shutil.copy(csv_file, dashboard_dir / csv_file.name)

# Generate dashboard config YAMLs (if not already present)
# These define chart types, axes, titles for Streamlit app
```

---

## Key Classes and Their Roles

### Core Processing Classes

#### `SummaryGenerator` (run_all.py)

**Purpose**: Orchestrates entire summary generation process

**Key Methods**:
- `__init__(config)`: Initialize with validated configuration
- `load_datasets()`: Read all CTRAMP CSVs into memory
- `generate_all_summaries()`: Main loop over all summaries
- `generate_summary(summary_def, datasets)`: Process one summary
- `write_outputs(results)`: Save combined CSVs

**Usage**:
```python
generator = SummaryGenerator(config)
generator.load_datasets()
results = generator.generate_all_summaries()
generator.write_outputs(results)
```

#### `DataModelLoader` (ctramp_data_model_loader.py)

**Purpose**: Load and validate summary definitions from YAML

**Key Methods**:
- `load_summary_definitions()`: Read all summary_*.yaml files
- `validate_summary(summary_def)`: Check for required fields
- `get_summary(name)`: Retrieve specific summary configuration

#### `ConfigLoader` (run_all.py)

**Purpose**: Load and validate top-level configuration

**Pydantic Models**:
- `ValidationConfig`: Complete config schema
- `DatasetConfig`: Single dataset specification
- `SummaryConfig`: Summary to generate
- `ObservedSummary`: External data integration

### Data Model Classes

#### `SummaryDefinition` (ctramp_data_model_loader.py)

**Purpose**: Schema for individual summary configurations

**Fields**:
```python
class SummaryDefinition(BaseModel):
    name: str
    description: str
    source_table: str  # households, persons, tours, trips
    filters: Optional[List[FilterSpec]]
    binning: Optional[List[BinSpec]]
    aggregation: Optional[Dict[str, Dict[str, List]]]
    groupby: List[str]
    metrics: List[str]
    share_within: Optional[List[str]]
```

#### `BinSpec` (ctramp_data_model_loader.py)

**Purpose**: Define continuous-to-categorical binning

```python
class BinSpec(BaseModel):
    variable: str  # Source column name
    bins: List[float]  # Bin edges
    labels: List[str]  # Category labels
    output_column: str  # New column name (default: f"{variable}_category")
```

---

## Data Processing Pipeline

### Pipeline Architecture

```
RAW DATA (CTRAMP CSV)
       ↓
    FILTER  ← Apply row filters (optional)
       ↓
    BIN     ← Convert continuous → categorical
       ↓
  AGGREGATE ← Combine detailed categories
       ↓
   GROUP BY ← Group by dimensions
       ↓
   WEIGHT   ← Apply sample_rate expansion
       ↓
   METRICS  ← Calculate counts, shares, averages
       ↓
   OUTPUT   ← Standardized CSV with dataset column
```

### Processing Functions

#### Filter Application

```python
def apply_filters(df: pd.DataFrame, filters: List[FilterSpec]) -> pd.DataFrame:
    """Apply row-level filters to data."""
    for filter_spec in filters:
        if filter_spec.operator == 'in':
            df = df[df[filter_spec.column].isin(filter_spec.values)]
        elif filter_spec.operator == '==':
            df = df[df[filter_spec.column] == filter_spec.value]
        elif filter_spec.operator == '>':
            df = df[df[filter_spec.column] > filter_spec.value]
    return df
```

#### Binning Continuous Variables

```python
def apply_binning(df: pd.DataFrame, binning: List[BinSpec]) -> pd.DataFrame:
    """Convert continuous variables to categorical bins."""
    for bin_spec in binning:
        output_col = bin_spec.output_column or f"{bin_spec.variable}_category"
        df[output_col] = pd.cut(
            df[bin_spec.variable],
            bins=bin_spec.bins,
            labels=bin_spec.labels,
            right=False,  # [a, b) intervals
            include_lowest=True
        )
    return df
```

#### Category Aggregation

```python
def apply_aggregation(df: pd.DataFrame, aggregation: Dict) -> pd.DataFrame:
    """Combine detailed categories into broader groups."""
    for variable, mapping in aggregation.items():
        output_col = f"{variable}_agg"
        
        # Create mapping function
        def map_value(x):
            for new_value, old_values in mapping.items():
                if x in old_values:
                    return new_value
            return x  # Keep original if not in mapping
        
        df[output_col] = df[variable].apply(map_value)
    return df
```

#### Grouping and Weighting

```python
def group_and_weight(df: pd.DataFrame, summary: SummaryDefinition) -> pd.DataFrame:
    """Group by dimensions, apply weights, calculate metrics."""
    
    # Group and count
    grouped = df.groupby(summary.groupby).agg({
        'hh_id': 'count',
        'sample_rate': 'first'
    }).reset_index()
    
    # Apply expansion weights
    grouped['households'] = grouped['hh_id'] / grouped['sample_rate']
    
    # Calculate shares if specified
    if summary.share_within:
        grouped['share'] = grouped.groupby(summary.share_within)['households'].transform(
            lambda x: x / x.sum() * 100
        )
    
    # Select final columns
    final_cols = summary.groupby + summary.metrics
    return grouped[final_cols]
```

---

## Configuration Loading

### Configuration File Structure

```yaml
# validation_config.yaml

# Dataset definitions
datasets:
  - name: "TM22_2015"
    directory: "A:/2015-tm22-dev-sprint-01/ctramp_output"
    type: "model"
    
  - name: "TM22_2023"
    directory: "A:/2023-tm22-dev-version-05/ctramp_output"
    type: "model"
    
  - name: "HTS_2023"
    directory: "surveys/2023_formatted"
    type: "survey"

# Summary specifications (references to data_model/*.yaml)
summaries:
  - name: "auto_ownership_regional"
  - name: "tour_mode_by_purpose"
  - name: "cdap_by_household_type"

# External data integration
observed_summaries:
  - summary_name: "auto_ownership_regional"
    file_path: "external_data/auto_ownership_acs_2023.csv"
    dataset_name: "ACS_2023"

# Dashboard display order
dataset_order:
  - "TM22_2015"
  - "TM22_2023"
  - "HTS_2023"
  - "ACS_2023"

# Output directory
output_dir: "outputs"
```

### Configuration Loading Code

```python
def load_config(config_path: Path) -> ValidationConfig:
    """Load and validate configuration file."""
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Pydantic automatically validates against schema
    config = ValidationConfig(**config_dict)
    
    # Additional validation
    validate_dataset_paths(config.datasets)
    validate_summary_references(config.summaries)
    
    return config

def validate_dataset_paths(datasets: List[DatasetConfig]):
    """Ensure all dataset directories exist."""
    for dataset in datasets:
        if not Path(dataset.directory).exists():
            raise ValueError(f"Dataset directory not found: {dataset.directory}")

def validate_summary_references(summaries: List[SummaryConfig]):
    """Ensure all referenced summaries have definitions."""
    available_summaries = load_data_model()
    for summary in summaries:
        if summary.name not in available_summaries:
            raise ValueError(f"Summary definition not found: {summary.name}")
```

---

## Code Module Map

### Directory Structure

```
tm2py_utils/summary/validation/
│
├── summaries/
│   ├── run_all.py              ← MAIN ENTRY POINT
│   └── config_driven_summaries.py  ← Legacy (being phased out)
│
├── data_model/
│   ├── ctramp_data_model_loader.py  ← Load summary definitions
│   ├── variable_labels.yaml         ← Display names
│   ├── summary_auto_ownership_regional.yaml
│   ├── summary_tour_mode_by_purpose.yaml
│   └── ... (25 summary definition files)
│
├── dashboard/
│   ├── dashboard_app.py        ← Streamlit visualization
│   ├── dashboard-auto-ownership.yaml
│   └── ... (8 dashboard config files)
│
├── outputs/
│   ├── auto_ownership_regional.csv
│   ├── tour_mode_by_purpose.csv
│   └── dashboard/
│       ├── *.csv (copies for deployment)
│       └── *.yaml (dashboard configs)
│
├── external_data/
│   ├── auto_ownership_acs_2023.csv
│   └── ... (preprocessed ACS, CTPP data)
│
├── validation_config.yaml      ← TOP-LEVEL CONFIGURATION
├── streamlit_app.py           ← Dashboard entry point
├── run_and_deploy_dashboard.py  ← Convenience wrapper
└── docs/
    ├── validation-system.md    ← User guide
    ├── code-flow.md           ← This file
    ├── data-model.md
    └── ...
```

### Module Dependencies

```
run_all.py
  ├─ imports ─→ ctramp_data_model_loader.py
  │             └─ loads ─→ data_model/summary_*.yaml
  │
  ├─ reads ─→ validation_config.yaml
  │
  ├─ loads ─→ CTRAMP CSVs from dataset directories
  │
  └─ writes ─→ outputs/*.csv

streamlit_app.py
  ├─ reads ─→ outputs/dashboard/*.csv
  ├─ reads ─→ dashboard/dashboard-*.yaml
  └─ reads ─→ data_model/variable_labels.yaml

run_and_deploy_dashboard.py
  ├─ calls ─→ run_all.py
  └─ launches ─→ streamlit_app.py
```

### Function Call Hierarchy

```
main()  [run_all.py]
  │
  ├─ parse_arguments()
  ├─ load_config()
  │   ├─ yaml.safe_load()
  │   └─ ValidationConfig.parse_obj()
  │
  ├─ SummaryGenerator.__init__()
  │
  ├─ generator.load_datasets()
  │   └─ For each dataset:
  │       ├─ load_ctramp_dataset()
  │       │   ├─ pd.read_csv("householdData_1.csv")
  │       │   ├─ pd.read_csv("personData_1.csv")
  │       │   └─ ...
  │       └─ validate_data_model()
  │
  ├─ generator.generate_all_summaries()
  │   └─ For each summary:
  │       ├─ load_summary_definition()
  │       ├─ generator.generate_summary()
  │       │   └─ For each dataset:
  │       │       ├─ apply_filters()
  │       │       ├─ apply_binning()
  │       │       ├─ apply_aggregation()
  │       │       ├─ group_and_weight()
  │       │       └─ calculate_metrics()
  │       └─ combine_datasets()
  │
  ├─ generator.integrate_external_data()
  │   └─ For each observed_summary:
  │       ├─ pd.read_csv(external_file)
  │       └─ append_to_summary()
  │
  └─ generator.write_outputs()
      └─ For each summary result:
          └─ df.to_csv()
```

---

## Execution Examples

### Example 1: Generate All Summaries

```bash
cd tm2py_utils/summary/validation
python -m tm2py_utils.summary.validation.summaries.run_all \
    --config validation_config.yaml
```

**What happens**:
1. Loads `validation_config.yaml`
2. Reads 3 datasets (2 model runs, 1 survey)
3. Generates 25 summaries
4. Writes 25 CSVs to `outputs/`
5. Integrates ACS data into 5 summaries
6. Copies files to `outputs/dashboard/`
7. Total time: ~2-5 minutes depending on data size

### Example 2: Generate Specific Summaries

```bash
python -m tm2py_utils.summary.validation.summaries.run_all \
    --config validation_config.yaml \
    --summaries auto_ownership_regional tour_mode_by_purpose
```

**What happens**:
- Only generates 2 specified summaries
- Skips other 23 summaries
- Faster execution (~30 seconds)

### Example 3: Validate Configuration Only

```bash
python -m tm2py_utils.summary.validation.summaries.run_all \
    --config validation_config.yaml \
    --validate-only
```

**What happens**:
- Loads and validates configuration
- Checks all paths exist
- Verifies summary definitions found
- Does NOT load data or generate summaries
- Reports any errors
- Exits

### Example 4: Run and Launch Dashboard

```bash
python run_and_deploy_dashboard.py \
    --config validation_config.yaml \
    --launch-dashboard
```

**What happens**:
1. Generates all summaries (same as Example 1)
2. Launches Streamlit on http://localhost:8501
3. Opens dashboard in browser
4. Dashboard auto-loads CSVs from `outputs/dashboard/`

---

## Performance Considerations

### Memory Usage

**Data Loading**: All datasets loaded into memory simultaneously
- Typical model run: ~500MB per dataset
- 3 datasets = ~1.5GB RAM
- Recommendation: 8GB+ RAM for production use

**Optimization**: Process datasets sequentially if memory constrained
```python
# Instead of loading all at once:
for dataset in datasets:
    data = load_dataset(dataset)
    process_summaries(data)
    del data  # Free memory
```

### Execution Time

**Typical Performance** (on 2023 hardware):
- Load 1 dataset (4 CSV files, ~2M records): 10-30 seconds
- Generate 1 summary: 1-5 seconds
- Total for 3 datasets × 25 summaries: 2-5 minutes

**Bottlenecks**:
1. CSV reading (disk I/O)
2. Groupby operations on large datasets
3. Writing output CSVs

**Parallelization** (future enhancement):
```python
# Process summaries in parallel
from multiprocessing import Pool
with Pool(4) as pool:
    results = pool.map(generate_summary, summaries)
```

### Data Size Limits

**Tested With**:
- Households: 2.7M records
- Persons: 6.5M records  
- Tours: 12M records
- Trips: 40M records

**Practical Limits**:
- CSV file size: <2GB per file
- Total memory: <16GB for all data
- If larger: Consider Parquet format or database backend

---

## Error Handling

### Common Errors and Solutions

#### Configuration Errors

**Error**: `Summary definition not found: xyz`
- **Cause**: Referenced summary doesn't have YAML file
- **Solution**: Check `data_model/` for `summary_xyz.yaml`

**Error**: `Dataset directory not found: path/to/data`
- **Cause**: Invalid path in validation_config.yaml
- **Solution**: Verify path exists and is accessible

#### Data Errors

**Error**: `KeyError: 'hh_id'`
- **Cause**: CTRAMP CSV missing required column
- **Solution**: Validate data against CTRAMP data model schema

**Error**: `ValueError: invalid literal for int()`
- **Cause**: Data type mismatch (e.g., text in numeric column)
- **Solution**: Clean source data, check for NaN values

#### Processing Errors

**Error**: `MemoryError`
- **Cause**: Dataset too large for available RAM
- **Solution**: Process datasets sequentially, increase RAM, or sample data

**Error**: `Empty DataFrame after filtering`
- **Cause**: Filters too restrictive, removed all records
- **Solution**: Review filter specifications in summary YAML

### Logging and Debugging

**Enable Verbose Logging**:
```python
logging.basicConfig(level=logging.DEBUG)
```

**Log Output Example**:
```
2025-12-11 10:30:15 - INFO - Loading configuration from validation_config.yaml
2025-12-11 10:30:16 - INFO - Found 3 datasets, 25 summaries
2025-12-11 10:30:16 - INFO - Loading dataset: TM22_2015
2025-12-11 10:30:45 - INFO - Loaded 2,700,000 households
2025-12-11 10:30:58 - INFO - Generating summary: auto_ownership_regional
2025-12-11 10:31:03 - INFO - Wrote outputs/auto_ownership_regional.csv
```

---

## Next Steps

- **[User Guide](validation-system.md)**: High-level system overview
- **[Data Model Reference](data-model.md)**: Complete schema documentation
- **[Custom Summaries](custom-summaries.md)**: Create new summary definitions
- **[Dashboard Guide](deploy-dashboard.md)**: Customize visualizations
- **[Development Tasks](validation-development.md)**: Ongoing improvements

---

**Live Dashboard**: https://tm2-dashboard.streamlit.app/
