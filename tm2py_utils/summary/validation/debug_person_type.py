"""Quick test to debug person_type_name issue"""
import pandas as pd
import yaml
from pathlib import Path

# Load config
config_path = Path('data_model/ctramp_data_model.yaml')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Load persons data
persons_file = Path('A:/2015-tm22-dev-sprint-04/ctramp_output/personData_3.csv')
df = pd.read_csv(persons_file, nrows=1000)

print("Original columns with 'type':", [c for c in df.columns if 'type' in c.lower()])
print("Sample 'type' values:", df['type'].value_counts().head())
print()

# Apply standardization (like load_ctramp_data does)
schema = config['input_schema']['persons']
cols_map = {}
for std_name, file_col in schema['columns']['required'].items():
    cols_map[file_col] = std_name

df = df.rename(columns=cols_map)
print("After standardization, columns with 'type':", [c for c in df.columns if 'type' in c.lower()])
print("person_type exists?", 'person_type' in df.columns)
if 'person_type' in df.columns:
    print("Sample person_type values:", df['person_type'].value_counts().head())
print()

# Apply value labels (like apply_value_labels does)
value_mappings = config['value_mappings']
for col in df.columns:
    mapping_key = col
    if mapping_key in value_mappings:
        mapping_dict = value_mappings[mapping_key]
        print(f"Processing column '{col}'...")
        print(f"  Mapping dict keys: {mapping_dict.keys()}")
        
        if isinstance(mapping_dict, dict) and 'values' in mapping_dict:
            mapping = mapping_dict['values']
            label_col = f"{col}_name"
            df[label_col] = df[col].map(mapping)
            print(f"  Created '{label_col}' using numeric mapping")
            print(f"  Non-null values: {df[label_col].notna().sum()}")
        elif isinstance(mapping_dict, dict) and 'text_values' in mapping_dict:
            label_col = f"{col}_name"
            df[label_col] = df[col]
            print(f"  Created '{label_col}' by copying (text values)")
            print(f"  Non-null values: {df[label_col].notna().sum()}")

print()
print("Final columns with 'type':", [c for c in df.columns if 'type' in c.lower()])
print("person_type_name exists?", 'person_type_name' in df.columns)
if 'person_type_name' in df.columns:
    print("Sample person_type_name values:", df['person_type_name'].value_counts().head())
