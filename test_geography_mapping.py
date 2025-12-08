import pandas as pd
import yaml

# Test the exact same logic as the loader
with open('tm2py_utils/summary/validation/data_model/ctramp_data_model.yaml', 'r') as f:
    config = yaml.safe_load(f)

input_schema = config.get('input_schema', {})
geo_config = input_schema.get('geography_lookup', {})

geography_lookup_config = {
    'file_path': geo_config.get('file_path'),
    'columns': geo_config.get('columns', {})
}

print("Geography lookup config:")
print(geography_lookup_config)
print()

# Load the file the same way
file_path = geography_lookup_config.get('file_path')
columns_config = geography_lookup_config.get('columns', {})

print("File path:", file_path)
print("Columns config:", columns_config)
print()

# Load only needed columns
usecols = list(columns_config.values()) if columns_config else None
print("Using columns:", usecols)

geo_df = pd.read_csv(file_path, usecols=usecols)
print(f"Loaded columns: {geo_df.columns.tolist()}")
print()

# Rename to internal names
if columns_config:
    rename_map = {v: k for k, v in columns_config.items()}
    print("Rename mapping (CSV -> internal):")
    for csv, internal in rename_map.items():
        print(f"  {csv} -> {internal}")
    
    geo_df_renamed = geo_df.rename(columns=rename_map)
    print(f"Final columns: {geo_df_renamed.columns.tolist()}")
    
    # Check for maz_node column
    if 'maz_node' in geo_df_renamed.columns:
        print("✓ 'maz_node' column found!")
        print(f"Sample values: {geo_df_renamed['maz_node'].head().tolist()}")
    else:
        print("✗ 'maz_node' column NOT found")
else:
    print("No columns config found")