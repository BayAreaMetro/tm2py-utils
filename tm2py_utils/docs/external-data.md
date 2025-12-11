# Integrate External Data Sources

Guide to integrating observed data from ACS, CTPP, and other external sources for model validation comparisons.

## Overview

The validation system allows you to **compare model outputs with observed data** from external sources. This enables validation against real-world benchmarks like census data, employment surveys, and journey-to-work statistics.

**Supported External Sources:**
- **ACS** (American Community Survey) - Household/person demographics
- **CTPP** (Census Transportation Planning Products) - Journey-to-work patterns
- **External surveys** - Employment surveys, regional studies, etc.
- **Other tabulated data** - Any pre-aggregated statistics

**Important:** This is for **pre-aggregated summary data from external sources**, not household travel survey microdata. Household travel surveys should be formatted to match the [CTRAMP data model](data-model.md) and processed as regular model inputs.

**How it works:**
1. Preprocess external data to match model summary format
2. Configure file paths and column mappings
3. System automatically merges with model summaries
4. Dashboard displays side-by-side comparisons

---

## System Architecture

```
┌──────────────────────────────────────────────┐
│ EXTERNAL DATA (ACS/CTPP/Surveys)             │
│ - Raw census tables                          │
│ - Pre-aggregated summaries                   │
│ - Different column names/formats             │
└──────────────────────────────────────────────┘
                    ↓
        YOU MUST PREPROCESS TO MATCH
        MODEL SUMMARY FORMAT
                    ↓
┌──────────────────────────────────────────────┐
│ PREPROCESSED EXTERNAL DATA                   │
│ - Same columns as model summaries            │
│ - Same categories (1,2,3,4+ households)      │
│ - Same geography (counties match model)      │
│ - CSV format with dataset column             │
└──────────────────────────────────────────────┘
                    ↓
        observed_summaries CONFIG
        (file paths + column mapping)
                    ↓
┌──────────────────────────────────────────────┐
│ SYSTEM MERGES                                │
│ Model Summary + External Data → Combined CSV │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ DASHBOARD VISUALIZATION                      │
│ Model vs. Observed comparisons               │
└──────────────────────────────────────────────┘
```

**Key principle:** You preprocess external data to match model format. The system does NOT automatically convert ACS/CTPP raw data.

---

## Quick Start

### Step 1: Preprocess External Data

Create a CSV matching your model summary format.

**Example:** ACS auto ownership by household size (regional)

**Required columns** (must match model summary):
- `num_persons` (or aggregated field name)
- `num_vehicles`
- `households` (count)
- `share` (percentage)

**Example file:** `acs_auto_ownership_by_household_size_regional.csv`

```csv
num_persons,num_vehicles,households,share
1,0,120000,0.30
1,1,180000,0.45
1,2,100000,0.25
2,0,80000,0.15
2,1,200000,0.38
2,2,250000,0.47
3,0,50000,0.10
3,1,150000,0.30
3,2,300000,0.60
4,0,40000,0.08
4,1,120000,0.24
4,2,340000,0.68
```

### Step 2: Configure in validation_config.yaml

Add to `observed_summaries` section:

```yaml
observed_summaries:
  - name: "acs_2023"
    display_name: "ACS 2023"
    summaries:
      auto_ownership_by_household_size_acs:
        file: "C:\\path\\to\\acs_auto_ownership_by_household_size_regional.csv"
        columns:
          num_persons_agg: "num_persons"  # Map 'num_persons' to model's 'num_persons_agg'
          num_vehicles: "num_vehicles"
          households: "households"
          share: "share"
```

### Step 3: Create Matching Model Summary

Ensure you have a model summary with the **same name and columns**:

```yaml
summaries:
  - name: "auto_ownership_by_household_size_acs"
    data_source: "households"
    group_by: ["num_persons_agg", "num_vehicles"]
    share_within: "num_persons_agg"
```

### Step 4: Regenerate Summaries

```powershell
conda activate tm2py-utils
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

**Output:** Combined CSV with model + ACS data:

```csv
num_persons_agg,num_vehicles,households,share,dataset
1,0,150000,0.28,2023 TM2.2 v05
1,1,200000,0.37,2023 TM2.2 v05
1,2,190000,0.35,2023 TM2.2 v05
1,0,120000,0.30,ACS 2023
1,1,180000,0.45,ACS 2023
1,2,100000,0.25,ACS 2023
...
```

---

## Configuration Details

### observed_summaries Structure

```yaml
observed_summaries:
  - name: "source_identifier"           # Internal name (no spaces)
    display_name: "Display Name"        # Name shown in dashboards
    summaries:
      summary_name_1:                   # Must match a model summary name
        file: "path/to/file.csv"
        columns:                        # Column mapping (model_col: file_col)
          model_column_1: "file_column_1"
          model_column_2: "file_column_2"
      summary_name_2:
        file: "path/to/another_file.csv"
        columns:
          ...
