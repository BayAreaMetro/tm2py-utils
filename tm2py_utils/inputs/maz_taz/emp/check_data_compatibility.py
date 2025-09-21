#!/usr/bin/env python3
"""
Check compatibility between 2023 land use data and synthetic population
to identify data mismatches causing Stop Location Choice crashes
"""
import pandas as pd
import numpy as np
import os

def check_landuse_popsyn_compatibility():
    """Check compatibility between land use and population synthesis data"""
    print("=== LANDUSE vs POPULATION SYNTHESIS COMPATIBILITY CHECK ===")
    
    # File paths
    landuse_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
    
    # Common popsyn file patterns to check
    popsyn_dir = r"E:\TM2_2023_LU_Test3\inputs\popsyn"
    
    try:
        # Load land use data
        print(f"Loading land use data from: {landuse_path}")
        landuse_df = pd.read_csv(landuse_path)
        print(f"Land use data: {len(landuse_df)} MAZ records")
        
        # Get MAZ and TAZ ranges from land use
        maz_min, maz_max = landuse_df['MAZ'].min(), landuse_df['MAZ'].max()
        taz_min, taz_max = landuse_df['TAZ'].min(), landuse_df['TAZ'].max()
        
        print(f"MAZ range: {maz_min} to {maz_max}")
        print(f"TAZ range: {taz_min} to {taz_max}")
        print(f"Unique MAZs in land use: {landuse_df['MAZ'].nunique():,}")
        print(f"Unique TAZs in land use: {landuse_df['TAZ'].nunique():,}")
        
        # Check for population synthesis files
        print(f"\n=== CHECKING POPULATION SYNTHESIS FILES ===")
        
        if not os.path.exists(popsyn_dir):
            print(f"❌ Population synthesis directory not found: {popsyn_dir}")
            return False
            
        popsyn_files = os.listdir(popsyn_dir)
        print(f"Files in popsyn directory: {len(popsyn_files)}")
        
        # Common popsyn file patterns
        household_files = [f for f in popsyn_files if 'household' in f.lower() or 'hh' in f.lower()]
        person_files = [f for f in popsyn_files if 'person' in f.lower()]
        
        print(f"Household files found: {household_files}")
        print(f"Person files found: {person_files}")
        
        # Check household file compatibility
        for hh_file in household_files:
            if hh_file.endswith('.csv'):
                try:
                    hh_path = os.path.join(popsyn_dir, hh_file)
                    print(f"\n--- Checking {hh_file} ---")
                    
                    # Read just a sample to check structure
                    hh_sample = pd.read_csv(hh_path, nrows=1000)
                    print(f"Sample households: {len(hh_sample)}")
                    print(f"Columns: {list(hh_sample.columns)}")
                    
                    # Check MAZ/TAZ references
                    maz_cols = [col for col in hh_sample.columns if 'maz' in col.lower()]
                    taz_cols = [col for col in hh_sample.columns if 'taz' in col.lower()]
                    
                    print(f"MAZ columns: {maz_cols}")
                    print(f"TAZ columns: {taz_cols}")
                    
                    # Check if household MAZs exist in land use data
                    for maz_col in maz_cols:
                        hh_mazs = hh_sample[maz_col].dropna().unique()
                        missing_mazs = set(hh_mazs) - set(landuse_df['MAZ'])
                        
                        if missing_mazs:
                            print(f"⚠️  {maz_col}: {len(missing_mazs)} MAZs not found in land use data")
                            print(f"   Sample missing MAZs: {sorted(list(missing_mazs))[:10]}")
                        else:
                            print(f"✅ {maz_col}: All MAZs found in land use data")
                    
                except Exception as e:
                    print(f"❌ Error reading {hh_file}: {e}")
        
        # Check for specific issues that could cause stop location choice problems
        print(f"\n=== STOP LOCATION CHOICE SPECIFIC CHECKS ===")
        
        # Check for MAZs with zero employment AND households
        zero_emp_hh = ((landuse_df['emp_total'] == 0) & (landuse_df['HH'] == 0)).sum()
        total_mazs = len(landuse_df)
        
        print(f"MAZs with zero employment AND zero households: {zero_emp_hh:,} ({zero_emp_hh/total_mazs*100:.1f}%)")
        
        # Check for MAZs that should be available for stops
        available_for_stops = ((landuse_df['emp_total'] > 0) | (landuse_df['HH'] > 0)).sum()
        print(f"MAZs available for stops: {available_for_stops:,} ({available_for_stops/total_mazs*100:.1f}%)")
        
        if available_for_stops == 0:
            print("❌ CRITICAL: No MAZs available for stops!")
            return False
        
        # Check coordinate validity
        invalid_coords = ((landuse_df['MAZ_X'] == -1) | (landuse_df['MAZ_Y'] == -1)).sum()
        print(f"MAZs with invalid coordinates: {invalid_coords:,}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_employment_data_issues():
    """Check for employment data issues specific to stop choice"""
    print(f"\n=== EMPLOYMENT DATA VALIDATION ===")
    
    try:
        landuse_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(landuse_path)
        
        # Check employment columns exist and have valid data
        emp_columns = ['emp_total', 'ret_loc', 'ret_reg', 'serv_pers', 'health', 
                      'eat', 'serv_soc', 'art_rec', 'gov', 'info']
        
        missing_cols = [col for col in emp_columns if col not in df.columns]
        if missing_cols:
            print(f"❌ Missing employment columns: {missing_cols}")
            return False
        
        # Check for negative employment values
        for col in emp_columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                print(f"⚠️  {col}: {negative_count} negative values")
        
        # Check for NaN employment values
        for col in emp_columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                print(f"⚠️  {col}: {nan_count} NaN values")
        
        print("✅ Employment data structure looks valid")
        return True
        
    except Exception as e:
        print(f"Error checking employment data: {e}")
        return False

def suggest_data_fixes():
    """Suggest potential fixes for data compatibility issues"""
    print(f"\n=== SUGGESTED DATA COMPATIBILITY FIXES ===")
    
    print("1. MAZ/TAZ ID Mapping Issues:")
    print("   - Check if population synthesis uses old MAZ/TAZ IDs")
    print("   - Create mapping between old and new ID systems")
    print("   - Update population files to use new IDs")
    
    print(f"\n2. Missing MAZs:")
    print("   - Identify MAZs referenced in population but missing from land use")
    print("   - Either add missing MAZs to land use or remove from population")
    
    print(f"\n3. Data Schema Changes:")
    print("   - Verify column names match what model expects")
    print("   - Check for renamed employment categories")
    print("   - Ensure coordinate systems are consistent")
    
    print(f"\n4. Model Configuration Updates:")
    print("   - Update file paths in properties files")
    print("   - Verify TAZ/MAZ ranges in model settings")
    print("   - Check alternative sampling parameters")

if __name__ == "__main__":
    landuse_ok = check_landuse_popsyn_compatibility()
    emp_ok = check_employment_data_issues()
    
    if landuse_ok and emp_ok:
        print(f"\n✅ Data structure looks compatible")
        print("Issue may be in alternative sampling or choice set generation")
    else:
        print(f"\n❌ Data compatibility issues found")
        suggest_data_fixes()
        
    print(f"\n=== NEXT STEPS ===")
    print("1. Run this analysis to identify specific data mismatches")
    print("2. Check model logs for which household/MAZ combinations fail")
    print("3. Compare 2015 vs 2023 data structures for differences")
    print("4. Test with a small subset of households to isolate the issue")