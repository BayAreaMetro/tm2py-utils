# Create Custom Summaries

Guide to defining new validation summaries using YAML configuration.

## Overview

The validation system is **fully config-driven** - you can create new summaries without writing Python code. All summaries are defined in `validation_config.yaml` under the `summaries` section.

**What you can configure:**
- Which data table to use (households, persons, tours, trips)
- How to group data (dimensions)
- Which metrics to calculate (counts, shares, percentages)
- Filters to apply
- How to bin continuous variables
- How to aggregate categories

**No coding required** - just edit YAML and regenerate.

---

## Basic Summary Structure

### Minimal Example

```yaml
summaries:
  - name: "auto_ownership_regional"
    data_source: "households"
    group_by: "num_vehicles"
    weight_field: "sample_rate"
    count_name: "households"
```

**Output:**

```csv
num_vehicles,households,share,dataset
0,150000,0.25,2023 TM2.2 v05
1,200000,0.33,2023 TM2.2 v05
2,180000,0.30,2023 TM2.2 v05
```

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Unique identifier (becomes filename) | `"auto_ownership_regional"` |
| `data_source` | string | Which table to query | `"households"`, `"persons"`, `"individual_tours"`, `"individual_trips"` |
| `group_by` | string or list | Columns to group by | `"num_vehicles"` or `["county", "num_vehicles"]` |

### Optional Fields

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `weight_field` | string | Column containing expansion weights | `"sample_rate"` | `"sample_rate"` |
| `count_name` | string | Name for count metric | Based on data_source | `"households"`, `"tours"` |
| `share_within` | string or list | Calculate shares within groups | `null` (regional) | `"income_category"` |
| `description` | string | Human-readable description | `""` | `"Vehicle ownership by income"` |
| `filter` | string | Filter expression (pandas query syntax) | `null` (no filter) | `"tour_purpose == 'Work'"` |
| `calculate_share` | boolean | Whether to calculate share column | `true` | `false` |

---

## Data Sources

The `data_source` field determines which table is queried:

| Data Source | Description | Available Columns |
|------------|-------------|-------------------|
| `households` | Household demographics | `num_vehicles`, `num_persons`, `num_workers`, `income_category`, `county`, `county_name`, etc. |
| `persons` | Person characteristics | `person_type`, `age`, `gender`, `cdap`, `value_of_time`, etc. |
| `individual_tours` | Tour-level data | `tour_purpose`, `tour_mode`, `start_period`, `end_period`, `tour_distance`, etc. |
| `individual_trips` | Trip-level data | `trip_mode`, `origin_purpose`, `destination_purpose`, `trip_distance`, etc. |
| `workplace_school_location` | Work/school locations | `work_location`, `school_location`, `work_location_distance`, etc. |

See [CTRAMP Data Model](data-model.md) for complete column lists.

**Column naming:**
- After data loading, columns use **standardized internal names**
- `hh_id` → `household_id`
- `size` → `num_persons`
- `autos` → `num_vehicles`

Use the internal names in your `group_by` specifications.

---

## Grouping Dimensions

### Single Dimension

```yaml
- name: "cdap_distribution"
  data_source: "persons"
  group_by: "cdap"
  count_name: "persons"
```

**Output:** One row per CDAP value (M, N, H)

### Multiple Dimensions

```yaml
- name: "auto_ownership_by_income"
  data_source: "households"
  group_by: ["income_category", "num_vehicles"]
  count_name: "households"
```

**Output:** One row per combination (income × vehicles)

```csv
income_category,num_vehicles,households,share,dataset
1,0,50000,0.15,2023 TM2.2 v05
1,1,80000,0.24,2023 TM2.2 v05
1,2,70000,0.21,2023 TM2.2 v05
2,0,40000,0.12,2023 TM2.2 v05
...
```

### Cross-Tabulations

For mode × purpose, destination × origin, etc.:

```yaml
- name: "tour_mode_by_purpose"
  data_source: "individual_tours"
  group_by: ["tour_purpose", "tour_mode"]
  share_within: "tour_purpose"  # Share within each purpose
```

**Output:** Mode distribution for each tour purpose

---

## Share Calculations

### Regional Shares (Default)

```yaml
- name: "auto_ownership_regional"
  data_source: "households"
  group_by: "num_vehicles"
```

**Output:** Share = count / total across all records

```csv
num_vehicles,households,share
0,150000,0.25
1,200000,0.33
2,180000,0.30
3,120000,0.20
```

Share adds to 1.0 (or 100%)

### Shares Within Groups

```yaml
- name: "auto_ownership_by_income"
  data_source: "households"
  group_by: ["income_category", "num_vehicles"]
  share_within: "income_category"
```

**Output:** Share = count / total within each income category

