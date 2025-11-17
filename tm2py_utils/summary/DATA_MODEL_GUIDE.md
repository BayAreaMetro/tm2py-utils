# Data Model Separation Implementation Guide

## Overview
This guide explains how to completely separate the data model from the analysis code,
allowing the validation system to work with any activity-based model regardless of
column naming conventions.

## Architecture

```
data_model.yaml          # All schema, mappings, validations
       ↓
data_model_loader.py     # Loads YAML, provides API
       ↓
run_all_validation_summaries.py  # Uses only internal names
```

## Implementation Steps

### Step 1: Define Your Data Model (data_model.yaml)

The YAML file contains 6 main sections:

#### 1.1 Input Schema
```yaml
input_schema:
  persons:
    file_pattern: "personData_{iteration}.csv"
    columns:
      required:
        household_id: "hh_id"      # internal_name: "actual_csv_column"
        person_id: "person_id"
        person_number: "person_num"
      optional:
        person_type: "type"
        age: "age"
```

**Purpose**: Maps your actual CSV column names to standardized internal names.

**Customization**: 
- Change right side ("hh_id", "type") to match YOUR CSV files
- Left side (household_id, person_type) stays the same (used in code)

#### 1.2 Internal Schema
```yaml
internal_schema:
  persons:
    - household_id        # Standard name used in code
    - person_id
    - person_type
    - age
```

**Purpose**: Documents all possible internal column names the code can use.

**Customization**: Add new columns here if you extend the analysis.

#### 1.3 Relationships
```yaml
relationships:
  - parent: households
    child: persons
    parent_key: household_id
    child_key: household_id
```

**Purpose**: Defines how tables link together for validation.

**Customization**: Usually stays the same unless your model has different structure.

#### 1.4 Value Mappings
```yaml
value_mappings:
  person_type:
    type: categorical
    values:
      1: "Full-time worker"
      2: "Part-time worker"
    text_values:
      - "Full-time worker"
      - "Part-time worker"
```

**Purpose**: Maps codes to human-readable labels for reports.

**Customization**: Update values to match YOUR model's coding scheme.

#### 1.5 Summary Definitions
```yaml
summary_definitions:
  auto_ownership:
    description: "Vehicle ownership by household"
    input_tables: ["households"]
    required_columns:
      households: ["household_id", "num_vehicles", "sample_rate"]
    geographic_levels: ["regional", "county"]
    output_columns:
      - "num_vehicles"
      - "household_count"
```

**Purpose**: Declares what data each summary needs (using internal names).

**Customization**: Modify if you add new summaries or change requirements.

#### 1.6 Output Configuration
```yaml
output_configuration:
  filenames:
    auto_ownership_regional: "vehicle_ownership_regional.csv"
  column_renames:
    household_count: "households"
    percentage: "share_pct"
```

**Purpose**: Customizes output file and column names.

**Customization**: Change to match your reporting requirements.

---

### Step 2: Load Data Model in Code

```python
from data_model_loader import load_data_model

# Load data model
data_model = load_data_model(Path("data_model.yaml"))

# Now you can query it:
mapping = data_model.get_column_mapping("persons")
# Returns: {"hh_id": "household_id", "type": "person_type", ...}
```

---

### Step 3: Apply Mapping When Loading Data

**OLD CODE (hardcoded):**
```python
df = pd.read_csv("personData_1.csv")
workers = df[df['person_type'].isin([1, 2])]  # ASSUMES column is called 'person_type'
```

**NEW CODE (data model driven):**
```python
df = pd.read_csv("personData_1.csv")
df = data_model.apply_column_mapping(df, "persons")  # Maps CSV names → internal names
workers = df[df['person_type'].isin([1, 2])]  # NOW this works regardless of CSV name
```

---

### Step 4: Validate Required Columns Exist

```python
is_valid, missing = data_model.validate_dataframe(df, "persons")
if not is_valid:
    raise ValueError(f"Missing required columns: {missing}")
```

---

### Step 5: Use Internal Names Throughout Code

**ALL analysis code should only reference internal names:**

```python
# ✓ CORRECT - uses internal names
summary = df.groupby('person_type')['household_id'].count()

# ✗ WRONG - hardcodes CSV column name
summary = df.groupby('type')['hh_id'].count()  # Will break with different CSVs
```

---

### Step 6: Apply Value Mappings for Reports

```python
# Map codes to labels
df['person_type_label'] = df['person_type'].apply(
    lambda x: data_model.map_value('person_type', x)
)
# 1 → "Full-time worker", 2 → "Part-time worker"
```

---

### Step 7: Apply Output Configuration

```python
# Rename columns for output
output_df = data_model.rename_output_columns(summary_df)
# 'household_count' → 'households', 'percentage' → 'share_pct'

# Get custom filename
filename = data_model.get_output_filename('auto_ownership_regional', 
                                          'default_auto_ownership.csv')
output_df.to_csv(output_dir / filename, index=False)
```

---

## Code Refactoring Checklist

