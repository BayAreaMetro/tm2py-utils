# Preprocessing Requirements for Enhanced Summaries

This document tracks preprocessing steps that need to be implemented before certain summaries can be generated.

## Overview

The current `summarize_model_run.py` tool works with **raw CTRAMP output files only**. Several enhanced summaries from the old `core_summaries.py` system require additional preprocessing or data joins that are not yet implemented.

---

## Missing Columns That Require Preprocessing

### 1. Geography Columns (district, county)

**Required for:**
- `time_of_day_tours` (originally used district/county grouping)
- `auto_ownership_detailed` (originally grouped by district/county)
- Journey to work summaries (home_county, work_county)

**Preprocessing needed:**
- Join households/persons/tours/trips with `geography_lookup` table
- Map `home_mgra` → `county_id`, `county_name`, `district_id`, `district_name`
- For journey to work: map both home and work locations

**Source:**
- Geography lookup file: `tm2py_utils/inputs/maz_taz/mazs_tazs_county_tract_PUMA_2.5.csv`
- Columns defined in `ctramp_data_model.yaml` under `geography_lookup`

**Status:** NOT IMPLEMENTED
- Current workaround: Removed geography dimensions from new summaries
- Future: Add preprocessing step to join geography before summarization

---

### 2. Auto Sufficiency

**Required for:**
- `trip_distance_detailed` (originally grouped by auto sufficiency)
- Trip distance summaries by auto ownership adequacy

**What it is:**
- Comparison of household autos vs. workers
- Categories: "0 autos", "autos < workers", "autos >= workers"

**Preprocessing needed:**
```python
def calculate_auto_sufficiency(households):
    conditions = [
        (households['autos'] == 0),
        (households['autos'] < households['workers']),
        (households['autos'] >= households['workers'])
    ]
    labels = ['0 autos', 'autos < workers', 'autos >= workers']
    households['auto_sufficiency'] = np.select(conditions, labels, default='Unknown')
    return households
```

**Status:** NOT IMPLEMENTED
- Current workaround: Removed auto_sufficiency dimension
- Future: Add to household preprocessing step

---

### 3. VMT (Vehicle Miles Traveled)

**Required for:**
- `vmt_summary` - VMT by geography and person type

**What it is:**
- Individual VMT (from individual tours)
- Joint VMT (from joint tours) 
- Total VMT per person
- Person trips count
- Vehicle trips count (accounting for occupancy)

**Preprocessing needed:**
- Aggregate tour distances to person level
- Separate individual vs. joint tour VMT
- Calculate vehicle trips (tours/trips weighted by occupancy)

**Source files:**
- `indivTourData_{iteration}.csv`
- `jointTourData_{iteration}.csv` (if exists)
- `indivTripData_{iteration}.csv`
- `jointTripData_{iteration}.csv` (if exists)

**Status:** NOT IMPLEMENTED
- Current workaround: Removed vmt_summary entirely
- Future: Add VMT calculation module
- Note: May be better as separate analysis tool rather than validation summary

---

### 4. Trip Travel Time

**Required for:**
- `trip_travel_time` - Average trip time by income/mode/purpose

**What it is:**
- Trip-level travel time in minutes
- May come from skims or could be calculated from departure/arrival times

**Preprocessing needed:**
- Check if `trip_time` exists in `indivTripData_{iteration}.csv`
- If not, calculate from `depart_period` and `arrival_period`
- Or join with skim matrices

**Status:** NOT IMPLEMENTED
- Current workaround: Removed trip_travel_time summary
- Future: Investigate if trip_time is in newer CTRAMP versions
- Alternative: Calculate from time periods or add skim lookup

---

### 5. Kids Without Drivers License

**Required for:**
- `auto_ownership_detailed` (originally used kids_no_drivers)

**What it is:**
- Count of household members under driving age (typically < 16)
- Used to understand auto ownership in context of household composition

**Preprocessing needed:**
```python
def calculate_kids_no_drivers(persons, min_driving_age=16):
    kids = persons[persons['age'] < min_driving_age].groupby('household_id').size()
    households['kids_no_drivers'] = households['household_id'].map(kids).fillna(0)
    return households
```

**Status:** NOT IMPLEMENTED
- Current workaround: Removed kids_no_drivers dimension
- Future: Add to household preprocessing

---

### 6. Income at Person Level

**Required for:**
- `activity_pattern_detailed` (originally grouped by person type AND income)
- Journey to work summaries (mean income by flow)

**What it is:**
- Income is stored at household level
- Need to join to person/tour/trip records for person-level summaries

**Preprocessing needed:**
- Join household income to persons table on `household_id`
- Propagate to tours and trips as needed

**Status:** PARTIALLY IMPLEMENTED
- Journey to work uses income from `wsLocResults.csv` (already has it)
- Other summaries: Join not implemented
- Current workaround: Removed income dimension from activity_pattern_detailed

---

### 7. Time Period for Trips

**Required for:**
- `trip_distance_by_time_purpose` - Trip distance by time of day

**What it is:**
- Which 30-minute time period the trip occurred in
- May be stored as `depart_period` or need to be calculated

