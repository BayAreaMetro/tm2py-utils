# Validation System Development Tasks

This page tracks **ongoing development work** for the validation summary system. These are tasks that need to be completed to make the system fully functional for TM2.2 calibration and validation.

---

## 1. Update Data Model with New Postprocessing Fields

### Current Status

The CTRAMP data model is being **enhanced with additional fields** from model postprocessing. The current data model (documented in [data-model.md](data-model.md)) reflects the core CTRAMP outputs, but several important fields are missing.

### Required Updates

**New fields being added to model outputs:**
- Income categories (aggregated from continuous income)
- Distance bins for tours and trips
- Time period aggregations
- Mode aggregations (Auto/Transit/Active)
- Geography lookups (TAZ → County, MAZ → TAZ)
- Additional person/household categorizations

### Task: Update Data Model Documentation

When new fields are added to the postprocessing pipeline, you must **update the data model documentation** to reflect the changes.

**Steps:**

1. **Identify new fields** in the postprocessed output files
   ```powershell
   # Check actual columns in model outputs
   cd C:\model_runs\2023_base_year\ctramp_output
   python -c "import pandas as pd; df = pd.read_csv('householdData_1.csv', nrows=1); print(df.columns.tolist())"
   ```

2. **Update data-model.md** with new field definitions

   Add new fields to the appropriate table (households, persons, tours, trips):

   ```markdown
   ### New Postprocessed Fields

   | Column | Type | Description | Values/Range | Required |
   |--------|------|-------------|--------------|----------|
   | income_category | string | Household income quartile | Q1, Q2, Q3, Q4 | Optional |
   | county_name | string | County name from TAZ lookup | Alameda, Contra Costa, etc. | Optional |
   | tour_distance_bin | string | Binned tour distance | 0-5, 5-10, 10-25, 25+ | Optional |
   ```

3. **Document derivation logic**

   Explain how new fields are calculated:

   ```markdown
   **Income Category Derivation:**
   - Q1: income < $30,000
   - Q2: $30,000 - $60,000
   - Q3: $60,000 - $100,000
   - Q4: $100,000+

   **County Name Derivation:**
   - Lookup from TAZ to County using geography crosswalk file
   - Requires `taz_geography.csv` with columns: `taz`, `county_name`
   ```

4. **Update example schemas**

   Modify the sample CSV structure to include new fields:

   ```csv
   hh_id,income,income_category,taz,county_name,num_persons,num_workers,num_vehicles
   1,45000,Q2,1001,Alameda,2,1,1
   ```

5. **Update summary configurations** that use new fields

   If summaries reference new fields, update `validation_config.yaml`:

   ```yaml
   summaries:
     - name: "auto_ownership_by_income_category"
       data_source: "households"
       group_by:
         - "income_category"  # NEW FIELD
         - "num_vehicles"
   ```

### Affected Components

- ✏️ **data-model.md** - Add new field definitions
- ✏️ **validation_config.yaml** - Update summaries using new fields
- ✏️ **custom-summaries.md** - Add examples using new fields
- ✏️ **Postprocessing scripts** - Document where fields are created

---

## 2. Prepare 2023 Household Travel Survey Data

### Current Status

The **2023 household travel survey data** is being prepared for validation. This survey provides observed trip-making behavior for comparison with model outputs.

### Required Format

The survey data **must be transformed to exactly match the CTRAMP data model** (see [data-model.md](data-model.md)). This is a **non-negotiable requirement** - the validation system expects identical schemas.

### Task: Convert Survey to CTRAMP Format

You must create **4 CSV files** with the same structure as CTRAMP model outputs:

#### File 1: `householdData_survey.csv`

**Required columns** (at minimum):

