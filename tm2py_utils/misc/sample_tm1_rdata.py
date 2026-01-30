"""
Quick preview of TM1 RData files - exports just first 10,000 rows for validation testing
"""
import pyreadr
import pandas as pd
from pathlib import Path

# Directories
rdata_dir = Path(r"M:\Application\Model One\RTP2025\IncrementalProgress\2023_TM161_IPA_35\OUTPUT\updated_output")
output_dir = Path(r"M:\Application\Model One\RTP2025\IncrementalProgress\2023_TM161_IPA_35\OUTPUT\ctramp_csv_sample")

# Create output directory
output_dir.mkdir(parents=True, exist_ok=True)

# Sample size
SAMPLE_SIZE = 10000

# Files to convert
rdata_files = {
    "households.rdata": "householdData_sample.csv",
    "persons.rdata": "personData_sample.csv",
    "tours.rdata": "indivTourData_sample.csv",
    "trips.rdata": "indivTripData_sample.csv",
}

print("=" * 80)
print("TM1 RData Sample Extractor (First 10K rows)")
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
        import time
        start = time.time()
        result = pyreadr.read_r(str(rdata_path))
        read_time = time.time() - start
        
        if len(result) == 0:
            print(f"  [ERROR] No objects found in file")
            continue
        
        # Get the first dataframe
        obj_name = list(result.keys())[0]
        df = result[obj_name]
        
        print(f"  Read time: {read_time:.1f}s")
        print(f"  Object: {obj_name}")
        print(f"  Full size: {len(df):,} rows, {len(df.columns)} columns")
        
        # Take sample
        if len(df) > SAMPLE_SIZE:
            df_sample = df.head(SAMPLE_SIZE)
            print(f"  Sampling: {SAMPLE_SIZE:,} rows (first {SAMPLE_SIZE} records)")
        else:
            df_sample = df
            print(f"  Using all rows (< {SAMPLE_SIZE:,})")
        
        # Show columns
        col_preview = ', '.join(df.columns[:15].tolist())
        if len(df.columns) > 15:
            col_preview += f", ... ({len(df.columns)} total)"
        print(f"  Columns: {col_preview}")
        
        # Save sample to CSV
        write_start = time.time()
        df_sample.to_csv(csv_path, index=False)
        write_time = time.time() - write_start
        
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] Saved: {csv_file} ({size_mb:.1f} MB, took {write_time:.1f}s)")
        
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
    
    print()

print("=" * 80)
print("SAMPLE EXTRACTION COMPLETE")
print("=" * 80)
print(f"Sample files saved to: {output_dir}")
print("\nNow you can run validation on the sample directory to test the data model.")
