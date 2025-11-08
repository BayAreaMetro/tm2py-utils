#!/usr/bin/env python3
"""
Verify PUMA-to-County assignments
"""
import pandas as pd

df = pd.read_csv('crosswalks/geo_cross_walk_tm2_maz.csv')
puma_county = df[['PUMA', 'COUNTY', 'county_name']].drop_duplicates().sort_values('PUMA')

print('PUMA-to-County assignments (one county per PUMA):')
print(f'Total unique PUMAs: {puma_county["PUMA"].nunique()}')
print(f'Counties represented: {sorted(puma_county["COUNTY"].unique())}')
print('\nFirst 15 PUMA-County assignments:')
print(puma_county.head(15).to_string(index=False))

print(f'\nTotal PUMA-County pairs: {len(puma_county)}')
print(f'Expected if one-to-one: {puma_county["PUMA"].nunique()}')

# Check for any PUMAs assigned to multiple counties (should be 0)
puma_counts = puma_county['PUMA'].value_counts()
multi_county_pumas = puma_counts[puma_counts > 1]
if len(multi_county_pumas) > 0:
    print(f'\nWARNING: {len(multi_county_pumas)} PUMAs assigned to multiple counties:')
    print(multi_county_pumas)
else:
    print('\n✅ SUCCESS: Each PUMA assigned to exactly one county')