```

**Fields:**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `name` | ✅ | Internal identifier | `"acs_2023"` |
| `display_name` | ✅ | Dashboard label | `"ACS 2023"` |
| `summaries` | ✅ | Dictionary of summaries to load | See below |

**Summary configuration:**

| Field | Required | Description |
|-------|----------|-------------|
| `file` | ✅ | Absolute path to CSV file |
| `columns` | ⚠️ | Column name mapping (optional if names match exactly) |

### Column Mapping

Maps external data column names to model column names.

**Syntax:**

```yaml
columns:
  model_column_name: "external_file_column_name"
```

**Example 1:** Column names differ

```yaml
columns:
  num_persons_agg: "hh_size"      # Model uses 'num_persons_agg', file has 'hh_size'
  num_vehicles: "vehicles"        # Model uses 'num_vehicles', file has 'vehicles'
  households: "count"             # Model uses 'households', file has 'count'
  share: "percentage"             # Model uses 'share', file has 'percentage'
```

**Example 2:** Column names match (no mapping needed)

```yaml
columns:
  num_persons_agg: "num_persons_agg"
  num_vehicles: "num_vehicles"
  households: "households"
  share: "share"
```

Or omit `columns` entirely if all names match.

---

## Data Format Requirements

### Required Columns

External data files must contain:

1. **Dimension columns** - Same as model summary's `group_by`
2. **Metric columns** - Usually `households`, `persons`, `tours`, or `trips`
3. **Share column** - Percentage (0.0 to 1.0 or 0 to 100)

**Do NOT include** `dataset` column - the system adds this automatically.

### Data Types

| Column Type | Format | Example |
|------------|--------|---------|
| Categorical dimensions | String or integer | `"Alameda"`, `1` |
| Count metrics | Integer or float | `150000`, `150000.5` |
| Shares | Float (0-1) | `0.25` (25%) |

### Category Alignment

**Critical:** External data categories must match model aggregations.

**Example:** Household size

**Model uses:** `num_persons_agg` with values `1, 2, 3, 4` (4 = "4+")

**ACS raw data has:** `1, 2, 3, 4, 5, 6, 7+`

**You must aggregate ACS:** `1, 2, 3, 4+` (combine 4, 5, 6, 7+ → 4)

**How to aggregate:**
- See model's `aggregation_specs` in `validation_config.yaml`
- Match those category definitions in your preprocessing
- Use same labels (strings must match exactly)

### Geography Alignment

**County names must match exactly:**

Model geography:
```
Alameda
Contra Costa
Marin
Napa
San Francisco
San Mateo
Santa Clara
Solano
Sonoma
```

External data must use identical spelling and capitalization.

---

## Preprocessing Examples

### Example 1: ACS Household Size by Vehicles

**Source:** ACS Table B08201 (Household Size by Vehicles Available)

**Raw ACS format:**

```csv
geography,grouping,universe,share
Bay Area,"Total:",2490000,1.0
Bay Area,"Total: 1-person household:",400000,0.161
Bay Area,"Total: 1-person household: No vehicle available",120000,0.048
Bay Area,"Total: 1-person household: 1 vehicle available",200000,0.080
Bay Area,"Total: 1-person household: 2 vehicles available",80000,0.032
...
```

**Preprocessing script:** `convert_acs_data.py`

```python
import pandas as pd

# Load raw ACS data
df = pd.read_csv('acs_raw.csv')

# Parse grouping labels
def parse_label(label):
    if '1-person household:' in label:
        persons = '1'
    elif '2-person household:' in label:
        persons = '2'
    elif '3-person household:' in label:
        persons = '3'
    elif '4-or-more-person household:' in label:
        persons = '4+'  # Aggregated
    else:
        return None, None
    
    if 'No vehicle' in label:
        vehicles = 0
    elif '1 vehicle' in label:
        vehicles = 1
    elif '2 vehicles' in label:
        vehicles = 2
    elif '3 vehicles' in label:
        vehicles = 3
    elif '4 or more' in label:
        vehicles = 4
    else:
        return None, None
    
    return persons, vehicles

# Extract detail rows
records = []
for _, row in df.iterrows():
    persons, vehicles = parse_label(row['grouping'])
    if persons and vehicles is not None:
        records.append({
            'num_persons': persons,
            'num_vehicles': vehicles,
            'households': row['universe'],
            'share': row['share']
        })

