import pandas as pd

# Check household data structure more thoroughly
print('Checking household data structure...')
hh_df = pd.read_csv('A:/2023-tm22-dev-version-05/ctramp_output/householdData_1.csv', nrows=100)
print('Household columns:')
print(hh_df.columns.tolist())
print()

# Look for any columns that might relate to MAZ
maz_columns = [col for col in hh_df.columns if 'maz' in col.lower() or 'mgra' in col.lower()]
print('Columns with MAZ or MGRA:', maz_columns)
print()

# Check unique home_mgra values to see the pattern
unique_mgras = pd.read_csv('A:/2023-tm22-dev-version-05/ctramp_output/householdData_1.csv')['home_mgra'].unique()
print(f'Total unique home_mgra values: {len(unique_mgras)}')
print(f'Min: {unique_mgras.min()}, Max: {unique_mgras.max()}')
print('Sample values:', sorted(unique_mgras)[:20])
print()

# Check geography file for any sequential ID column
geo_df = pd.read_csv('tm2py_utils/inputs/maz_taz/mazs_tazs_county_tract_PUMA_2.5.csv')
print('Geography columns again:')
for col in geo_df.columns:
    sample_vals = geo_df[col].head(5).tolist()
    print(f'{col}: {sample_vals}')
    if col == 'MAZ_SEQ':
        print(f'  MAZ_SEQ range: {geo_df[col].min()} to {geo_df[col].max()}')
        print(f'  MAZ_SEQ unique count: {geo_df[col].nunique()}')
print()

# Check if MAZ_SEQ matches household mgra pattern
if 'MAZ_SEQ' in geo_df.columns:
    maz_seq_range = (geo_df['MAZ_SEQ'].min(), geo_df['MAZ_SEQ'].max())
    mgra_range = (unique_mgras.min(), unique_mgras.max())
    print(f'MAZ_SEQ range: {maz_seq_range}')
    print(f'home_mgra range: {mgra_range}')
    
    # Check overlap using MAZ_SEQ instead
    overlap_seq = pd.Series(unique_mgras).isin(geo_df['MAZ_SEQ']).sum()
    print(f'home_mgra values matching MAZ_SEQ: {overlap_seq}/{len(unique_mgras)} ({overlap_seq/len(unique_mgras)*100:.1f}%)')