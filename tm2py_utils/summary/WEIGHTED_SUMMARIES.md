# Weighted Summary Calculations

## Overview

All validation summaries now support **weighted calculations** to properly handle:
- **Sample expansion**: Model outputs with sampling (e.g., 50% sample → sample_rate=2.0)
- **Survey weights**: Travel survey data with person/household weights
- **Population estimation**: Converting sample data to population totals

## How It Works

### 1. Weight Field Configuration (`ctramp_data_model.yaml`)

```yaml
weight_fields:
  households:
    field: "sample_rate"
    description: "Household expansion factor - inverse of sampling rate"
    calculate_weighted: true
    default_value: 1.0
  
  persons:
    field: "sample_rate"
    description: "Person expansion factor - inherited from household"
    calculate_weighted: true
    default_value: 1.0
  
  tours:
    field: "sample_rate"
    description: "Tour expansion factor"
    calculate_weighted: true
    default_value: 1.0
  
  trips:
    field: "sample_rate"
    description: "Trip expansion factor"
    calculate_weighted: true
    default_value: 1.0
```

**Key Fields**:
- `field`: Column name containing weights (e.g., "sample_rate", "weight", "expansion_factor")
- `description`: Human-readable description
- `calculate_weighted`: Whether to use weights (true) or raw counts (false)
- `default_value`: Default weight if column is missing (usually 1.0 for unweighted)

### 2. Data Model Loader API

The `ctramp_data_model_loader.py` provides methods to query weight configuration:

```python
from tm2py_utils.summary.ctramp_data_model_loader import load_data_model

data_model = load_data_model()

# Get weight column name
weight_col = data_model.get_weight_field('households')  # Returns: "sample_rate"

# Check if weights are configured
if data_model.has_weights('households'):
    print("Weights available")

# Check if weighted calculations should be performed
if data_model.should_calculate_weighted('households'):
    print("Use weighted calculations")

# Ensure DataFrame has weight column
df = data_model.ensure_weight_column(df, 'households')
```

### 3. Summary Function Updates

All summary functions now accept an optional `weight_col` parameter:

```python
# household_summary.py
def generate_auto_ownership_summary(
    hh_data: pd.DataFrame, 
    dataset_name: str,
    weight_col: Optional[str] = None  # NEW: weight column parameter
) -> Dict[str, pd.DataFrame]:
    # ...
```

**Weighted vs Unweighted Logic**:

```python
# Determine if we use weighted or unweighted counts
use_weights = weight_col is not None and weight_col in hh_data.columns

# Weighted count - sum the weights
if use_weights:
    summary = (hh_data.groupby('num_vehicles')[weight_col]
              .sum()
              .reset_index(name='households'))
else:
    # Unweighted count - count rows
    summary = (hh_data.groupby('num_vehicles')
              .size()
              .reset_index(name='households'))

# Calculate share (same for both)
summary['share'] = summary['households'] / summary['households'].sum() * 100
```

### 4. Main Orchestrator Integration

`run_all_validation_summaries.py` automatically passes weight columns:

```python
# Get weight field from data model
weight_col = None
if hasattr(self, 'data_model') and self.data_model:
    weight_col = self.data_model.get_weight_field('households')

# Pass to summary function
all_summaries.update(
    household_summary.generate_all_household_summaries(
        data['households'], 
        dataset_name, 
        weight_col  # Automatically passed
    )
)
```

## Examples

### Example 1: 50% Sample Model Run

**Input Data** (`householdData_1.csv`):
```csv
hh_id,autos,size,income,sampleRate
1,2,3,2,2.0
2,1,2,1,2.0
3,0,1,1,2.0
```

**Without Weights** (raw counts):
```
num_vehicles | households | share
0            | 1          | 33.3%
1            | 1          | 33.3%
2            | 1          | 33.3%
Total        | 3          | 100%
```

**With Weights** (sample_rate=2.0, estimated population):
```
num_vehicles | households | share
0            | 2.0        | 33.3%
1            | 2.0        | 33.3%
2            | 2.0        | 33.3%
Total        | 6.0        | 100%
```

### Example 2: Travel Survey with Variable Weights

**Input Data** (`survey_households.csv`):
```csv
hh_id,autos,size,income,weight
101,2,3,2,15.5
102,1,2,1,22.3
103,0,1,1,18.7
104,2,4,3,12.1
```

**Configuration**:
```yaml
weight_fields:
  households:
    field: "weight"  # Changed from "sample_rate" to "weight"
    calculate_weighted: true
```

**With Weights** (variable survey weights):
```
num_vehicles | households | share
0            | 18.7       | 27.3%
1            | 22.3       | 32.6%
2            | 27.6       | 40.2%
Total        | 68.6       | 100%
```

### Example 3: Full Enumeration (No Sampling)

**Input Data** (`householdData_full.csv`):
```csv
hh_id,autos,size,income
1,2,3,2
2,1,2,1
3,0,1,1
```

**Configuration**:
```yaml
weight_fields:
  households:
    field: "sample_rate"
    calculate_weighted: true
    default_value: 1.0  # Used when column missing
```

**Result** (default weight=1.0 applied automatically):
```
num_vehicles | households | share
0            | 1.0        | 33.3%
1            | 1.0        | 33.3%
2            | 1.0        | 33.3%
Total        | 3.0        | 100%
```