result = pd.DataFrame(records)

# Recalculate shares within household size
result['share'] = result.groupby('num_persons')['households'].transform(
    lambda x: x / x.sum()
)

result.to_csv('acs_auto_ownership_by_household_size_regional.csv', index=False)
```

**Output:**

```csv
num_persons,num_vehicles,households,share
1,0,120000,0.30
1,1,200000,0.50
1,2,80000,0.20
2,0,80000,0.15
...
```

### Example 2: CTPP Journey to Work

**Source:** CTPP Table A302 (Place of Work by Residence)

**Goal:** Compare commute patterns

**Preprocessing:**

```python
import pandas as pd

# Load CTPP data
ctpp = pd.read_csv('ctpp_work_flows.csv')

# Map TAZs to counties
taz_to_county = pd.read_csv('taz_county_lookup.csv')

# Aggregate to county-to-county flows
flows = ctpp.merge(
    taz_to_county.rename(columns={'county': 'home_county'}),
    left_on='residence_taz',
    right_on='taz'
).merge(
    taz_to_county.rename(columns={'county': 'work_county'}),
    left_on='workplace_taz',
    right_on='taz'
)

result = flows.groupby(['home_county', 'work_county'])['workers'].sum().reset_index()
result['share'] = result.groupby('home_county')['workers'].transform(lambda x: x / x.sum())

result.to_csv('ctpp_work_location_by_home_county.csv', index=False)
```

### Example 3: External Employment Survey

**Source:** Regional employment survey by industry

**Goal:** Compare employment distribution

**Format to match model:**

```python
import pandas as pd

survey = pd.read_csv('employment_survey.csv')

# Map survey categories to model person_types
category_map = {
    'Full-time': 1,
    'Part-time': 2,
    'Student': 3,
    # etc.
}

survey['person_type'] = survey['employment_category'].map(category_map)

result = survey.groupby('person_type')['persons'].sum().reset_index()
result['share'] = result['persons'] / result['persons'].sum()

result.to_csv('survey_employment_distribution.csv', index=False)
```

---

## Complete Configuration Example

### Scenario: Compare Model to ACS 2023

**Model summaries to validate:**
1. Auto ownership by household size (regional)
2. Auto ownership by household size (county-level)

**External data:**
- ACS 2023 data, preprocessed to match model format

**Configuration:**

```yaml
# validation_config.yaml

# Model summaries (generate from model data)
summaries:
  - name: "auto_ownership_by_household_size_acs"
    description: "Vehicle ownership by household size (ACS categories)"
    data_source: "households"
    group_by: ["num_persons_agg", "num_vehicles"]
    weight_field: "sample_rate"
    count_name: "households"
    share_within: "num_persons_agg"
  
  - name: "auto_ownership_by_household_size_county"
    description: "Vehicle ownership by household size and county"
    data_source: "households"
    group_by: ["county", "num_persons_agg", "num_vehicles"]
    weight_field: "sample_rate"
    count_name: "households"
    share_within: ["county", "num_persons_agg"]

# External data (load from preprocessed files)
observed_summaries:
  - name: "acs_2023"
    display_name: "ACS 2023"
    summaries:
      # Regional comparison
      auto_ownership_by_household_size_acs:
        file: "C:\\data\\acs\\acs_auto_ownership_by_household_size_regional.csv"
        columns:
          num_persons_agg: "num_persons"
          num_vehicles: "num_vehicles"
          households: "households"
          share: "share"
      
      # County-level comparison
      auto_ownership_by_household_size_county:
        file: "C:\\data\\acs\\acs_auto_ownership_by_household_size_county.csv"
        columns:
          county: "county"
          num_persons_agg: "num_persons"
          num_vehicles: "num_vehicles"
          households: "households"
          share: "share"

# Aggregation spec (model and ACS must use same categories)
aggregation_specs:
  num_persons_agg:
    apply_to: ["num_persons"]
    mapping:
      1: 1
      2: 2
      3: 3
      4: 4   # 4+ aggregation
      5: 4
      6: 4
      7: 4
      8: 4
      9: 4
      10: 4
```

---

## Execution and Output

### Run Summary Generation

```powershell
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

**Log output:**

