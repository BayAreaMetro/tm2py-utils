# PopulationSim Summaries

This directory contains pre-generated summary files from PopulationSim runs.

## Files

**CSV Summary Files:**
- `households_by_county.csv` - Household distribution by county
- `households_by_income.csv` - Household income distribution
- `households_by_workers.csv` - Household worker distribution
- `household_size_regional.csv` - Regional household size distribution
- `persons_by_age.csv` - Population age distribution

**Dashboard Configuration:**
- `dashboard-populationsim.yaml` - SimWrapper dashboard configuration for PopulationSim multi-year comparison

## Source

These files are generated from PopulationSim output aggregate summaries and copied here for validation dashboard use.

**Default source location:**
```
C:\GitHub\populationsim\bay_area\output_2023\aggregate_summaries
```

## Usage

These summaries are used alongside CTRAMP model output summaries for comprehensive validation in the SimWrapper dashboard.

See: `../dashboard/` for the complete validation dashboard deployment.