```csv
income_category,num_vehicles,households,share
1,0,50000,0.33    # Share within income=1
1,1,80000,0.53
1,2,20000,0.13
2,0,30000,0.20    # Share within income=2
2,1,90000,0.60
2,2,30000,0.20
```

Within each `income_category`, shares add to 1.0.

### Multiple Grouping Levels

```yaml
- name: "auto_ownership_by_household_size_county"
  data_source: "households"
  group_by: ["county", "num_persons_agg", "num_vehicles"]
  share_within: ["county", "num_persons_agg"]
```

**Output:** Share within each county × household_size combination

```csv
county,num_persons_agg,num_vehicles,households,share
Alameda,1,0,57000,0.28    # Share within Alameda 1-person households
Alameda,1,1,100000,0.50
Alameda,1,2,44000,0.22
Alameda,2,0,40000,0.15    # Share within Alameda 2-person households
...
```

Shares add to 1.0 within each (county, num_persons_agg) group.

### Disable Share Calculation

For raw counts without percentages:

```yaml
- name: "time_of_day_tours"
  data_source: "individual_tours"
  group_by: ["start_period", "end_period"]
  calculate_share: false
```

---

## Filtering Data

Use pandas query syntax to filter records before aggregation.

### Simple Filters

**Filter to work tours only:**

```yaml
- name: "work_tour_modes"
  data_source: "individual_tours"
  filter: "tour_purpose == 'Work'"
  group_by: "tour_mode"
```

**Filter to adults (age 18+):**

```yaml
- name: "adult_cdap"
  data_source: "persons"
  filter: "age >= 18"
  group_by: "cdap"
```

**Filter to specific county:**

```yaml
- name: "sf_auto_ownership"
  data_source: "households"
  filter: "county_name == 'San Francisco'"
  group_by: "num_vehicles"
```

### Complex Filters

**Multiple conditions (AND):**

```yaml
filter: "age >= 18 and age <= 65"
```

**Multiple conditions (OR):**

```yaml
filter: "tour_purpose == 'Work' or tour_purpose == 'School'"
```

**List membership:**

```yaml
filter: "tour_purpose in ['Work', 'School', 'University']"
```

**Numeric ranges:**

```yaml
filter: "tour_distance >= 5 and tour_distance < 20"
```

**String matching:**

```yaml
filter: "county_name.str.contains('San')"
```

### Filter Execution

Filters are applied **before** aggregation:

1. Load data
2. **Apply filter** → Reduce rows
3. Group by dimensions
4. Calculate counts and shares

**Log output:**

```
INFO - ✓ Applied filter: 'tour_purpose == "Work"' (1,500,000 → 450,000 rows)
```

---

## Binning Continuous Variables

Convert continuous variables (distance, time, age, income) into categories.

### Define Bins Globally

In `validation_config.yaml`:

```yaml
binning_specs:
  tour_distance:
    bins: [0, 5, 10, 20, 50, 1000]
    labels: ['0-5', '5-10', '10-20', '20-50', '50+']
    
  worker_age:
    bins: [0, 25, 35, 45, 55, 65, 120]
    labels: ['<25', '25-34', '35-44', '45-54', '55-64', '65+']
```

### Use Binned Columns

The system automatically creates `{column}_bin` columns:

```yaml
- name: "tour_distance_distribution"
  data_source: "individual_tours"
  group_by: "tour_distance_bin"  # Uses binning_specs.tour_distance
```

**Output:**

```csv
tour_distance_bin,tours,share,dataset
0-5,250000,0.40,2023 TM2.2 v05
5-10,180000,0.29,2023 TM2.2 v05
10-20,120000,0.19,2023 TM2.2 v05
20-50,60000,0.10,2023 TM2.2 v05
50+,15000,0.02,2023 TM2.2 v05
```

### Binning Configuration

| Field | Description | Example |
|-------|-------------|---------|
| `bins` | Bin edges (inclusive lower, exclusive upper) | `[0, 5, 10, 20, 50, 1000]` |
| `labels` | Category labels (one less than bins) | `['0-5', '5-10', '10-20', '20-50', '50+']` |

**Bin behavior:**
- `bins: [0, 5, 10]` creates: `[0, 5)` and `[5, 10)`
- First bin includes lower edge: `[0, 5)` → 0 ≤ x < 5
- Last bin includes upper edge: `[50, 1000]` → 50 ≤ x ≤ 1000

### Pre-Configured Bins

The system includes these bin specifications:

| Variable | Bins | Labels |
|----------|------|--------|
| `tour_distance` | 0, 5, 10, 20, 50, 1000 | 0-5, 5-10, 10-20, 20-50, 50+ |
| `trip_distance` | 0, 1, 3, 5, 10, 20, 1000 | 0-1, 1-3, 3-5, 5-10, 10-20, 20+ |
| `tour_duration` | 0, 30, 60, 120, 240, 10000 | 0-30, 30-60, 60-120, 120-240, 240+ |
| `trip_duration` | 0, 5, 10, 15, 30, 60, 10000 | 0-5, 5-10, 10-15, 15-30, 30-60, 60+ |
| `worker_age` | 0, 25, 35, 45, 55, 65, 120 | <25, 25-34, 35-44, 45-54, 55-64, 65+ |
| `income_category` | 0, 30000, 60000, 100000, 150000, 1000000000 | <30K, 30-60K, 60-100K, 100-150K, 150K+ |

---

## Aggregating Categories

Combine detailed categories into broader groups (e.g., 4+ person households, Auto/Transit/Active modes).

### Define Aggregations Globally

In `validation_config.yaml`:

```yaml
aggregation_specs:
  # Household size: 1, 2, 3, 4+ (match ACS categories)
  num_persons_agg:
    apply_to: ["num_persons"]
    mapping:
      1: 1
      2: 2
      3: 3
      4: 4
      5: 4
      6: 4
      7: 4
      8: 4
      9: 4
      10: 4
```

### Use Aggregated Columns

The system automatically creates `{column}_agg` columns:

```yaml
- name: "auto_ownership_by_household_size_acs"
  data_source: "households"
  group_by: ["num_persons_agg", "num_vehicles"]  # Uses aggregation_specs.num_persons_agg
  share_within: "num_persons_agg"
```

**Before aggregation** (`num_persons`):
- 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (10 categories)

**After aggregation** (`num_persons_agg`):
- 1, 2, 3, 4 (4 categories, where 4 = "4+")

### Transportation Mode Aggregation

Group 17 detailed modes into broader categories:

```yaml
aggregation_specs:
  transportation_mode:
    apply_to: ["tour_mode", "trip_mode"]
    mapping:
      1: "Auto - SOV"        # SOV_GP
      2: "Auto - SOV"        # SOV_PAY
      3: "Auto - Shared"     # SR2_GP
      4: "Auto - Shared"     # SR2_HOV
      5: "Auto - Shared"     # SR2_PAY
      6: "Auto - Shared"     # SR3_GP
      7: "Auto - Shared"     # SR3_HOV
      8: "Auto - Shared"     # SR3_PAY
      9: "Active"            # WALK
      10: "Active"           # BIKE
      11: "Transit"          # WLK_TRN
      12: "Transit"          # PNR_TRN
      13: "Transit"          # KNRPRV_TRN
      14: "Transit"          # KNRTNC_TRN
      15: "TNC/Taxi"         # TAXI
      16: "TNC/Taxi"         # TNC
      17: "School Bus"       # SCHLBUS
```

**Usage:**

```yaml
- name: "tour_mode_choice_aggregated"
  data_source: "individual_tours"
  group_by: "tour_mode_agg"  # Uses transportation_mode aggregation
```

**Output:** 6 categories instead of 17

### Aggregation vs. Binning

| | Binning | Aggregation |
|---|---------|-------------|
| **Input** | Continuous numeric | Categorical (codes/text) |
| **Process** | Create ranges | Map values to groups |
| **Example** | Distance → bins | 17 modes → 6 groups |
| **Suffix** | `_bin` | `_agg` |

---

## Complete Examples

### Example 1: Simple Distribution

**Goal:** Vehicle ownership distribution

```yaml
- name: "auto_ownership_regional"
  description: "Regional vehicle ownership distribution"
  data_source: "households"
  group_by: "num_vehicles"
  weight_field: "sample_rate"
  count_name: "households"
```

**Output:**

```csv
num_vehicles,households,share,dataset
0,150000,0.25,2023 TM2.2 v05
1,200000,0.33,2023 TM2.2 v05
2,180000,0.30,2023 TM2.2 v05
3,72000,0.12,2023 TM2.2 v05
```

### Example 2: Cross-Tabulation with Shares

**Goal:** Mode choice by tour purpose

```yaml
- name: "tour_mode_by_purpose"
  description: "Tour mode by purpose cross-tabulation"
  data_source: "individual_tours"
  group_by: ["tour_purpose", "tour_mode"]
  weight_field: "sample_rate"
  count_name: "tours"
  share_within: "tour_purpose"
```

**Output:**

```csv
tour_purpose,tour_mode,tours,share,dataset
Work,1,80000,0.40,2023 TM2.2 v05
Work,9,30000,0.15,2023 TM2.2 v05
Work,11,60000,0.30,2023 TM2.2 v05
Shop,1,120000,0.60,2023 TM2.2 v05
Shop,9,80000,0.40,2023 TM2.2 v05
```

Shares add to 1.0 within each `tour_purpose`.