| Column | Description | Notes |
|--------|-------------|-------|
| `hh_id` | Household ID | Unique identifier from survey |
| `home_taz` | Home TAZ | Map survey home location to TM2.2 TAZ system |
| `income` | Annual household income | Continuous dollar amount |
| `num_persons` | Household size | Count of persons |
| `num_workers` | Number of workers | Count of workers |
| `num_vehicles` | Number of vehicles | Count of vehicles |
| `building_type` | Housing type | 1=Single Family, 2=Multi-Family, 3=Mobile Home, 4=Other |
| `sample_rate` | Sample expansion factor | Survey weight for expanding to population |

**Derived fields** (if using new postprocessed data model):

| Column | Description | Derivation |
|--------|-------------|------------|
| `income_category` | Income quartile | Bin `income` into Q1/Q2/Q3/Q4 |
| `county_name` | County name | Map `home_taz` to county |
| `num_persons_agg` | Aggregated household size | Aggregate to 1/2/3/4+ |

**Example transformation:**

```python
import pandas as pd

# Load survey household data
survey_hh = pd.read_csv('survey_households_raw.csv')

# Map to CTRAMP format
ctramp_hh = pd.DataFrame({
    'hh_id': survey_hh['household_id'],
    'home_taz': survey_hh['home_taz_tm22'],  # Must use TM2.2 TAZ system
    'income': survey_hh['annual_income'],
    'num_persons': survey_hh['household_size'],
    'num_workers': survey_hh['workers'],
    'num_vehicles': survey_hh['vehicles'],
    'building_type': survey_hh['housing_type'].map({
        'Single Family': 1,
        'Multi-Family': 2,
        'Mobile Home': 3,
        'Other': 4
    }),
    'sample_rate': survey_hh['expansion_factor']  # Survey weight
})

# Add derived fields (if using enhanced data model)
ctramp_hh['income_category'] = pd.cut(ctramp_hh['income'], 
    bins=[0, 30000, 60000, 100000, float('inf')],
    labels=['Q1', 'Q2', 'Q3', 'Q4'])

ctramp_hh['num_persons_agg'] = ctramp_hh['num_persons'].apply(
    lambda x: '4+' if x >= 4 else str(x)
)

# Save in CTRAMP format
ctramp_hh.to_csv('householdData_survey.csv', index=False)
```

#### File 2: `personData_survey.csv`

**Required columns:**

| Column | Description | Notes |
|--------|-------------|-------|
| `person_id` | Person ID | Unique identifier |
| `hh_id` | Household ID | Links to household file |
| `person_num` | Person number in household | 1, 2, 3, etc. |
| `person_type` | Person type code | 1-8 (see data-model.md) |
| `age` | Age in years | Continuous |
| `gender` | Gender | 1=Male, 2=Female |
| `work_taz` | Work location TAZ | -1 if not working |
| `school_taz` | School location TAZ | -1 if not in school |

**Person type mapping** (critical for CDAP summaries):

```python
def map_person_type(row):
    """Map survey person characteristics to CTRAMP person_type codes"""
    if row['age'] < 5:
        return 8  # Preschool
    elif row['age'] < 16:
        return 7 if row['enrolled_in_school'] else 8  # School age
    elif row['age'] < 18:
        return 6  # Driving age student
    elif row['full_time_worker']:
        return 1  # Full-time worker
    elif row['part_time_worker']:
        return 2  # Part-time worker
    elif row['enrolled_in_university']:
        return 3  # University student
    elif row['age'] >= 65:
        return 5  # Retired
    else:
        return 4  # Non-working adult

survey_persons['person_type'] = survey_persons.apply(map_person_type, axis=1)
```

#### File 3: `indivTourData_survey.csv`

**Required columns:**

| Column | Description | Notes |
|--------|-------------|-------|
| `tour_id` | Tour ID | Unique identifier |
| `person_id` | Person ID | Links to person file |
| `hh_id` | Household ID | Links to household file |
| `tour_purpose` | Primary tour purpose | Work, School, Shop, Discretionary, etc. |
| `tour_mode` | Primary tour mode | 1-17 (see data-model.md) |
| `start_period` | Departure time period | 1-40 (half-hour periods) |
| `end_period` | Return time period | 1-40 |
| `tour_distance` | Total tour distance (miles) | Round-trip distance |
| `num_ob_stops` | Outbound stops | Intermediate stops before primary destination |
| `num_ib_stops` | Inbound stops | Intermediate stops on return |