```
INFO - Loading data from 2023_version_05: A:\2023-tm22-dev-version-05\ctramp_output
INFO -   ✓ Loaded households: 2,490,000 records
...
INFO - Loading pre-aggregated summaries from acs_2023: ACS 2023
INFO -   ✓ Loaded auto_ownership_by_household_size_acs: 20 rows from acs_auto_ownership_by_household_size_regional.csv
INFO -   ✓ Loaded auto_ownership_by_household_size_county: 180 rows from acs_auto_ownership_by_household_size_county.csv
...
INFO - Combining multi-run summaries...
INFO -   ✓ Saved auto_ownership_by_household_size_acs.csv: 60 rows (3 datasets)
INFO -   ✓ Saved auto_ownership_by_household_size_county.csv: 539 rows (3 datasets)
```

### Output File Structure

**Combined file:** `auto_ownership_by_household_size_acs.csv`

```csv
num_persons_agg,num_vehicles,households,share,dataset
1,0,150000,0.28,2023 TM2.2 v05
1,1,200000,0.37,2023 TM2.2 v05
1,2,190000,0.35,2023 TM2.2 v05
1,0,130000,0.26,2015 TM2.2 Sprint 04
1,1,210000,0.42,2015 TM2.2 Sprint 04
1,2,160000,0.32,2015 TM2.2 Sprint 04
1,0,120000,0.30,ACS 2023
1,1,180000,0.45,ACS 2023
1,2,100000,0.25,ACS 2023
2,0,80000,0.15,2023 TM2.2 v05
2,1,200000,0.38,2023 TM2.2 v05
...
```

**Dataset column values:**
- `2023 TM2.2 v05` - From model run
- `2015 TM2.2 Sprint 04` - From older model run
- `ACS 2023` - From external data (`display_name` in config)

---

## Troubleshooting

### External Data Not Appearing

```
WARNING - Summary file not found: C:\...\acs_data.csv
```

**Solutions:**
1. Check file path is absolute (not relative)
2. Verify file exists at specified location
3. Check for typos in path

### Column Not Found

```
KeyError: 'num_persons_agg'
```

**Cause:** Column mapping incorrect

**Solution:** Verify column names in external file match `columns` mapping

### Mismatched Categories

**Dashboard shows:** Model has 4+ households, ACS shows 4, 5, 6, 7+

**Cause:** External data not aggregated to match model

**Solution:** Preprocess external data to combine 4, 5, 6, 7+ → "4+"

### Wrong Summary Name

```
WARNING - No model summary found matching 'wrong_name'
```

**Cause:** `observed_summaries` key doesn't match any model summary name

**Solution:** Ensure `summaries:` keys match `summaries[].name` in config exactly

### Shares Don't Match

**Example:** ACS share = 0.30, but model share calculated differently

**Cause:** Different `share_within` grouping

**Model:**
```yaml
share_within: ["county", "num_persons_agg"]  # Share within county × household size
```

**External data:** Share might be regional (not within groups)

**Solution:** Recalculate shares in preprocessing to match model's grouping

---

## Best Practices

1. **Match aggregations first** - Review model's `aggregation_specs` before preprocessing
2. **Use absolute paths** - Avoid relative paths in `file` specifications
3. **Standardize geography** - County names must match exactly (case-sensitive)
4. **Document preprocessing** - Keep scripts that generate external data files
5. **Version control** - Track which ACS/CTPP year/version you're using
6. **Test with one summary** - Validate workflow before adding multiple summaries
7. **Check shares add to 1.0** - Within appropriate grouping levels

---

## Data Source Guidelines

### ACS (American Community Survey)

**Recommended tables:**
- B08201 - Household Size by Vehicles
- B08134 - Means of Transportation to Work
- B08303 - Travel Time to Work
- B19001 - Household Income

**Aggregation notes:**
- Household size: Use 1, 2, 3, 4+ categories
- Vehicles: 0, 1, 2, 3, 4+ (ACS has "3 or more", model might have separate 3 and 4+)

### CTPP (Census Transportation Planning Products)

**Recommended tables:**
- A302 - Place of Work by Residence
- A201 - Journey to Work Flows
- A103 - Travel Time to Work

**Geography notes:**
- CTPP uses TAZs → aggregate to counties for comparison
- Maintain lookup tables for TAZ-to-county mapping

### Employment Surveys

**Considerations:**
- Map employment categories to model's `person_type` codes
- Ensure sample weights/expansion factors applied
- Match reference year to model year

---

## Next Steps

- **[Generate Summaries](generate-summaries.md)** - Run the full summary generation
- **[Deploy Dashboard](deploy-dashboard.md)** - Visualize model vs. observed comparisons
- **[Custom Summaries](custom-summaries.md)** - Create new summary definitions
- **[Data Model Reference](data-model.md)** - Understand model data format
