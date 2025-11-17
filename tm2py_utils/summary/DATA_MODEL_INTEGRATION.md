# Data Model Integration

## Overview

The validation summary system now uses a **schema-driven approach** where column names and data structures are defined in a separate YAML data model file. This allows the code to work with any Activity-Based Model (ABM) by simply updating the data model configuration.

## Architecture

```
CSV Files (Model Outputs)
    ↓
ctramp_data_model.yaml (Column Mapping)
    ↓
DataLoader.load_directory() (Apply Mapping)
    ↓
DataFrames with Internal Standard Names
    ↓
Modular Summary Functions
    ↓
Validation Summaries
```

## Key Components

### 1. Data Model (`ctramp_data_model.yaml`)
- **Purpose**: Defines the schema for CTRAMP/TM2 model outputs
- **Location**: `tm2py_utils/summary/ctramp_data_model.yaml`
- **Size**: 973 lines, 127 fields, 6 tables
- **Structure**:
  - `input_schema`: Maps CSV column names → internal standard names
  - `internal_schema`: Defines all fields with descriptions and validation rules
  - `value_mappings`: Categorical value labels (e.g., person_type: 1=FTW, 2=PTW)
  - `summary_definitions`: Template definitions for output summaries
  - `validation_rules`: Data quality checks

**Example Mapping**:
```yaml
input_schema:
  households:
    num_vehicles: "autos"      # CSV has "autos", code uses "num_vehicles"
    num_persons: "size"        # CSV has "size", code uses "num_persons"
    income_category: "income"  # CSV has "income", code uses "income_category"
```

### 2. Data Model Loader (`ctramp_data_model_loader.py`)
- **Purpose**: Python API to query schema and apply transformations
- **Location**: `tm2py_utils/summary/ctramp_data_model_loader.py`
- **Key Classes**:
  - `DataModel`: Main interface
  - `ColumnSchema`: Field definition
  - `ValueMapping`: Categorical labels
  - `SummaryDefinition`: Output templates

**Key Methods**:
```python
data_model = load_data_model("ctramp_data_model.yaml")

# Apply column mapping: CSV names → internal names
mapped_df = data_model.apply_column_mapping(df, "households")

# Get field definition
schema = data_model.get_column_schema("households", "num_vehicles")

# Get value labels
labels = data_model.get_value_mapping("person_type")
```

### 3. Modular Summary Functions
All summary functions now use **internal standard names**:

- `household_summary.py`: Uses `num_vehicles`, `num_persons`, `income_category`
- `worker_summary.py`: Uses `person_type`, `work_location`, `telecommute`
- `tour_summary.py`: Uses `tour_purpose`, `tour_mode`, `start_period`, `end_period`
- `trip_summary.py`: Uses `trip_mode`, `destination_purpose`, `depart_hour`

### 4. Main Orchestrator (`run_all_validation_summaries.py`)
**Integration Points**:
1. **Line 33**: Imports data model loader
2. **Line 152-169**: DataLoader.__init__ loads data model
3. **Line 231-238**: load_directory() applies column mapping after reading CSV

## Usage

### For TM2py Users (Default)
No changes needed - the system automatically uses `ctramp_data_model.yaml`.

### For Other ABM Users
1. Copy `ctramp_data_model.yaml` → `your_model_data_model.yaml`
2. Update `input_schema` to match your CSV column names
3. Keep `internal_schema` names unchanged (or update both model + summaries)
4. Pass custom data model path:
```python
loader = DataLoader(
    file_specs=specs,
    data_model_path=Path("your_model_data_model.yaml")
)
```

## Internal Column Name Standards

### Households Table
- `hh_id`: Household identifier
- `num_vehicles`: Number of vehicles owned
- `num_persons`: Household size
- `income_category`: Income group (1-4)
- `home_zone_id`: Home TAZ/MAZ

### Persons Table  
- `person_id`: Person identifier
- `hh_id`: Household identifier
- `person_type`: Employment status (1=FTW, 2=PTW, 3=university, 4=non-worker, etc.)
- `age`: Person age
- `gender`: 1=Male, 2=Female

### Tours Table
- `tour_id`: Tour identifier
- `person_id`: Person identifier
- `tour_purpose`: Purpose code (1=work, 2=university, 3=school, etc.)
- `tour_mode`: Mode choice (1=SOV, 2=HOV2, 3=HOV3+, etc.)
- `start_period`: Departure time period
- `end_period`: Arrival time period

### Trips Table
- `trip_id`: Trip identifier  
- `tour_id`: Parent tour identifier
- `trip_mode`: Mode choice
- `destination_purpose`: Purpose at destination
- `depart_hour`: Departure hour (0-23)

## Benefits

### Portability
- **Any ABM**: Works with ActivitySim, CT-RAMP, DaySim, etc.
- **Configuration Only**: No code changes needed
- **Version Flexibility**: Handle different model versions

### Maintainability
- **Single Source of Truth**: All schema in one YAML file
- **Documentation**: Field descriptions, value labels, validation rules in one place
- **Code Clarity**: Functions use clear semantic names (not CSV abbreviations)

### Quality
- **Validation**: Data model enforces required fields, data types, value ranges
- **Consistency**: All summaries use same standard names
- **Debugging**: Easy to trace column name issues

## Migration from Old System

### Before (Hardcoded)
```python
# Code directly used CSV column names
auto_summary = hh_data.groupby('autos').size()
size_summary = hh_data.groupby('size').size()
income_summary = hh_data.groupby('income').size()
```

### After (Schema-Driven)
```python
# DataLoader maps CSV → internal names automatically
mapped_df = data_model.apply_column_mapping(hh_data, "households")

# Code uses semantic internal names
auto_summary = mapped_df.groupby('num_vehicles').size()
size_summary = mapped_df.groupby('num_persons').size()  
income_summary = mapped_df.groupby('income_category').size()
```

## Testing

### Verify Integration
```python
from tm2py_utils.summary.ctramp_data_model_loader import load_data_model
from pathlib import Path

# Load data model
data_model = load_data_model(Path("ctramp_data_model.yaml"))

# Test column mapping
import pandas as pd
df = pd.DataFrame({'autos': [1, 2], 'size': [2, 3], 'income': [1, 2]})
mapped = data_model.apply_column_mapping(df, "households")

# Check internal names present
assert 'num_vehicles' in mapped.columns
assert 'num_persons' in mapped.columns
assert 'income_category' in mapped.columns
```

### Run Validation Summaries
```bash
python -m tm2py_utils.summary.run_all_validation_summaries \
    --config validation_config.yaml \
    --output-dir results/
```

## Future Enhancements

### Planned
- [ ] Auto-generate summary definitions from data model
- [ ] Support for multiple data model versions (TM1 vs TM2)
- [ ] Web UI for data model editing
- [ ] Validation rule execution engine
- [ ] Unit tests for each summary function

### Considered
- [ ] Database backend for large datasets
- [ ] Streaming processing for memory efficiency
- [ ] Parallel summary generation
- [ ] Interactive dashboard for results

## References

- **TM2py Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/
- **Data Model Schema**: `ctramp_data_model.yaml`
- **Loader API**: `ctramp_data_model_loader.py`
- **Summary Functions**: `validation/` directory