**Mode code mapping** (see data-model.md for full list):

```python
mode_mapping = {
    'Drive Alone': 1,
    'Shared Ride 2': 2,
    'Shared Ride 3+': 3,
    'Walk to Transit': 4,
    'Drive to Transit': 5,
    'Walk': 6,
    'Bike': 7,
    # ... (see data-model.md for codes 8-17)
}

survey_tours['tour_mode'] = survey_tours['mode_description'].map(mode_mapping)
```

**Time period mapping** (5:00 AM = period 1, 30-minute increments):

```python
def time_to_period(time_str):
    """Convert time string to period number (1-40)"""
    hour, minute = map(int, time_str.split(':'))
    total_minutes = (hour - 5) * 60 + minute  # Minutes since 5:00 AM
    period = (total_minutes // 30) + 1
    return max(1, min(40, period))  # Clamp to 1-40

survey_tours['start_period'] = survey_tours['departure_time'].apply(time_to_period)
survey_tours['end_period'] = survey_tours['return_time'].apply(time_to_period)
```

#### File 4: `indivTripData_survey.csv`

**Required columns:**

| Column | Description | Notes |
|--------|-------------|-------|
| `trip_id` | Trip ID | Unique identifier |
| `person_id` | Person ID | Links to person file |
| `hh_id` | Household ID | Links to household file |
| `tour_id` | Parent tour ID | Links to tour file |
| `trip_mode` | Trip mode | 1-17 (same codes as tour_mode) |
| `trip_purpose` | Trip purpose | Work, School, Shop, Eat, Discretionary, etc. |
| `origin_taz` | Origin TAZ | Trip origin |
| `destination_taz` | Destination TAZ | Trip destination |
| `trip_distance` | Trip distance (miles) | One-way distance |
| `depart_period` | Departure time period | 1-40 |

### Integration with Validation System

Once survey data is in CTRAMP format, add to `validation_config.yaml`:

```yaml
input_directories:
  - path: "C:/model_runs/2023_base_year"
    name: "2023_base_year"
    display_name: "2023 Base Year Model"
    source_type: "model"
    iteration: 1

  - path: "C:/survey_data/2023_household_travel_survey"
    name: "2023_survey"
    display_name: "2023 Household Travel Survey"
    source_type: "survey"
    iteration: 1  # Use _1.csv suffix or omit iteration for no suffix
```

The system will then:
1. Load survey data alongside model outputs
2. Apply same aggregations and binning
3. Compare model vs. survey in dashboard

### Critical Notes

⚠️ **Geography Alignment**: Survey TAZs must match TM2.2 TAZ system exactly. If survey uses different geography, you must **crosswalk** locations.

⚠️ **Sample Weights**: `sample_rate` is critical for accurate aggregation. Survey weights expand sample to represent full population.

⚠️ **Mode/Purpose Codes**: Must use exact CTRAMP codes. Do NOT create custom categories - map to standard codes.

⚠️ **Intersects with Task 1**: If new postprocessed fields are added to data model, survey data must include those fields too (e.g., `income_category`, `county_name`).

---

## 3. Fix Non-Working Summaries

### Current Status

Some summaries defined in `validation_config.yaml` have **errors** and do not generate output correctly. These will be **obvious on the dashboard** - charts will be missing or show errors.

### Task: Debug and Fix Broken Summaries

**Steps to identify broken summaries:**

1. **Run full summary generation**

   ```powershell
   cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
   conda activate tm2py-utils
   python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
   ```

