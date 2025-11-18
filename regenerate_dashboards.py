"""Quick script to regenerate SimWrapper dashboards from existing CSV files."""

import pandas as pd
from pathlib import Path
from tm2py_utils.summary.validation.simwrapper_writer import (
    create_household_dashboard,
    create_tour_dashboard, 
    create_trip_dashboard
)

# Load existing summary CSVs and combine by type
validation_dir = Path("tm2py_utils/summary/validation")
csv_files = list(validation_dir.glob("*.csv"))

# Group by summary type and combine datasets
summaries = {}
for csv_path in csv_files:
    if csv_path.name == "summary_index.csv":
        continue
    
    df = pd.read_csv(csv_path)
    
    # Extract base name (remove dataset suffix)
    name = csv_path.stem
    for dataset in ['2023_version_05', '2015_sprint_04']:
        if name.endswith(f'_{dataset}'):
            base_name = name.replace(f'_{dataset}', '')
            if base_name not in summaries:
                summaries[base_name] = []
            summaries[base_name].append(df)
            break

# Concatenate dataframes with same base name
combined = {}
for base_name, dfs in summaries.items():
    if len(dfs) == 1:
        combined[base_name] = dfs[0]
    else:
        combined[base_name] = pd.concat(dfs, ignore_index=True)

print(f"Combined {len(summaries)} summaries into {len(combined)} multi-run tables")

# Create SimWrapper output directory
simwrapper_dir = validation_dir / "simwrapper"
simwrapper_dir.mkdir(exist_ok=True)

# Group by type
household_summaries = {k: v for k, v in combined.items() if 'household' in k or 'auto_ownership' in k or 'income' in k}
tour_summaries = {k: v for k, v in combined.items() if 'tour' in k}
trip_summaries = {k: v for k, v in combined.items() if 'trip' in k}

# Create dashboards
if household_summaries:
    create_household_dashboard(simwrapper_dir, household_summaries)
    print(f"✓ Created household dashboard with {len(household_summaries)} summaries")

if tour_summaries:
    create_tour_dashboard(simwrapper_dir, tour_summaries)
    print(f"✓ Created tour dashboard with {len(tour_summaries)} summaries")

if trip_summaries:
    create_trip_dashboard(simwrapper_dir, trip_summaries)
    print(f"✓ Created trip dashboard with {len(trip_summaries)} summaries")

print(f"\n✓ SimWrapper dashboards saved to {simwrapper_dir}")