### Phase 1: Setup
- [x] Create data_model.yaml with your schema
- [x] Create data_model_loader.py module
- [ ] Add data_model parameter to DataLoader class
- [ ] Add data_model parameter to summary functions

### Phase 2: Remove Hardcoded Column Names
Find and replace ALL hardcoded column references:

- [ ] Replace `df['hh_id']` → `df['household_id']`
- [ ] Replace `df['person_type']` checks with internal name
- [ ] Replace `df['tour_purpose']` with internal name
- [ ] Replace `df['tour_mode']` with internal name
- [ ] Remove all column name strings from constants/code

### Phase 3: Add Mapping Logic
- [ ] Apply mapping in DataLoader.load_directory()
- [ ] Apply mapping in DataLoader.load_file()
- [ ] Validate columns after mapping
- [ ] Log mapping operations

### Phase 4: Update Summary Functions
- [ ] Pass data_model to all summary functions
- [ ] Use data_model.get_summary() to get column requirements
- [ ] Check optional columns before using them
- [ ] Apply value mappings for categorical fields

### Phase 5: Testing
- [ ] Test with original column names
- [ ] Test with different column names (modify data_model.yaml)
- [ ] Verify all summaries still work
- [ ] Check output files have correct names/columns

---

## Example: Refactoring a Summary Function

**BEFORE (hardcoded):**
```python
def summarize_tours(tour_data: pd.DataFrame) -> pd.DataFrame:
    if 'tour_purpose' in tour_data.columns:
        summary = tour_data.groupby('tour_purpose').size()
    else:
        logger.warning("No tour_purpose column")
        return pd.DataFrame()
    
    return summary
```

**AFTER (data model driven):**
```python
def summarize_tours(tour_data: pd.DataFrame, data_model: DataModel) -> pd.DataFrame:
    # Get required columns from data model
    required_cols = data_model.get_summary_required_columns('tour_frequency', 'tours')
    
    # Validate we have what we need
    is_valid, missing = data_model.validate_dataframe(tour_data, 'tours')
    if not is_valid:
        logger.error(f"Missing required columns: {missing}")
        return pd.DataFrame()
    
    # Use internal names (guaranteed to exist after mapping)
    summary = tour_data.groupby('tour_purpose').size().reset_index(name='tour_count')
    
    # Apply value mappings for readable labels
    summary['purpose_label'] = summary['tour_purpose'].apply(
        lambda x: data_model.map_value('tour_purpose', x)
    )
    
    # Apply output configuration
    summary = data_model.rename_output_columns(summary)
    
    return summary
```

---

## Benefits of This Approach

1. **Portability**: Works with any ABM that has similar data structure
2. **Maintainability**: Change column names in one place (YAML), not code
3. **Validation**: Automatic checking that required columns exist
4. **Documentation**: YAML serves as schema documentation
5. **Flexibility**: Easy to add new summaries or customize outputs
6. **Type Safety**: Pydantic models catch configuration errors early

---

## Migration Strategy

### Option A: Big Bang (Recommended for small codebases)
1. Update data_model.yaml with current schema
2. Refactor all code at once
3. Test thoroughly

### Option B: Incremental (Safer for large codebases)
1. Add data_model_loader.py
2. Keep old code working
3. Add `use_data_model=True` parameter
4. Refactor one summary at a time
5. Once all working, remove old code

---

## Common Pitfalls

❌ **Pitfall 1**: Forgetting to apply mapping after loading CSV
```python
df = pd.read_csv(file)
# FORGOT: df = data_model.apply_column_mapping(df, "persons")
workers = df[df['person_type'].isin([1, 2])]  # KeyError!
```

✓ **Solution**: Always apply mapping immediately after load

❌ **Pitfall 2**: Using CSV column names instead of internal names
```python
# data_model.yaml says: person_type: "type"
df = df[df['type'].isin([1, 2])]  # WRONG - uses CSV name
```

✓ **Solution**: Always use internal names in analysis code

❌ **Pitfall 3**: Not validating optional columns exist
```python
df['age_group'] = pd.cut(df['age'], bins=[0, 18, 65, 120])  # KeyError if age missing!
```

✓ **Solution**: Check optional columns first
```python
if 'age' in df.columns:
    df['age_group'] = pd.cut(df['age'], bins=[0, 18, 65, 120])
```

---

## Next Steps

1. **Review data_model.yaml**: Ensure it matches YOUR model's actual CSV structure
2. **Test data_model_loader.py**: Verify it loads correctly
3. **Plan refactoring**: Decide on Big Bang vs Incremental approach
4. **Refactor one function**: Start small, test thoroughly
5. **Expand gradually**: Refactor more functions once confident
6. **Document changes**: Update README with new configuration approach

## Questions to Answer Before Proceeding

1. Do your CSV files use different column names than shown in data_model.yaml?
2. Are there additional columns in your model not covered in the schema?
3. Do you have custom categorical value codes that need mapping?
4. What output file/column names do you prefer?
5. Do you want to tackle all refactoring at once or incrementally?

---

Let me know and we can proceed with the refactoring!
