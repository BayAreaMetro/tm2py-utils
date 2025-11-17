"""
Quick script to check sampleRate values in CTRAMP output files.
This will help us confirm if sampleRate is:
  - A sampling percentage (0.1 = 10% sample), or
  - An expansion factor (10.0 = 10% sample)
"""

import pandas as pd
from pathlib import Path
import sys

def check_sample_rate(file_path):
    """Check sampleRate values in a CSV file."""
    print(f"\nChecking: {file_path.name}")
    print("=" * 60)
    
    try:
        df = pd.read_csv(file_path)
        
        if 'sampleRate' not in df.columns:
            print("  ⚠ No 'sampleRate' column found")
            return
        
        sr = df['sampleRate']
        
        print(f"  Total records: {len(df):,}")
        print(f"\n  sampleRate statistics:")
        print(f"    Min:    {sr.min():.4f}")
        print(f"    Max:    {sr.max():.4f}")
        print(f"    Mean:   {sr.mean():.4f}")
        print(f"    Median: {sr.median():.4f}")
        print(f"    Std:    {sr.std():.4f}")
        
        print(f"\n  Unique values: {sr.nunique()}")
        unique_vals = sr.unique()
        if len(unique_vals) <= 10:
            print(f"    {sorted(unique_vals)}")
        else:
            print(f"    First 10: {sorted(unique_vals)[:10]}")
        
        print(f"\n  Value counts:")
        print(sr.value_counts().head(5).to_string())
        
        # Interpretation hint
        if sr.mean() < 1.0:
            print("\n  💡 INTERPRETATION: Values < 1.0 suggest this is sampling percentage")
            print("     Example: 0.1 = 10% sample")
            print("     ⚠ Our weight config may need to use 1/sampleRate for expansion")
        else:
            print("\n  💡 INTERPRETATION: Values > 1.0 suggest this is expansion factor")
            print("     Example: 10.0 = 10% sample (multiply by 10 to get population)")
            print("     ✓ Our weight config is correct as-is")
            
    except Exception as e:
        print(f"  ✗ Error: {e}")

def main():
    # Check if path provided as argument
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if file_path.exists():
            check_sample_rate(file_path)
        else:
            print(f"File not found: {file_path}")
        return
    
    # Otherwise, look for common CTRAMP output files
    print("Searching for CTRAMP output files in model config directories...")
    print("(You can also run: python check_sample_rate.py path/to/file.csv)")
    
    # Look in config-specific model run directories
    config_dirs = [
        Path("tm2py_utils/config/2023-tm22-dev-version-05"),
        Path("tm2py_utils/config/2015-tm22-dev-sprint-04"),
        Path("tm2py_utils/config/develop"),
    ]
    
    search_patterns = [
        "**/ctramp_output/householdData_*.csv",
        "**/ctramp_output/indivTourData_*.csv",
        "**/householdData_*.csv",
        "**/indivTourData_*.csv",
        "**/personData_*.csv"
    ]
    
    found_files = []
    
    # Search in config directories
    for config_dir in config_dirs:
        if config_dir.exists():
            for pattern in search_patterns:
                found_files.extend(config_dir.glob(pattern))
    
    # Also search current directory
    for pattern in search_patterns:
        found_files.extend(Path('.').glob(pattern))
    
    if not found_files:
        print("\n⚠ No CTRAMP output files found")
        print("\nSearched in:")
        for config_dir in config_dirs:
            print(f"  - {config_dir}/ctramp_output/")
        print(f"  - Current directory")
        print("\nTo check a specific file, run:")
        print("  python check_sample_rate.py path/to/householdData_1.csv")
        print("\nNote: From model_config.toml, sample rates are configured as:")
        print("  sample_rate_by_iteration = [0.05, 0.5, 1.0, 0.02, 0.02]")
        print("  (0.05 = 5% sample, 0.5 = 50% sample, 1.0 = 100% sample)")
        return
    
    # Check up to 3 files
    for file_path in found_files[:3]:
        check_sample_rate(file_path)
    
    if len(found_files) > 3:
        print(f"\n... and {len(found_files) - 3} more files")

if __name__ == "__main__":
    main()