### Example 3: Filtered + Binned

**Goal:** Work tour distance distribution (work tours only)

```yaml
- name: "work_tour_distance"
  description: "Distance distribution for work tours"
  data_source: "individual_tours"
  filter: "tour_purpose == 'Work'"
  group_by: "tour_distance_bin"
  weight_field: "sample_rate"
  count_name: "tours"
```

**Output:** Distance distribution for work tours only (non-work filtered out)

### Example 4: Multi-Level Grouping

**Goal:** Auto ownership by income and household size

```yaml
- name: "auto_ownership_by_income_and_size"
  description: "Vehicle ownership by income and household size"
  data_source: "households"
  group_by: ["income_category", "num_persons", "num_vehicles"]
  weight_field: "sample_rate"
  count_name: "households"
  share_within: ["income_category", "num_persons"]
```

**Output:** Shares add to 1.0 within each (income, household size) combination

### Example 5: Aggregated Categories

**Goal:** Simplified mode choice (Auto/Transit/Active/Other)

```yaml
- name: "tour_mode_choice_aggregated"
  description: "Tour mode choice (aggregated categories)"
  data_source: "individual_tours"
  group_by: "tour_mode_agg"
  weight_field: "sample_rate"
  count_name: "tours"
```

**Output:**

```csv
tour_mode_agg,tours,share,dataset
Auto - SOV,450000,0.45,2023 TM2.2 v05
Auto - Shared,200000,0.20,2023 TM2.2 v05
Transit,250000,0.25,2023 TM2.2 v05
Active,80000,0.08,2023 TM2.2 v05
TNC/Taxi,20000,0.02,2023 TM2.2 v05
```

### Example 6: Geographic Summary

**Goal:** Auto ownership by county

```yaml
- name: "auto_ownership_by_county"
  description: "Vehicle ownership by county"
  data_source: "households"
  group_by: ["county_name", "num_vehicles"]
  weight_field: "sample_rate"
  count_name: "households"
  share_within: "county_name"
```

**Output:** Vehicle distribution for each Bay Area county

---

## Common Patterns

### Pattern 1: Regional Distribution

```yaml
group_by: "variable"
# No share_within → regional shares
```

### Pattern 2: Conditional Distribution

```yaml
group_by: ["condition", "variable"]
share_within: "condition"
# Share of 'variable' within each 'condition'
```

### Pattern 3: Filtered Subset

```yaml
filter: "expression"
group_by: "variable"
# Distribution for filtered records only
```

### Pattern 4: Multi-Dimensional

```yaml
group_by: ["dim1", "dim2", "dim3"]
share_within: ["dim1", "dim2"]
# Share within each (dim1, dim2) combination
```

---

## Troubleshooting

### Empty Output

```
WARNING - Generated my_summary: 0 rows
```

**Causes:**
- Filter removed all records
- Missing column in data
- Column has all null values

**Solutions:**
1. Check filter expression
2. Verify column exists: see [Data Model](data-model.md)
3. Check for typos in column names

### Missing Columns

```
KeyError: 'tour_distance_bin'
```

**Solution:** Add binning spec to `binning_specs` section for `tour_distance`

### Wrong Data Source

```
WARNING - Column 'tour_mode' not found
```

**Cause:** Using `data_source: "households"` but `tour_mode` is in `"individual_tours"`

**Solution:** Use correct data source table

### Shares Don't Add to 1.0

**Cause:** Using wrong `share_within` grouping

**Example:**

```yaml
group_by: ["county", "income", "vehicles"]
share_within: "county"  # Wrong - shares within county, not county×income
```

**Fix:**

```yaml
share_within: ["county", "income"]  # Shares within each county×income combination
```

---

## Best Practices

1. **Use descriptive names** - `auto_ownership_by_income` not `summary_1`
2. **Add descriptions** - Helps future users understand purpose
3. **Start simple** - Test with single dimension before adding complexity
4. **Check shares** - Verify they add to 1.0 within expected groups
5. **Use aggregations** - For comparison with external data (ACS uses 4+ households)
6. **Leverage bins** - Pre-configured bins for common variables
7. **Filter early** - Reduces processing time
8. **Test incrementally** - Add one feature at a time

---

## Validation

Check your summary configuration:

```powershell
python validate_config.py --config validation_config.yaml
```

Checks:
- Required fields present
- Data source valid
- Group-by columns exist
- Filter syntax correct
- Binning specs defined

---

## Next Steps

- **[Generate Summaries](generate-summaries.md)** - Run the summary generation
- **[External Data Integration](external-data.md)** - Add ACS/CTPP comparisons
- **[Data Model Reference](data-model.md)** - See available columns
- **[Deploy Dashboard](deploy-dashboard.md)** - Visualize your summaries