2. **Check console output for errors**

   Look for:
   - `KeyError` - Missing column in data
   - `ValueError` - Invalid binning or grouping
   - `FileNotFoundError` - Missing input files
   - Empty DataFrames - No data after filtering

3. **Identify missing output files**

   ```powershell
   cd outputs/dashboard
   Get-ChildItem *.csv | Measure-Object  # Should be 25 files
   ```

   Compare to expected summaries in `validation_config.yaml`.

4. **Debug specific summary**

   For each broken summary, check:

   **a) Column names match data model**

   ```yaml
   summaries:
     - name: "broken_summary"
       group_by:
         - "tour_mode"  # Does this column exist in indivTourData_1.csv?
   ```

   Fix: Use actual column name from data model

   **b) Binning spec references valid columns**

   ```yaml
   binning_specs:
     tour_distance_bins:
       column: "tour_distance"  # Does this column exist?
       bins: [0, 5, 10, 25, 100]
   ```

   Fix: Add missing column to data model (Task 1) or remove binning

   **c) Aggregation spec references valid categories**

   ```yaml
   aggregation_specs:
     mode_groups:
       column: "tour_mode"
       mapping:
         Auto: [1, 2, 3]  # Are these valid tour_mode codes?
   ```

   Fix: Use correct mode codes from data-model.md

   **d) Filters use valid syntax**

   ```yaml
   summaries:
     - name: "commute_tours"
       filter: "tour_purpose == 'Work'"  # Quotes correct? Column exists?
   ```

   Fix: Use pandas query syntax, check column names

5. **Test fix**

   Run single summary to verify:

   ```python
   from tm2py_utils.summary.validation.summaries.run_all import generate_summary
   
   # Test specific summary
   generate_summary('broken_summary', config)
   ```

### Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| `KeyError: 'tour_distance'` | Column doesn't exist in data | Add to data model (Task 1) or remove from config |
| `Empty DataFrame after groupby` | Filter too restrictive | Check filter syntax, verify data exists |
| `ValueError: bins must be monotonic` | Invalid bin edges | Fix bin specification in `binning_specs` |
| `No observed data for summary` | Missing observed_summaries config | Add external data (Task 5) or remove comparison |

### Expected Output

After fixes, all 25 summaries should generate without errors:

```
Processing summary: auto_ownership_regional... ✓
Processing summary: auto_ownership_by_county... ✓
Processing summary: auto_ownership_by_household_size... ✓
...
All summaries completed successfully!
```

---

## 4. Build Additional Summaries from Calibration/Validation Spreadsheet

### Current Status

The system has **25 pre-configured summaries**, but the **calibration/validation spreadsheet** lists additional validation targets that need summary generation.

### Task: Add New Summaries from Spreadsheet

**Steps:**

1. **Review calibration/validation spreadsheet**

   Identify targets not currently covered by the 25 summaries. Look for:
   - Additional geography breakdowns (e.g., by district, superdistrict)
   - New cross-tabulations (e.g., mode by income AND household size)
   - Time-of-day summaries not yet implemented
   - Trip length distributions by purpose/mode combinations

2. **Design summary configuration**

   For each new target, create a summary specification. See [custom-summaries.md](custom-summaries.md) for examples.

   **Example:** Add "Trip Mode by Income and Household Size"

   ```yaml
   summaries:
     - name: "trip_mode_by_income_household_size"
       description: "Trip mode shares by income category and household size"
       data_source: "trips"
       group_by:
         - "income_category"  # Requires Task 1 - new field
         - "num_persons_agg"
         - "trip_mode"
       metrics:
         - column: "trip_id"
           aggregation: "count"
           output_name: "trips"
       share_within:
         - ["income_category", "num_persons_agg"]
       weight_column: "sample_rate"
       aggregation_specs:
         - "mode_groups"  # Group modes into Auto/Transit/Active
         - "household_size_4plus"
   ```

