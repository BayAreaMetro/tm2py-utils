import pandas as pd

print("Creating combined dashboard datasets with ACS observed data...")

# 1. Regional auto ownership with ACS
model_regional = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_regional.csv')
acs_regional = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_regional.csv')

# Prepare ACS data to match model format
acs_regional_formatted = acs_regional.groupby('num_vehicles').agg({
    'households': 'sum',
    'share': 'sum'  # This will be recalculated
}).reset_index()

# Recalculate share
total_acs = acs_regional_formatted['households'].sum()
acs_regional_formatted['share'] = (acs_regional_formatted['households'] / total_acs * 100)
acs_regional_formatted['dataset'] = 'ACS 2023 Observed'

# Combine model and ACS data
combined_regional = pd.concat([model_regional, acs_regional_formatted], ignore_index=True)
combined_regional.to_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_regional.csv', index=False)
print("✓ Updated auto_ownership_regional.csv with ACS data")

# 2. ACS comparison dataset (already exists)
acs_comparison = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_by_household_size_acs.csv')
acs_data = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_regional.csv')

# Add ACS data to the comparison dataset
acs_data_formatted = acs_data.copy()
acs_data_formatted['num_persons_agg'] = acs_data_formatted['num_persons']  # ACS already has 1,2,3,4+ format
acs_data_formatted['dataset'] = 'ACS 2023 Observed'

combined_acs = pd.concat([acs_comparison, acs_data_formatted[['num_persons_agg', 'num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
combined_acs.to_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_by_household_size_acs.csv', index=False)
print("✓ Updated auto_ownership_by_household_size_acs.csv with ACS data")

# 3. County comparison with ACS
model_county = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_by_household_size_county.csv')
acs_county = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_county.csv')

# Add ACS county data
acs_county_formatted = acs_county.copy()
acs_county_formatted['num_persons_agg'] = acs_county_formatted['num_persons']
acs_county_formatted['dataset'] = 'ACS 2023 Observed'

combined_county = pd.concat([model_county, acs_county_formatted[['county', 'num_persons_agg', 'num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
combined_county.to_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_by_household_size_county.csv', index=False)
print("✓ Updated auto_ownership_by_household_size_county.csv with ACS data")

print("\n✅ Dashboard datasets now include ACS observed data for validation comparison")
print("Dashboard will show: 2015 Model | 2023 Model | ACS 2023 Observed")