"""
Convert TM1 RData files to CSV format for validation
"""
import pyreadr
import pandas as pd
from pathlib import Path

# Directories
rdata_dir = Path(r"M:\Application\Model One\RTP2025\IncrementalProgress\2023_TM161_IPA_35\OUTPUT\updated_output")
output_dir = Path(r"M:\Application\Model One\RTP2025\IncrementalProgress\2023_TM161_IPA_35\OUTPUT\ctramp_csv")

# Create output directory
output_dir.mkdir(parents=True, exist_ok=True)

# Files to convert
rdata_files = {
    "households.rdata": "householdData_final.csv",
    "persons.rdata": "personData_final.csv",
    "tours.rdata": "indivTourData_final.csv",
    "trips.rdata": "indivTripData_final.csv",
    "work_locations.rdata": "wsLocResults.csv",
}

print("=" * 80)
print("TM1 RData to CSV Converter")
print("=" * 80)
print(f"Source: {rdata_dir}")
print(f"Output: {output_dir}")
print()

for rdata_file, csv_file in rdata_files.items():
    rdata_path = rdata_dir / rdata_file
    csv_path = output_dir / csv_file
    
    print(f"Processing: {rdata_file}")
    
    if not rdata_path.exists():
        print(f"  [SKIP] File not found")
        continue
    
    try:
        # Read .rdata file
        result = pyreadr.read_r(str(rdata_path))
        
        # .rdata files can contain multiple objects
        # Usually there's just one data frame with a predictable name
        if len(result) == 0:
            print(f"  [ERROR] No objects found in file")
            continue
        
        # Get the first (and usually only) dataframe
        obj_name = list(result.keys())[0]
        df = result[obj_name]
        
        print(f"  Object: {obj_name}")
        print(f"  Rows: {len(df):,}, Columns: {len(df.columns)}")
        
        # Show first few column names
        col_preview = ', '.join(df.columns[:10].tolist())
        if len(df.columns) > 10:
            col_preview += f", ... ({len(df.columns)} total)"
        print(f"  Columns: {col_preview}")
        
        # Save to CSV
        print(f"  Writing CSV (this may take a while for large files)...")
        import time
        start = time.time()
        df.to_csv(csv_path, index=False)
        elapsed = time.time() - start
        print(f"  [OK] Saved: {csv_file} (took {elapsed:.1f} seconds)")
        
        # Show file size
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"  File size: {size_mb:.1f} MB")
        
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
    
    print()

print("=" * 80)
print("CONVERSION COMPLETE")
print("=" * 80)
print(f"CSV files saved to: {output_dir}")
