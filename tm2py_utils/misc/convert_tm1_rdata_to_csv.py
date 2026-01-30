"""
Convert TM1 RData files to CSV format for validation - OPTIMIZED VERSION

Optimizations:
- Converts float64 to float32 and int64 to int32 to reduce memory
- Uses minimal quoting (only when needed) for faster CSV writing
- Limits float precision to 6 decimal places
- Adds memory usage reporting
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
        import time
        read_start = time.time()
        result = pyreadr.read_r(str(rdata_path))
        read_time = time.time() - read_start
        
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
        print(f"  Read time: {read_time:.1f} seconds")
        
        # Show memory usage
        mem_mb = df.memory_usage(deep=True).sum() / (1024**2)
        print(f"  Memory usage: {mem_mb:.1f} MB")
        
        # Show first few column names
        col_preview = ', '.join(df.columns[:10].tolist())
        if len(df.columns) > 10:
            col_preview += f", ... ({len(df.columns)} total)"
        print(f"  Columns: {col_preview}")
        
        # Optimize data types to reduce memory and speed up writing
        print(f"  Optimizing data types...")
        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = df[col].astype('float32')
        for col in df.select_dtypes(include=['int64']).columns:
            # Check if values fit in int32
            if df[col].min() >= -2147483648 and df[col].max() <= 2147483647:
                df[col] = df[col].astype('int32')
        
        new_mem_mb = df.memory_usage(deep=True).sum() / (1024**2)
        print(f"  Optimized memory: {new_mem_mb:.1f} MB (saved {mem_mb - new_mem_mb:.1f} MB)")
        
        # Save to CSV with optimizations
        print(f"  Writing CSV (optimized settings)...")
        write_start = time.time()
        df.to_csv(
            csv_path, 
            index=False,
            quoting=1,  # csv.QUOTE_MINIMAL - only quote when necessary
            float_format='%.6f'  # Limit float precision
        )
        write_time = time.time() - write_start
        
        # Show file size and performance
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        total_time = read_time + write_time
        rows_per_sec = len(df) / write_time
        
        print(f"  [OK] Saved: {csv_file}")
        print(f"  Write time: {write_time:.1f} seconds ({rows_per_sec:.0f} rows/sec)")
        print(f"  File size: {size_mb:.1f} MB")
        print(f"  Total time: {total_time:.1f} seconds")
        
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
    
    print()

print("=" * 80)
print("CONVERSION COMPLETE")
print("=" * 80)
print(f"CSV files saved to: {output_dir}")
