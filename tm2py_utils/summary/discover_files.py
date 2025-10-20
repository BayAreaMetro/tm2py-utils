"""
Quick file discovery script for TM2 core summaries

This script will list all files in your core_summaries directory and help you 
understand what data is available before running the full analysis.
"""

from pathlib import Path
import pandas as pd

# Your actual data directory
DATA_DIR = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\core_summaries")

def discover_files():
    """Discover and examine files in the core summaries directory."""
    
    print("=" * 70)
    print("TM2 CORE SUMMARIES FILE DISCOVERY")
    print("=" * 70)
    print(f"Directory: {DATA_DIR}")
    
    if not DATA_DIR.exists():
        print(f"ERROR: Directory not found: {DATA_DIR}")
        return
    
    # Find all data files
    csv_files = list(DATA_DIR.glob('*.csv'))
    xlsx_files = list(DATA_DIR.glob('*.xlsx'))
    all_files = csv_files + xlsx_files
    
    print(f"\nFound {len(all_files)} data files:")
    print(f"  CSV files: {len(csv_files)}")
    print(f"  Excel files: {len(xlsx_files)}")
    
    if not all_files:
        print("No CSV or Excel files found.")
        return
    
    print(f"\nFile listing:")
    for i, file in enumerate(sorted(all_files), 1):
        print(f"  {i:2d}. {file.name}")
    
    # Sample a few files to understand structure
    print(f"\nSampling file contents (first 3 files):")
    for file in sorted(all_files)[:3]:
        try:
            if file.suffix.lower() == '.csv':
                df = pd.read_csv(file, nrows=5)  # Read just first 5 rows
            elif file.suffix.lower() == '.xlsx':
                df = pd.read_excel(file, nrows=5)
            else:
                continue
            
            print(f"\n📄 {file.name}")
            print(f"   Shape: {df.shape[0]}+ rows, {df.shape[1]} columns")
            print(f"   Columns: {list(df.columns)}")
            if not df.empty:
                print(f"   Sample data:")
                print(f"   {df.head(2).to_string(index=False)}")
                
        except Exception as e:
            print(f"\n📄 {file.name}")
            print(f"   ERROR reading file: {e}")
    
    print(f"\n" + "=" * 70)
    print("DISCOVERY COMPLETE")
    print("=" * 70)
    print(f"You can now run the analysis script:")
    print(f"  python aggregated_analysis.py analysis_config.toml")
    print(f"")
    print(f"Or interactively:")
    print(f"  python aggregated_analysis.py")

if __name__ == "__main__":
    discover_files()