import pandas as pd
import yaml

# Load the config to see what columns are expected
with open('tm2py_utils/summary/validation/data_model/ctramp_data_model.yaml', 'r') as f:
    config = yaml.safe_load(f)

geo_config = config.get('schema', {}).get('geography_lookup', {})
print("Geography config:")
print(geo_config)
print()

# Test the column mapping
columns_config = geo_config.get('columns', {})
print("Column mapping:")
for internal, csv in columns_config.items():
    print(f"  {internal} -> {csv}")
print()

# Load geography file to test the mapping
geo_file = 'tm2py_utils/inputs/maz_taz/mazs_tazs_county_tract_PUMA_2.5.csv'
geo_df = pd.read_csv(geo_file)
print(f"Geography file columns: {geo_df.columns.tolist()}")
print()

# Apply the rename mapping
if columns_config:
    rename_map = {v: k for k, v in columns_config.items()}
    print("Rename mapping (CSV -> internal):")
    for csv, internal in rename_map.items():
        print(f"  {csv} -> {internal}")
    
    geo_renamed = geo_df.rename(columns=rename_map)
    print(f"Renamed columns: {geo_renamed.columns.tolist()}")
    print()
    
    # Check if maz_node exists after rename
    if 'maz_node' in geo_renamed.columns:
        print("✓ 'maz_node' column exists after rename")
        print(f"Sample maz_node values: {geo_renamed['maz_node'].head().tolist()}")
    else:
        print("✗ 'maz_node' column NOT found after rename")