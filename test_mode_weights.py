import sys
sys.path.insert(0, 'tm2py_utils/summary')
from ctramp_data_model_loader import load_data_model

dm = load_data_model()

print("Testing individual_tours column mapping:")
mapping = dm.get_column_mapping('individual_tours')
print(f"  Has sampleRate key: {'sampleRate' in mapping}")
print(f"  sampleRate maps to: {mapping.get('sampleRate', 'NOT FOUND')}")
print(f"  Total mappings: {len(mapping)}")

print("\nTesting individual_tours weight field:")
weight_field = dm.get_weight_field('individual_tours')
print(f"  Weight field: {weight_field}")

weight_info = dm.weight_fields.get('individual_tours', {})
print(f"  Should invert: {weight_info.get('invert', False)}")

print("\nAll weight field keys:")
print(f"  {list(dm.weight_fields.keys())}")

print("\nSample of column mappings:")
for i, (k, v) in enumerate(mapping.items()):
    if i >= 10:
        break
    print(f"  {k} -> {v}")
