#!/usr/bin/env python3
"""
Copy updated MAZ employment files to TM2 model run directory
"""
import shutil
import os
from pathlib import Path

def copy_updated_maz_files():
    """Copy updated maz_data files to the TM2 model run directory"""
    
    print("=== COPYING UPDATED MAZ FILES TO MODEL RUN DIRECTORY ===")
    
    # Source: Box directory with updated files
    source_dir = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse")
    
    # Destination: TM2 model run directory  
    model_run_dir = Path(r"E:\TM2_2023_LU_Test3\inputs\landuse")
    
    # Files to copy
    files_to_copy = [
        'maz_data.csv',
        'maz_data_withDensity.csv'
    ]
    
    print(f"Source directory: {source_dir}")
    print(f"Destination directory: {model_run_dir}")
    
    # Check source directory exists
    if not source_dir.exists():
        print(f"❌ ERROR: Source directory does not exist: {source_dir}")
        return False
    
    # Ensure destination directory exists
    try:
        model_run_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Destination directory ready: {model_run_dir}")
    except Exception as e:
        print(f"❌ ERROR: Could not create destination directory: {e}")
        return False
    
    # Copy each file
    success_count = 0
    for fname in files_to_copy:
        src = source_dir / fname
        dst = model_run_dir / fname
        
        print(f"\nCopying {fname}...")
        print(f"  From: {src}")
        print(f"  To:   {dst}")
        
        if not src.exists():
            print(f"  ❌ ERROR: Source file not found")
            continue
            
        # Check if destination exists and create backup
        if dst.exists():
            backup_path = dst.with_suffix(dst.suffix + '.backup')
            try:
                shutil.copy2(dst, backup_path)
                print(f"  📋 Created backup: {backup_path}")
            except Exception as e:
                print(f"  ⚠️ WARNING: Could not create backup: {e}")
        
        # Copy the file
        try:
            shutil.copy2(src, dst)
            
            # Verify the copy
            if dst.exists():
                src_size = src.stat().st_size
                dst_size = dst.stat().st_size
                if src_size == dst_size:
                    print(f"  ✅ SUCCESS: Copied {fname} ({src_size:,} bytes)")
                    success_count += 1
                else:
                    print(f"  ❌ ERROR: File size mismatch (src: {src_size}, dst: {dst_size})")
            else:
                print(f"  ❌ ERROR: Destination file not created")
                
        except Exception as e:
            print(f"  ❌ ERROR: Copy failed - {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"COPY SUMMARY")
    print(f"{'='*60}")
    print(f"Files copied successfully: {success_count} / {len(files_to_copy)}")
    
    if success_count == len(files_to_copy):
        print("🎉 SUCCESS: All files copied successfully!")
        print("TM2 model run directory is now updated with fixed employment data.")
        print("This should resolve the ExplicitTelecommute crashes!")
        return True
    else:
        print("⚠️ WARNING: Some files failed to copy - check errors above")
        return False

def verify_employment_fixes():
    """Quick verification that the copied files have the employment fixes"""
    print(f"\n--- VERIFYING EMPLOYMENT FIXES ---")
    
    model_run_dir = Path(r"E:\TM2_2023_LU_Test3\inputs\landuse")
    
    try:
        import pandas as pd
        
        # Check maz_data.csv
        maz_data_path = model_run_dir / 'maz_data.csv'
        if maz_data_path.exists():
            df = pd.read_csv(maz_data_path)
            
            # Check for employment consistency using the CORRECT employment subcategories
            # CRITICAL: Include serv_pers instead of serv_per to match UEC expressions
            emp_cols = ['ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
                       'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
                       'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_pers', 'serv_soc', 'transp', 'util']
            
            available_emp_cols = [col for col in emp_cols if col in df.columns]
            
            if available_emp_cols and 'emp_total' in df.columns:
                df['emp_sum'] = df[available_emp_cols].sum(axis=1)
                mismatches = abs(df['emp_total'] - df['emp_sum']) > 0.01
                
                print(f"maz_data.csv verification:")
                print(f"  - Total MAZs: {len(df):,}")
                print(f"  - Employment mismatches: {mismatches.sum():,}")
                print(f"  - Status: {'✅ FIXED' if mismatches.sum() == 0 else '❌ ISSUES REMAIN'}")
            else:
                print("maz_data.csv: Cannot verify - missing employment columns")
        else:
            print("maz_data.csv: File not found for verification")
            
    except Exception as e:
        print(f"Verification error: {e}")
        print("Manual verification recommended")

if __name__ == "__main__":
    success = copy_updated_maz_files()
    
    if success:
        verify_employment_fixes()
    
    print(f"\nNext steps:")
    print(f"1. Run your TM2 model with the updated employment data")
    print(f"2. Check that ExplicitTelecommute no longer crashes on households")
    print(f"3. Look for the specific households that were failing (e.g., 3099105, 1817736)")