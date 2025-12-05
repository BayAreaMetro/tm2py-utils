import pandas as pd

# Check geography file
geo_df = pd.read_csv('tm2py_utils/inputs/maz_taz/mazs_tazs_county_tract_PUMA_2.5.csv')
print('Geography file info:')
print(f'Total MAZs: {len(geo_df)}')
print('Counties:')
print(geo_df['county_name'].value_counts())
print()

# Check columns in geography file
print('Geography columns:')
print(geo_df.columns.tolist())
print()

# Check a sample of households data to see home_mgra range
print('Loading a small sample of household data...')
hh_sample = pd.read_csv('A:/2023-tm22-dev-version-05/ctramp_output/householdData_1.csv', nrows=1000)
print(f'Sample home_mgra range: {hh_sample["home_mgra"].min()} to {hh_sample["home_mgra"].max()}')
print()

# Check overlap
maz_min = geo_df['MAZ_NODE'].min()
maz_max = geo_df['MAZ_NODE'].max()
print(f'MAZ_NODE range in geography: {maz_min} to {maz_max}')
overlap = hh_sample['home_mgra'].isin(geo_df['MAZ_NODE']).sum()
total = len(hh_sample)
pct = overlap/total*100
print(f'Households with home_mgra in geography file: {overlap}/{total} ({pct:.1f}%)')

# Show some examples
print('\nFirst few MAZ_NODE values in geography:')
print(geo_df['MAZ_NODE'].head(10).tolist())
print('\nFirst few home_mgra values in households:')
print(hh_sample['home_mgra'].head(10).tolist())

# Check if MAZ_NODE values are in the household range
hh_min = hh_sample['home_mgra'].min()
hh_max = hh_sample['home_mgra'].max()
maz_in_hh_range = geo_df[(geo_df['MAZ_NODE'] >= hh_min) & (geo_df['MAZ_NODE'] <= hh_max)]
print(f'\nMAZ values in household range ({hh_min}-{hh_max}): {len(maz_in_hh_range)}/{len(geo_df)}')