**Preprocessing needed:**
- Check if `time_period` or `depart_period` exists in trip files
- Standardize to match tour time period codes (1-40 or 1-48)

**Status:** NEEDS VERIFICATION
- Summary assumes `time_period` column exists
- Need to check actual CTRAMP trip file schema
- May already exist, just with different column name

---

### 8. Workplace/School Location File

**Required for:**
- `journey_to_work`
- `journey_to_work_employment`

**What it is:**
- Separate output file: `wsLocResults.csv`
- Contains work/school location choices for each person
- Not always generated in all model runs

**Status:** OPTIONAL FILE
- File pattern defined in YAML: `wsLocResults.csv`
- Current behavior: Skips these summaries if file not found
- No preprocessing needed, just need file to exist

---

## Recommended Implementation Approach

### Phase 1: Add Basic Preprocessing Module (HIGH PRIORITY)

Create `preprocess_ctramp_data.py` with functions:

1. **Geography joins**
   ```python
   def add_geography(data, geography_lookup):
       """Join county/district to households, persons, tours, trips"""
   ```

2. **Auto sufficiency calculation**
   ```python
   def calculate_auto_sufficiency(households):
       """Calculate auto ownership adequacy"""
   ```

3. **Kids without drivers**
   ```python
   def calculate_kids_no_drivers(persons, households):
       """Count kids under driving age per household"""
   ```

4. **Income propagation**
   ```python
   def add_household_attributes_to_persons(persons, households):
       """Join income and other HH attributes to persons"""
   ```

### Phase 2: Add Advanced Calculations (MEDIUM PRIORITY)

5. **VMT calculation module**
   - Separate script or module
   - Aggregate individual tour distances
   - Aggregate joint tour distances
   - Calculate vehicle trips
   - May be better as standalone analysis tool

### Phase 3: Investigate Missing Fields (LOW PRIORITY)

6. **Trip time verification**
   - Check if newer CTRAMP versions output trip_time
   - Document how to calculate from time periods
   - Consider skim matrix lookup

---

## Integration Plan

### Option A: Preprocessing Module (RECOMMENDED)

Add preprocessing step to `summarize_model_run.py`:

```python
def main():
    # ... existing code ...
    
    # STEP 2.5: Preprocess data (NEW)
    data = preprocess_data(data, config)
    
    # Continue with existing steps...
```

**Pros:**
- Single tool does everything
- User-friendly (one command)
- Preprocessing logic reusable

**Cons:**
- Tool becomes more complex
- Longer runtime
- More dependencies

### Option B: Separate Preprocessing Tool

Create `preprocess_model_run.py`:
- User runs preprocessing first
- Outputs enriched CSV files
- `summarize_model_run.py` reads enriched files

**Pros:**
- Keeps summarization tool simple
- Can skip preprocessing if not needed
- Easy to debug each step

**Cons:**
- Two-step process for users
- Need to manage intermediate files
- More complex workflow

### Option C: Optional Preprocessing Flag

Add `--preprocess` flag to `summarize_model_run.py`:

```bash
# Without preprocessing (current behavior)
python summarize_model_run.py <dir>

# With preprocessing (enables advanced summaries)
python summarize_model_run.py <dir> --preprocess
```

**Pros:**
- Flexible for users
- Maintains simplicity for basic use
- Clear when preprocessing happens

**Cons:**
- Still makes main tool more complex
- Need to handle both modes

---

## Current Workarounds

Until preprocessing is implemented, enhanced summaries have been simplified:

| Original Summary | Removed Dimension | Current Workaround |
|-----------------|-------------------|-------------------|
| `activity_pattern_detailed` | income_category | Group by person_type/CDAP/IMF/INMF only |
| `auto_ownership_detailed` | district, county, kids_no_drivers | Group by autos/size/workers only |
| `trip_distance_detailed` | auto_sufficiency, income, time_period | Removed entirely, replaced with simpler versions |
| `trip_travel_time` | All (no trip_time field) | Removed entirely |
| `time_of_day_tours` | district, county | Group by purpose/mode/time only |
| `vmt_summary` | All (no VMT calculated) | Removed entirely |

New simplified summaries added:
- `trip_distance_by_mode_purpose` - Distance by mode and purpose
- `trip_distance_by_time_purpose` - Distance by time and purpose (if time_period exists)
- `journey_to_work` - Simplified to just home_mgra and work_location
- `journey_to_work_employment` - By employment category and work segment

---

## Summary Statistics

**Total summaries defined:** 30
- Original basic summaries: 21 ✅ Working
- Enhanced summaries (simplified): 9
  - Working if data exists: 7 ✅
  - Need preprocessing: 2 ⚠️ (removed for now)

**Preprocessing needed for full functionality:**
- Geography joins: 🔴 Required for 5+ summaries
- Auto sufficiency: 🔴 Required for 1 summary
- Kids calculation: 🟡 Nice to have
- Income joins: 🟡 Nice to have  
- VMT calculation: 🟡 Separate tool recommended
- Trip time: 🟡 Investigate if available

**Recommendation:** Implement Phase 1 (geography joins + auto sufficiency) to unlock most value from enhanced summaries.