## Utility Functions

The `validation/summary_utils.py` module provides reusable helpers:

```python
from tm2py_utils.summary.validation.summary_utils import (
    weighted_groupby_count,
    add_share_column,
    weighted_mean,
    log_weight_info
)

# Weighted groupby
summary = weighted_groupby_count(
    df, 
    groupby_cols=['num_vehicles'], 
    weight_col='sample_rate',
    count_name='households'
)

# Add share column
summary = add_share_column(summary, count_col='households', share_col='share')

# Weighted mean
avg_income = weighted_mean(df, value_col='income', weight_col='sample_rate')

# Log weight usage
log_weight_info('model_run_1', 'sample_rate', df)
# Output: ℹ Using weighted counts for model_run_1 (total weight=50,000)
```

## Updated Summary Modules

### ✅ Completed
- **household_summary.py**: All functions support `weight_col` parameter
  - `generate_auto_ownership_summary()`
  - `generate_household_size_summary()`
  - `generate_income_summary()`
  - `generate_all_household_summaries()`

### ⏳ TODO
- **worker_summary.py**: Needs `weight_col` parameter added
  - `generate_work_location_summary()`
  - `generate_telecommute_summary()`
  - `generate_worker_demographics_summary()`
  - `generate_all_worker_summaries()`

- **tour_summary.py**: Needs `weight_col` parameter added
  - `generate_tour_purpose_summary()`
  - `generate_tour_mode_summary()`
  - `generate_tour_tod_summary()`
  - `generate_all_tour_summaries()`

- **trip_summary.py**: Needs `weight_col` parameter added
  - `generate_trip_mode_summary()`
  - `generate_trip_purpose_summary()`
  - `generate_trip_tod_summary()`
  - `generate_all_trip_summaries()`

## Customization for Other ABMs

### Different Weight Column Name

If your ABM uses a different weight column name:

```yaml
# In ctramp_data_model.yaml or your_model_data_model.yaml
weight_fields:
  households:
    field: "expansion_factor"  # Instead of "sample_rate"
    calculate_weighted: true
    default_value: 1.0
```

### No Weights (Full Enumeration)

To disable weighted calculations:

```yaml
weight_fields:
  households:
    field: null
    calculate_weighted: false
    default_value: 1.0
```

Or simply omit the weight_col parameter when calling summary functions:

```python
# Unweighted
summaries = generate_all_household_summaries(hh_data, "dataset_1")

# Weighted
summaries = generate_all_household_summaries(hh_data, "dataset_1", "sample_rate")
```

## Benefits

1. **Accurate Population Estimation**: Convert sample data to population totals
2. **Survey Data Support**: Handle variable survey weights
3. **Flexible**: Works with or without weights
4. **Backward Compatible**: Existing code works without changes (weights optional)
5. **Configurable**: Change weight column via YAML, no code changes needed

## Technical Notes

### Why Sum Weights Instead of Count?

When using weighted calculations:
- **Unweighted**: `df.groupby('category').size()` → counts rows
- **Weighted**: `df.groupby('category')[weight_col].sum()` → sums weights

**Example**:
```python
# Data: 3 households from 50% sample
hh_id | category | sample_rate
1     | A        | 2.0
2     | A        | 2.0  
3     | B        | 2.0

# Unweighted count
A: 2 households
B: 1 household

# Weighted count (population estimate)
A: 2×2.0 = 4.0 households
B: 1×2.0 = 2.0 households
```

### Shares Calculation

Shares are always calculated the same way (weighted or unweighted):
```python
share = count / total * 100
```

This ensures shares sum to 100% regardless of whether counts are weighted.

### Missing Weight Column Handling

If `weight_col` is specified but not found:
1. Warning logged: `"Weight column 'sample_rate' not found"`
2. Falls back to unweighted counting
3. Continues processing (doesn't fail)

## Migration Guide

### For Existing Code

No changes required! Weights are optional:

```python
# Old code still works (unweighted)
summaries = generate_all_household_summaries(hh_data, "dataset_1")

# New code with weights
summaries = generate_all_household_summaries(hh_data, "dataset_1", "sample_rate")
```

### For New Summary Functions

Template for adding weight support:

```python
def generate_my_summary(
    df: pd.DataFrame, 
    dataset_name: str,
    weight_col: Optional[str] = None  # Add this parameter
) -> Dict[str, pd.DataFrame]:
    
    # Check if weights available
    use_weights = weight_col is not None and weight_col in df.columns
    
    # Weighted or unweighted groupby
    if use_weights:
        summary = df.groupby('field')[weight_col].sum().reset_index(name='count')
    else:
        summary = df.groupby('field').size().reset_index(name='count')
    
    # Rest of logic (same for both)
    summary['share'] = summary['count'] / summary['count'].sum() * 100
    
    return {'my_summary': summary}
```

## References

- **Data Model**: `ctramp_data_model.yaml` → `weight_fields` section
- **Loader API**: `ctramp_data_model_loader.py` → `get_weight_field()`, `ensure_weight_column()`
- **Utilities**: `validation/summary_utils.py` → helper functions
- **Example**: `validation/household_summary.py` → complete implementation
