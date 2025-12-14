# External Observed Data

Reference guide for observed data sources used for model validation.

## Overview

The summaries generated from CTRAMP model runs can be compared against observed data from external sources like census data, employment surveys, and synthetic population outputs.

**Available External Data Sources:**

### PopulationSim Summaries

Pre-generated PopulationSim summary files are stored in:
```
tm2py_utils/summary/validation/outputs/populationsim/
```

**Files included:**
- `households_by_county.csv` - Household distribution by county
- `households_by_income.csv` - Household income distribution  
- `households_by_workers.csv` - Household worker distribution
- `household_size_regional.csv` - Regional household size distribution
- `persons_by_age.csv` - Population age distribution

**Source:** These files are generated from PopulationSim output (`aggregate_summaries/`) and copied here for reference alongside CTRAMP model outputs.

See the [README](../tm2py_utils/summary/validation/outputs/populationsim/README.md) in that directory for more details.

### ACS (American Community Survey) Data

ACS observed data files are stored in:
```
tm2py_utils/summary/validation/outputs/observed/
```

**Files included:**
- `acs_auto_ownership_by_household_size.csv`
- `acs_auto_ownership_by_household_size_county.csv`
- `acs_auto_ownership_by_household_size_regional.csv`

### Other External Sources

Additional external data sources that may be useful for validation:
- **CTPP** (Census Transportation Planning Products) - Journey-to-work patterns
- **External surveys** - Employment surveys, regional studies
- **Other tabulated data** - Pre-aggregated statistics

**Note:** This is for **pre-aggregated summary data from external sources**, not household travel survey microdata. Household travel surveys should be formatted to match the [CTRAMP data model](configuration.md) and processed as model inputs.

---

## Using Observed Data

The observed data files can be used for manual comparison with model summaries, loaded into analysis tools like Excel or R, or incorporated into custom validation workflows.

For information on the model summary format and available summaries, see:
- [Summary Definitions](summaries.md) - List of all 30 available summaries
- [Generate Summaries](generate-summaries.md) - How to run the summarizer
- [Configuration Reference](configuration.md) - YAML data model documentation
