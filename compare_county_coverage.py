import pandas as pd

# Load model county data  
model_county = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/auto_ownership_by_household_size_county.csv')
model_county_2023 = model_county[model_county['dataset'] == '2023 TM2.2 v05']

# Load ACS county data
acs_county = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_county.csv')

print('Model county data by county:')
county_counts = model_county_2023['county'].value_counts().sort_index()
print(county_counts)
print()

print('ACS county data by county:')  
acs_county_counts = acs_county['county'].value_counts().sort_index()
print(acs_county_counts)
print()

print('Counties in both datasets:')
model_counties = set(model_county_2023['county'].unique())
acs_counties = set(acs_county['county'].unique())
common = model_counties.intersection(acs_counties)
print(f'Common counties: {len(common)}/{len(acs_counties)} ACS counties covered')
print(sorted(common))

# Test a quick comparison for Alameda County
print()
print('Sample comparison - Alameda County, 0 vehicles:')
alameda_model = model_county_2023[(model_county_2023['county'] == 'Alameda') & (model_county_2023['num_vehicles'] == 0)]
alameda_acs = acs_county[(acs_county['county'] == 'Alameda') & (acs_county['num_vehicles'] == 0)]

if len(alameda_model) > 0 and len(alameda_acs) > 0:
    print('Model (Alameda, 0 vehicles):')
    for _, row in alameda_model.iterrows():
        print(f'  {row["num_persons_agg"]} persons: {row["share"]:.1f}%')
    print('ACS (Alameda, 0 vehicles):') 
    for _, row in alameda_acs.iterrows():
        print(f'  {row["num_persons"]} persons: {row["share"]:.1f}%')