3. **Add required binning/aggregation specs**

   If new summary requires custom bins or aggregations:

   ```yaml
   binning_specs:
     income_quartiles:  # For income_category
       column: "income"
       bins: [0, 30000, 60000, 100000, 999999]
       labels: ["Q1", "Q2", "Q3", "Q4"]
       output_column: "income_category"
   
   aggregation_specs:
     mode_groups:
       column: "trip_mode"
       mapping:
         Auto: [1, 2, 3]
         Transit: [4, 5, 6, 7, 8, 9, 10, 11, 12]
         Active: [13, 14]
       output_column: "mode_group"
   ```

4. **Test new summary**

   ```powershell
   # Run validation with new summary added
   python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
   
   # Check output
   cd outputs/dashboard
   Get-Content trip_mode_by_income_household_size.csv | Select-Object -First 10
   ```

5. **Add to dashboard** (if desired)

   Create chart configuration in appropriate dashboard YAML:

   ```yaml
   # In dashboard-trips.yaml
   layout:
     trip_mode_by_income:
       - type: bar
         title: "Trip Mode by Income and Household Size"
         props:
           dataset: "trip_mode_by_income_household_size.csv"
           x: "income_category"
           y: "share"
           groupBy: "mode_group"
           facet: "num_persons_agg"
         description: "Trip mode shares across income categories, by household size"
   ```

### Prioritization

**High Priority** (required for calibration):
- VMT by facility type and time period
- Transit boardings by line and time period
- Work location by residence district
- Mode shares for work and school tours

**Medium Priority** (validation targets):
- Trip length distributions by mode and purpose
- Activity participation rates by person type
- Auto occupancy by purpose
- Park-and-ride usage

**Low Priority** (nice to have):
- Detailed origin-destination patterns
- Toll facility usage
- Non-motorized trip characteristics

### Documentation

After adding new summaries, update **generate-summaries.md**:

```markdown
### Additional Summaries (Custom Configured)

| Summary | Description | Geography | Source |
|---------|-------------|-----------|--------|
| trip_mode_by_income_household_size | Trip mode shares by income and household size | Regional | Trips |
| vmt_by_facility_time | VMT by facility type and time period | Regional | Network |
```

---

## 5. Reformat CTPP Data to Match System

### Current Status

**Census Transportation Planning Products (CTPP)** data provides observed journey-to-work patterns but is **not currently formatted** for the validation system.

### Required Format

CTPP data must be **preprocessed into the same format as model summaries** - same columns, same categories, same geography. See [external-data.md](external-data.md) for detailed guidance.

### Task: Create CTPP Preprocessing Script

**Goal:** Convert CTPP tables into CSV files that match model summary output format.

#### Step 1: Identify Relevant CTPP Tables

**Key tables for TM2.2 validation:**

| Table | Description | Validation Use |
|-------|-------------|----------------|
| A302100 | Workers by Work Location | Work location choice |
| A302200 | Workers by Mode to Work | Commute mode choice |
| A102100 | Workers by Residence | Home-work flow patterns |
| B302105 | Travel Time to Work | Commute time distributions |

#### Step 2: Map CTPP Geography to TM2.2 Geography

CTPP uses **Census geographies** (tracts, PUMAs, counties). TM2.2 uses **TAZs**.

**Create geography crosswalk:**

```python
import pandas as pd

# Load CTPP data (by county)
ctpp = pd.read_csv('ctpp_a302200_workers_by_mode.csv')
# Columns: county_fips, mode_category, workers

# Load TM2.2 county mapping
taz_county = pd.read_csv('taz_to_county.csv')
# Columns: taz, county_name, county_fips

# Map county_fips to county_name
county_mapping = taz_county[['county_fips', 'county_name']].drop_duplicates()
ctpp = ctpp.merge(county_mapping, on='county_fips')
```

#### Step 3: Map CTPP Categories to CTRAMP Codes

**Mode mapping example:**

