# Dashboard Generalization Pattern

## Overview
Standardize dashboard creation to support comparing N model runs with consistent chart patterns.

## Data Structure

### Single Run
Each summary includes a `dataset` column:
```csv
num_vehicles,households,share,dataset,geography
0,5234,0.163,2023_version_05,Regional
1,8932,0.278,2023_version_05,Regional
```

### Multiple Runs
Concatenate into single CSV:
```csv
num_vehicles,households,share,dataset,geography
0,5234,0.163,2023_version_05,Regional
1,8932,0.278,2023_version_05,Regional
0,5891,0.171,2024_version_01,Regional
1,9234,0.267,2024_version_01,Regional
```

## Chart Patterns

### 1D Distribution (e.g., auto ownership)

**A. Share Chart**
- X-axis: Primary variable (e.g., `num_vehicles`)
- Y-axis: `share`
- Color/Group: `dataset` (for comparing runs)
- Chart type: Grouped bar or line
- Purpose: Compare distribution shape across runs

**B. Total Chart**
- X-axis: Primary variable (e.g., `num_vehicles`)
- Y-axis: Count variable (e.g., `households`)
- Color/Group: `dataset`
- Chart type: Grouped bar or line
- Purpose: Compare absolute numbers across runs

### 2D Crosstab (e.g., auto ownership × income)

**A. Share Within Groups**
- X-axis: Primary variable (e.g., `num_vehicles`)
- Y-axis: `share`
- Stacking/Facet: Secondary variable (e.g., `income_category_bin`)
- Color/Series: `dataset`
- Chart type: Stacked bar or faceted bar
- Purpose: Compare within-group distributions across runs

**B. Total Counts**
- X-axis: Primary variable (e.g., `num_vehicles`)
- Y-axis: Count variable (e.g., `households`)
- Stacking/Facet: Secondary variable (e.g., `income_category_bin`)
- Color/Series: `dataset`
- Chart type: Grouped or stacked bar
- Purpose: Compare absolute numbers by groups across runs

## Implementation Approach

### Option 1: Combine at Data Generation
```python
# In run_all_validation_summaries.py
# For each summary type, concatenate all runs before writing
for summary_type in ['auto_ownership_regional', 'auto_ownership_by_income', ...]:
    combined_df = pd.concat([
        summaries['2023_v05'][summary_type],
        summaries['2024_v01'][summary_type]
    ])
    writer.write_csv(combined_df, f'{summary_type}.csv')
```

### Option 2: Combine in Dashboard Writer
```python
# In simwrapper_writer.py
def _combine_multi_run_summaries(summaries: Dict[str, pd.DataFrame]):
    # Group by base summary name (removing dataset suffix)
    # Concatenate matching summaries
    # Return combined DataFrames
```

### Option 3: SimWrapper Built-in Comparison
```yaml
# In dashboard YAML
datasets:
  - file: auto_ownership_2023_v05.csv
    label: "2023 Version 05"
  - file: auto_ownership_2024_v01.csv
    label: "2024 Version 01"
charts:
  - type: bar
    x: num_vehicles
    y: share
    compare: true  # SimWrapper feature for side-by-side comparison
```

## Recommendation

**Use Option 1** - Combine at data generation level:
- More explicit control over data structure
- Easier to debug
- Single CSV per summary type (simpler file management)
- `dataset` column provides natural grouping

## Dashboard Structure

### For each summary module (household, worker, tour, trip):

```python
def create_X_dashboard(output_dir, summaries):
    # 1. Combine multi-run summaries
    combined = combine_by_summary_type(summaries)
    
    # 2. For each 1D summary:
    #    - Create share chart (y=share, color=dataset)
    #    - Create total chart (y=count, color=dataset)
    
    # 3. For each 2D summary:
    #    - Create share chart (y=share, stack=secondary, color=dataset)
    #    - Create total chart (y=count, stack=secondary, color=dataset)
```

## Example: Auto Ownership Dashboard

```python
# 1D: Auto ownership distribution
- Chart: Share by vehicle ownership (comparing runs)
  - x: num_vehicles
  - y: share
  - color: dataset
  
- Chart: Total households by vehicle ownership (comparing runs)
  - x: num_vehicles
  - y: households
  - color: dataset

# 2D: Auto ownership × income
- Chart: Share by vehicle ownership within income groups (comparing runs)
  - x: num_vehicles
  - y: share
  - facet: income_category_bin (or stack)
  - color: dataset
  
- Chart: Total by vehicle ownership and income (comparing runs)
  - x: num_vehicles
  - y: households
  - facet: income_category_bin
  - color: dataset
```

## Questions to Resolve

1. **N runs handling**: Where to combine summaries?
   - ✅ Recommended: In run_all_validation_summaries.py before dashboard creation
   
2. **Chart type for multi-run**: Grouped bars vs lines?
   - Lines better for many runs (cleaner)
   - Grouped bars better for few runs (2-3)
   - Make configurable?

3. **Faceting vs stacking for 2D**: 
   - Stacked bars: Good for composition, hard to compare across runs
   - Facets (small multiples): Better for comparing runs, more space
   - Use both?

4. **Color scheme**: Dataset color vs variable color?
   - Option A: Color=dataset, facet=variable (better for comparing runs)
   - Option B: Color=variable, facet=dataset (better for seeing patterns)