```python
# CTPP mode categories
ctpp_mode_mapping = {
    'Car, truck, or van -- Drove alone': 'Drive Alone',
    'Car, truck, or van -- Carpooled: 2-person': 'Shared Ride 2',
    'Car, truck, or van -- Carpooled: 3-or-more': 'Shared Ride 3+',
    'Public transportation': 'Transit',
    'Walked': 'Walk',
    'Bicycle': 'Bike',
    'Taxicab, motorcycle, or other means': 'Other',
    'Worked at home': 'Work from Home'
}

ctpp['tour_mode'] = ctpp['mode_category'].map(ctpp_mode_mapping)
```

**Aggregate to match model summary:**

```python
# Model summary has mode_group aggregation (Auto/Transit/Active)
mode_group_mapping = {
    'Drive Alone': 'Auto',
    'Shared Ride 2': 'Auto',
    'Shared Ride 3+': 'Auto',
    'Transit': 'Transit',
    'Walk': 'Active',
    'Bike': 'Active',
    'Other': 'Other',
    'Work from Home': 'Other'
}

ctpp['mode_group'] = ctpp['tour_mode'].map(mode_group_mapping)
```

#### Step 4: Calculate Shares

Match model summary metric structure:

```python
# Group by county and mode_group
ctpp_summary = ctpp.groupby(['county_name', 'mode_group']).agg({
    'workers': 'sum'
}).reset_index()

# Calculate shares within each county
ctpp_summary['share'] = ctpp_summary.groupby('county_name')['workers'].transform(
    lambda x: x / x.sum()
)

# Add dataset identifier
ctpp_summary['dataset'] = 'CTPP 2016-2020'
```

#### Step 5: Match Model Summary Column Names

Ensure columns match exactly:

```python
# Model summary: work_mode_by_county.csv
# Columns: county_name, mode_group, workers, share, dataset

ctpp_formatted = ctpp_summary[[
    'county_name',
    'mode_group', 
    'workers',
    'share',
    'dataset'
]]

# Save in same format as model summary
ctpp_formatted.to_csv('work_mode_by_county_ctpp.csv', index=False)
```

#### Step 6: Add to Validation Config

```yaml
observed_summaries:
  - name: "work_mode_by_county_ctpp"
    file_path: "C:/validation_data/ctpp/work_mode_by_county_ctpp.csv"
    description: "CTPP 2016-2020 work mode by county"
    dataset_name: "CTPP 2016-2020"
    
    column_mapping:
      dimensions:
        county_name: "county_name"
        mode_group: "mode_group"
      metrics:
        workers: "workers"
        share: "share"
```

### CTPP Tables to Process

**Priority 1** (commute patterns):
- A302200: Mode to work by residence
- A302100: Workers by workplace
- B302105: Travel time to work

**Priority 2** (demographics):
- A101102: Household size
- A101103: Household income
- A101104: Vehicles available

**Priority 3** (detailed flows):
- A302106: Residence-workplace flows by mode
- A302107: Residence-workplace flows by time

### Preprocessing Script Template

```python
"""
CTPP Preprocessing for TM2.2 Validation System

Converts CTPP tables to match model summary format
"""

import pandas as pd
import numpy as np

def process_ctpp_mode_choice(ctpp_file, county_mapping_file, output_file):
    """
    Process CTPP A302200 (Mode to Work) table
    
    Args:
        ctpp_file: Path to CTPP CSV
        county_mapping_file: Path to county mapping
        output_file: Path for output CSV
    """
    # Load CTPP data
    ctpp = pd.read_csv(ctpp_file)
    
    # Load county mapping
    counties = pd.read_csv(county_mapping_file)
    
    # Map CTPP mode categories to model mode groups
    mode_mapping = {
        'Drove alone': 'Auto',
        'Carpooled': 'Auto',
        'Public transportation': 'Transit',
        'Walked': 'Active',
        'Bicycle': 'Active',
        'Other': 'Other'
    }
    
    ctpp['mode_group'] = ctpp['mode_category'].map(mode_mapping)
    
    # Join geography
    ctpp = ctpp.merge(counties, on='county_fips')
    
    # Aggregate
    summary = ctpp.groupby(['county_name', 'mode_group']).agg({
        'workers': 'sum'
    }).reset_index()
    
    # Calculate shares
    summary['share'] = summary.groupby('county_name')['workers'].transform(
        lambda x: x / x.sum()
    )
    
    # Add dataset identifier
    summary['dataset'] = 'CTPP 2016-2020'
    
    # Save
    summary.to_csv(output_file, index=False)
    print(f"Saved {len(summary)} rows to {output_file}")

# Run preprocessing
process_ctpp_mode_choice(
    ctpp_file='ctpp_a302200_raw.csv',
    county_mapping_file='taz_to_county.csv',
    output_file='work_mode_by_county_ctpp.csv'
)
```

### Validation

After preprocessing, verify format matches model summaries:

```python
# Load model summary
model = pd.read_csv('outputs/dashboard/work_mode_by_county.csv')

# Load CTPP summary
ctpp = pd.read_csv('work_mode_by_county_ctpp.csv')

# Check columns match
assert set(model.columns) == set(ctpp.columns), "Column mismatch!"

# Check categories match
assert set(model['mode_group'].unique()).issubset(
    set(ctpp['mode_group'].unique())
), "Mode categories don't align!"

print("✓ CTPP format matches model summary")
```

### Integration

Once CTPP is preprocessed, it will automatically appear in dashboard comparisons:

```python
# Combined file will have both datasets
combined = pd.read_csv('outputs/dashboard/work_mode_by_county.csv')

print(combined['dataset'].unique())
# Output: ['2023_base_year', 'CTPP 2016-2020']
```

---

## Summary of Tasks

| Task | Status | Priority | Effort | Dependencies |
|------|--------|----------|--------|--------------|
| 1. Update data model docs | 🔄 In Progress | High | Medium | Postprocessing pipeline updates |
| 2. Format 2023 survey data | ⏳ Not Started | High | High | Task 1 (data model changes) |
| 3. Fix broken summaries | ⏳ Not Started | High | Low | None |
| 4. Add new summaries | ⏳ Not Started | Medium | Medium | Task 1, Task 3 |
| 5. Reformat CTPP data | ⏳ Not Started | Medium | Medium | Geography crosswalk |

### Recommended Sequence

1. **Complete Task 1 first** - Finalize data model with all postprocessed fields
2. **Then Task 2** - Format survey data to match finalized data model
3. **Then Task 3** - Fix broken summaries using updated data
4. **Parallel: Tasks 4 & 5** - Add new summaries while preprocessing CTPP

### Success Criteria

✅ All 4 CTRAMP data files documented with complete schemas  
✅ 2023 survey data loads without errors  
✅ All 25 existing summaries generate successfully  
✅ 10+ new summaries added from calibration spreadsheet  
✅ CTPP data integrated for model-vs-observed comparison  
✅ Dashboard displays all comparisons without errors  

---

## Related Documentation

- **[Data Model Reference](data-model.md)** - Current CTRAMP schema (needs updates per Task 1)
- **[Custom Summaries Guide](custom-summaries.md)** - How to configure new summaries (Task 4)
- **[External Data Integration](external-data.md)** - CTPP preprocessing guidance (Task 5)
- **[Generate Summaries](generate-summaries.md)** - Running validation after changes
- **[Validation System Overview](validation-system.md)** - Return to main documentation

---

## Questions or Issues?

If you encounter issues with any of these tasks:

1. **Check error messages** in console output - most issues are column name mismatches
2. **Review data model** - ensure new fields are documented
3. **Test incrementally** - process one summary at a time, not all 25 at once
4. **Verify geography alignment** - TAZ systems must match exactly
5. **Document as you go** - update relevant .md files when making changes
