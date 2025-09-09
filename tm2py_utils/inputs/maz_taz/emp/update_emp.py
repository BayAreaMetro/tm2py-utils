def print_column_summary(jobs, maz_data, maz_density):
    jobs_cols = set(jobs.columns)
    maz_data_cols = set(maz_data.columns)
    maz_density_cols = set(maz_density.columns)

    print("\n--- COLUMN SUMMARY ---")
    print(f"jobs_maz_2023_v1.csv columns: {sorted(jobs_cols)}")
    print(f"maz_data.csv columns: {sorted(maz_data_cols)}")
    print(f"maz_data_withDensity.csv columns: {sorted(maz_density_cols)}")

    # Columns in all three
    all_three = jobs_cols & maz_data_cols & maz_density_cols
    print(f"\nColumns in ALL THREE files: {sorted(all_three)}")

    # Pairwise intersections
    jobs_maz_data = jobs_cols & maz_data_cols
    jobs_maz_density = jobs_cols & maz_density_cols
    maz_data_maz_density = maz_data_cols & maz_density_cols

    print(f"\nColumns in BOTH jobs_maz_2023_v1.csv and maz_data.csv: {sorted(jobs_maz_data)}")
    print(f"Columns in BOTH jobs_maz_2023_v1.csv and maz_data_withDensity.csv: {sorted(jobs_maz_density)}")
    print(f"Columns in BOTH maz_data.csv and maz_data_withDensity.csv: {sorted(maz_data_maz_density)}")

    # Unique columns
    print(f"\nColumns UNIQUE to jobs_maz_2023_v1.csv: {sorted(jobs_cols - maz_data_cols - maz_density_cols)}")
    print(f"Columns UNIQUE to maz_data.csv: {sorted(maz_data_cols - jobs_cols - maz_density_cols)}")
    print(f"Columns UNIQUE to maz_data_withDensity.csv: {sorted(maz_density_cols - jobs_cols - maz_data_cols)}")

# This is how we are supposed to do this: https://github.com/BayAreaMetro/travel-model-two/blob/master/model-files/scripts/preprocess/createMazDensityFile.py

import os
import pandas as pd

# Paths to files
TARGET_DIR = r"C:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse"
JOBS_FILE = os.path.join(TARGET_DIR, "jobs_maz_2023_v1.csv")
MAZ_DATA_FILE = os.path.join(TARGET_DIR, "maz_data.csv")
MAZ_DENSITY_FILE = os.path.join(TARGET_DIR, "maz_data_withDensity.csv")
COORD_FILE = r"C:\GitHub\tm2py-utils\tm2py_utils\inputs\maz_taz\mazs_tazs_county_tract_PUMA_2.5.csv"
OUTPUT_MAZ_DATA = os.path.join(TARGET_DIR, "maz_data_UPDATED.csv")
OUTPUT_MAZ_DENSITY = os.path.join(TARGET_DIR, "maz_data_withDensity_UPDATED.csv")

# Columns to update from jobs file (customize as needed)
JOBS_MAZ_COL = "maz"
MAZ_DATA_MAZ_COL = "MAZ_ORIGINAL"
MAZ_DENSITY_MAZ_COL = "MAZ"

def load_csv(path):
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def merge_and_update():
    # ...existing code...
    # Print column summary
    
    # Load data
    jobs = load_csv(JOBS_FILE)
    maz_data = load_csv(MAZ_DATA_FILE)
    maz_density = load_csv(MAZ_DENSITY_FILE)
    coords = load_csv(COORD_FILE)

    print_column_summary(jobs, maz_data, maz_density)

    if jobs is None or maz_data is None or maz_density is None:
        print("\nOne or more input files could not be loaded. Exiting script.")
        return
        
    if coords is None:
        print("\nWarning: Coordinate file could not be loaded. Proceeding without coordinates.")
    else:
        print(f"\nLoaded coordinate data: {len(coords)} rows")
        print(f"Coordinate file columns: {sorted(coords.columns)}")

    # Identify job columns to merge (all except maz)
    job_cols = [col for col in jobs.columns if col != JOBS_MAZ_COL]

    # Print column summary
    print_column_summary(jobs, maz_data, maz_density)

    # --- Update maz_data.csv ---
    maz_data_merged = pd.merge(
        maz_data,
        jobs,
        left_on=MAZ_DATA_MAZ_COL,
        right_on=JOBS_MAZ_COL,
        how="right"  # include all jobs MAZs
    )
    # Zero out columns from maz_data that are NaN due to new MAZs
    for col in maz_data.columns:
        if col != MAZ_DATA_MAZ_COL and col in maz_data_merged.columns:
            maz_data_merged[col] = maz_data_merged[col].fillna(0)


    # Keep jobs columns in case of conflict: drop _x, rename _y to original
    cols_to_drop = [col for col in maz_data_merged.columns if col.endswith('_x') and col[:-2] + '_y' in maz_data_merged.columns]
    maz_data_merged = maz_data_merged.drop(columns=cols_to_drop)
    maz_data_merged.columns = [col[:-2] if col.endswith('_y') else col for col in maz_data_merged.columns]

    # --- Add coordinates to maz_data if missing ---
    coord_cols = [col for col in maz_data_merged.columns if any(spatial in col.upper() for spatial in ['_X', '_Y'])]
    if not coord_cols and coords is not None:
        print("\nAdding coordinates to maz_data...")
        # Prepare coordinate subset (MAZ in coord file = MAZ_ORIGINAL in maz_data)
        coord_subset = coords[['MAZ', 'MAZ_X', 'MAZ_Y']].rename(columns={'MAZ': 'MAZ_ORIGINAL'})
        coord_subset = coord_subset.drop_duplicates()
        
        # Merge coordinates
        maz_data_merged = pd.merge(
            maz_data_merged,
            coord_subset,
            on='MAZ_ORIGINAL',
            how='left'
        )
        
        # Fill missing coordinates with -1
        maz_data_merged['MAZ_X'] = maz_data_merged['MAZ_X'].fillna(-1)
        maz_data_merged['MAZ_Y'] = maz_data_merged['MAZ_Y'].fillna(-1)
        
        # Check success
        missing_coords = (maz_data_merged[['MAZ_X', 'MAZ_Y']] == -1).any(axis=1).sum()
        if missing_coords == 0:
            print(f"✅ Successfully added coordinates to maz_data")
        else:
            print(f"✅ Added coordinates to maz_data ({missing_coords} MAZs marked with -1 for missing coords)")

    # Recalculate emp_total to match sum of employment subcategories
    emp_subcategories = ['ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
                        'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
                        'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_soc', 'transp', 'util']
    
    # Check which employment columns are actually present
    available_emp_cols = [col for col in emp_subcategories if col in maz_data_merged.columns]
    if available_emp_cols:
        old_total = maz_data_merged['emp_total'].sum()
        maz_data_merged['emp_total'] = maz_data_merged[available_emp_cols].sum(axis=1)
        new_total = maz_data_merged['emp_total'].sum()
        print(f"✅ Recalculated emp_total for maz_data: {old_total:,.0f} -> {new_total:,.0f} ({len(available_emp_cols)} categories)")
    else:
        print("⚠️ No employment subcategories found for emp_total recalculation in maz_data")

    # Save updated file
    maz_data_merged.to_csv(OUTPUT_MAZ_DATA, index=False)

    # --- Update maz_data_withDensity.csv ---
    print("\nmaz_density columns before merge:", list(maz_density.columns))
    print("jobs columns before merge:", list(jobs.columns))
        # Use MAZ_ORIGINAL as the join column for maz_data_withDensity and maz for jobs
    if 'MAZ_ORIGINAL' not in maz_density.columns:
        raise KeyError("No MAZ_ORIGINAL column found in maz_data_withDensity for merging.")
    maz_density_merged = pd.merge(
        maz_density,
        jobs,
        left_on='MAZ_ORIGINAL',
        right_on=JOBS_MAZ_COL,
        how="left"  # preserve maz_density structure including MAZ_ORIGINAL
    )
    for col in maz_density.columns:
        if col != 'MAZ_ORIGINAL' and col in maz_density_merged.columns:
            maz_density_merged[col] = maz_density_merged[col].fillna(0)



    # --- Ensure only a single MAZ column is carried forward ---
    # Print columns after merge to debug
    print(f"Columns after merge: {list(maz_density_merged.columns)}")
    print(f"MAZ_ORIGINAL in merged data: {'MAZ_ORIGINAL' in maz_density_merged.columns}")
    
    # Acceptable variants: 'MAZ', 'MAZ_x', 'MAZ_y', 'maz' (but NOT MAZ_ORIGINAL!)
    maz_variants = [col for col in maz_density_merged.columns if (col.lower() == 'maz' or col.lower().startswith('maz_')) and col != 'MAZ_ORIGINAL']
    # Prefer 'MAZ', then 'MAZ_x', then 'maz', then 'MAZ_y'
    keep_maz = None
    for candidate in ['MAZ', 'MAZ_x', 'maz', 'MAZ_y']:
        if candidate in maz_density_merged.columns:
            keep_maz = candidate
            break
    if keep_maz:
        maz_density_merged = maz_density_merged.rename(columns={keep_maz: 'MAZ'})
    # Drop all other MAZ variants (but keep MAZ_ORIGINAL)
    drop_maz = [col for col in maz_variants if col != keep_maz and col != 'MAZ' and col != 'MAZ_ORIGINAL']
    if drop_maz:
        maz_density_merged = maz_density_merged.drop(columns=drop_maz)
        print(f"Dropped MAZ variants: {drop_maz}")

    # Keep jobs columns in case of conflict: drop _x (old density data), rename _y (new jobs data) to original
    print(f"Before employment column cleanup: {len(maz_density_merged.columns)} columns")
    
    # Find all _x/_y pairs
    x_cols = [col for col in maz_density_merged.columns if col.endswith('_x')]
    y_cols = [col for col in maz_density_merged.columns if col.endswith('_y')]
    
    print(f"_x columns (old density data to drop): {x_cols}")
    print(f"_y columns (new jobs data to keep): {y_cols}")
    
    # Drop _x columns where there's a corresponding _y column (except coordinate columns)
    cols_to_drop = []
    for x_col in x_cols:
        base_name = x_col[:-2]  # Remove '_x'
        y_col = base_name + '_y'
        # Only drop if there's a corresponding _y column and it's not a coordinate column
        if y_col in maz_density_merged.columns and not any(spatial in x_col.upper() for spatial in ['MAZ_X', 'MAZ_Y']):
            cols_to_drop.append(x_col)
    
    if cols_to_drop:
        maz_density_merged = maz_density_merged.drop(columns=cols_to_drop)
        print(f"Dropped old density columns: {cols_to_drop}")
    
    # Rename _y columns to original names (new jobs data becomes the main data)
    rename_cols = {}
    for col in maz_density_merged.columns:
        if col.endswith('_y') and not any(spatial in col.upper() for spatial in ['MAZ_X', 'MAZ_Y']):
            original_name = col[:-2]  # Remove '_y'
            rename_cols[col] = original_name
    
    if rename_cols:
        maz_density_merged = maz_density_merged.rename(columns=rename_cols)
        print(f"Renamed jobs columns: {list(rename_cols.values())}")
    
    print(f"After employment column cleanup: {len(maz_density_merged.columns)} columns")

    # Recalculate emp_total to match sum of employment subcategories
    emp_subcategories = ['ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
                        'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
                        'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_soc', 'transp', 'util']
    
    # Check which employment columns are actually present
    available_emp_cols = [col for col in emp_subcategories if col in maz_density_merged.columns]
    if available_emp_cols:
        old_total = maz_density_merged['emp_total'].sum()
        maz_density_merged['emp_total'] = maz_density_merged[available_emp_cols].sum(axis=1)
        new_total = maz_density_merged['emp_total'].sum()
        print(f"✅ Recalculated emp_total for maz_density: {old_total:,.0f} -> {new_total:,.0f} ({len(available_emp_cols)} categories)")
    else:
        print("⚠️ No employment subcategories found for emp_total recalculation in maz_density")



    # --- Overwrite EmpDen, RetEmpDen, PopDen columns with new calculations ---
    sq_mi_acre = 1 / 640  # 1 acre = 1/640 square miles
    if "emp_total" in maz_density_merged.columns and "ACRES" in maz_density_merged.columns:
        maz_density_merged["EmpDen"] = maz_density_merged["emp_total"] / maz_density_merged["ACRES"].replace(0, pd.NA)
    if "ret_loc" in maz_density_merged.columns and "ret_reg" in maz_density_merged.columns and "ACRES" in maz_density_merged.columns:
        maz_density_merged["RetEmpDen"] = (maz_density_merged["ret_loc"] + maz_density_merged["ret_reg"]) / maz_density_merged["ACRES"].replace(0, pd.NA)
    if "POP" in maz_density_merged.columns and "ACRES" in maz_density_merged.columns:
        maz_density_merged["PopDen"] = maz_density_merged["POP"] / maz_density_merged["ACRES"].replace(0, pd.NA)
    # Calculate PopEmpDenPerMi = (POP+emp_total)/(10*ACRES*sq_mi_acre)
    if all(col in maz_density_merged.columns for col in ["POP", "emp_total", "ACRES"]):
        maz_density_merged["PopEmpDenPerMi"] = (maz_density_merged["POP"] + maz_density_merged["emp_total"]) / maz_density_merged["ACRES"].replace(0, pd.NA)

    # Define empdenbin: [0-10)=1, [10-30)=2, 30+=3
    if "EmpDen" in maz_density_merged.columns:
        bins = [0, 10, 30, float('inf')]
        labels = [1, 2, 3]
        empden_numeric = pd.to_numeric(maz_density_merged["EmpDen"], errors="coerce")
    maz_density_merged["EmpDenBin"] = pd.cut(empden_numeric, bins=bins, labels=labels, right=False)
    maz_density_merged["EmpDenBin"] = maz_density_merged["EmpDenBin"].fillna(1)



    # Calculate DUDen as HH / ACRES
    if "HH" in maz_density_merged.columns and "ACRES" in maz_density_merged.columns:
        maz_density_merged["DUDen"] = maz_density_merged["HH"] / maz_density_merged["ACRES"].replace(0, pd.NA)

    # Define DuDenBin: [0-5)=1, [5-10)=2, 10+=3
    if "DUDen" in maz_density_merged.columns:
        du_bins = [0, 5, 10, float('inf')]
        du_labels = [1, 2, 3]
        duden_numeric = pd.to_numeric(maz_density_merged["DUDen"], errors="coerce")
        maz_density_merged["DuDenBin"] = pd.cut(duden_numeric, bins=du_bins, labels=du_labels, right=False)
        maz_density_merged["DuDenBin"] = maz_density_merged["DuDenBin"].fillna(1)

    # --- Add coordinate data and clean up columns ---
    if coords is not None:
        print("\nMerging coordinate data...")
        # Identify coordinate columns (MAZ_X, MAZ_Y, etc.)
        coord_cols = [col for col in coords.columns if any(spatial in col.upper() for spatial in ['_X', '_Y', 'LONGITUDE', 'LATITUDE'])]
        
        print(f"Available coordinate columns: {coord_cols}")
        print(f"Coordinate file has columns: {list(coords.columns)}")
        
        # The coordinate file has 'MAZ' which corresponds to 'MAZ_ORIGINAL' in our density file
        if 'MAZ' in coords.columns and 'MAZ_ORIGINAL' in maz_density_merged.columns:
            # Prepare coordinate subset with MAZ + coordinate columns
            coord_cols_to_merge = ['MAZ'] + coord_cols
            coords_subset = coords[coord_cols_to_merge].drop_duplicates()
            
            # Rename MAZ to MAZ_ORIGINAL for the merge
            coords_subset = coords_subset.rename(columns={'MAZ': 'MAZ_ORIGINAL'})
            
            # Merge coordinates
            maz_density_merged = pd.merge(
                maz_density_merged,
                coords_subset,
                on='MAZ_ORIGINAL',
                how='left'
            )
            
            # Fill missing coordinates with -1
            for coord_col in coord_cols:
                if coord_col in maz_density_merged.columns:
                    maz_density_merged[coord_col] = maz_density_merged[coord_col].fillna(-1)
            
            missing_coords = (maz_density_merged[coord_cols] == -1).any(axis=1).sum()
            if missing_coords == 0:
                print(f"✅ Successfully merged {len(coord_cols)} coordinate columns")
            else:
                print(f"✅ Successfully merged {len(coord_cols)} coordinate columns ({missing_coords} MAZs marked with -1 for missing coords)")
        else:
            print(f"Warning: Cannot merge coordinates")
            print(f"  - Coordinate file has MAZ: {'MAZ' in coords.columns}")
            print(f"  - Density file has MAZ_ORIGINAL: {'MAZ_ORIGINAL' in maz_density_merged.columns}")
    
    # --- Clean up duplicate MAZ/TAZ columns ---
    print("\nCleaning up duplicate columns...")
    
    # Remove unwanted index columns first
    unwanted_cols = [col for col in maz_density_merged.columns if col.startswith('Unnamed:')]
    if unwanted_cols:
        maz_density_merged = maz_density_merged.drop(columns=unwanted_cols)
        print(f"Dropped unwanted index columns: {unwanted_cols}")
    
    # Ensure we have the core columns: MAZ, TAZ, MAZ_ORIGINAL, TAZ_ORIGINAL
    required_cols = ['MAZ', 'TAZ']
    optional_cols = ['MAZ_ORIGINAL', 'TAZ_ORIGINAL']
    
    # Handle MAZ variants - keep sequential MAZ as 'MAZ'
    maz_variants = [col for col in maz_density_merged.columns if col.upper() in ['MAZ', 'MAZ_X', 'MAZ_Y'] and not any(spatial in col.upper() for spatial in ['_X', '_Y'])]
    if 'MAZ' not in maz_variants and len(maz_variants) > 0:
        # Rename first available MAZ variant to MAZ
        maz_density_merged = maz_density_merged.rename(columns={maz_variants[0]: 'MAZ'})
        maz_variants[0] = 'MAZ'
    
    # Handle TAZ variants - keep sequential TAZ as 'TAZ'  
    taz_variants = [col for col in maz_density_merged.columns if col.upper() in ['TAZ', 'TAZ_X', 'TAZ_Y'] and not any(spatial in col.upper() for spatial in ['_X', '_Y'])]
    if 'TAZ' not in taz_variants and len(taz_variants) > 0:
        # Rename first available TAZ variant to TAZ
        maz_density_merged = maz_density_merged.rename(columns={taz_variants[0]: 'TAZ'})
        taz_variants[0] = 'TAZ'
    
    # Drop remaining duplicates (keep MAZ, TAZ, MAZ_ORIGINAL, TAZ_ORIGINAL + spatial)
    cols_to_drop = []
    for col in maz_density_merged.columns:
        if col in ['maz', 'taz'] and col.upper() in [c.upper() for c in maz_density_merged.columns]:
            # Drop lowercase if uppercase exists
            if col.upper() in maz_density_merged.columns:
                cols_to_drop.append(col)
        elif col.endswith('_x') and not any(spatial in col.upper() for spatial in ['_X', '_Y']):
            # Drop merge artifacts like MAZ_x, TAZ_x (but preserve coordinate columns like MAZ_X, MAZ_Y)
            cols_to_drop.append(col)
    
    if cols_to_drop:
        maz_density_merged = maz_density_merged.drop(columns=cols_to_drop)
        print(f"Dropped duplicate columns: {cols_to_drop}")
    
    # Verify we have core columns
    missing_core = [col for col in required_cols if col not in maz_density_merged.columns]
    present_optional = [col for col in optional_cols if col in maz_density_merged.columns]
    
    if missing_core:
        print(f"Warning: Missing core columns: {missing_core}")
    else:
        print(f"✅ All core columns present: {required_cols}")
    
    if present_optional:
        print(f"✅ Optional columns present: {present_optional}")
    
    # Check for coordinate columns
    spatial_cols = [col for col in maz_density_merged.columns if any(spatial in col.upper() for spatial in ['_X', '_Y'])]
    if spatial_cols:
        print(f"✅ Coordinate columns present: {spatial_cols}")
    else:
        print("⚠️ No coordinate columns found")
    
    print(f"Final column count: {len(maz_density_merged.columns)}")
    print(f"Final columns: {sorted(maz_density_merged.columns)}")

    # Save updated file
    maz_density_merged.to_csv(OUTPUT_MAZ_DENSITY, index=False)
    print('TO DO: Figure out what IntDenBin is, and update.')

def rename_final_files():
    """Rename files to final naming convention"""
    import os
    
    # Use the same TARGET_DIR as the rest of the script
    box_dir = TARGET_DIR
    
    # Define file mappings: current_name -> new_name
    file_renames = {
        'maz_data.csv': 'maz_data_old.csv',
        'maz_data_withDensity.csv': 'maz_data_withDensity_old.csv',
        'maz_data_UPDATED.csv': 'maz_data.csv',
        'maz_data_withDensity_UPDATED.csv': 'maz_data_withDensity.csv'
    }
    
    print("\n--- FINAL FILE RENAMING ---")
    for old_name, new_name in file_renames.items():
        old_path = os.path.join(box_dir, old_name)
        new_path = os.path.join(box_dir, new_name)
        
        if os.path.exists(old_path):
            try:
                # If target exists, remove it first (for _old files, this overwrites any previous _old version)
                if os.path.exists(new_path):
                    os.remove(new_path)
                    print(f"Removed existing: {new_name}")
                
                os.rename(old_path, new_path)
                print(f"✅ Renamed: {old_name} -> {new_name}")
            except Exception as e:
                print(f"❌ Error renaming {old_name}: {e}")
        else:
            print(f"⚠️ File not found: {old_name}")
    
    print("Final files:")
    print("- maz_data.csv (current version)")
    print("- maz_data_withDensity.csv (current version)")
    print("- maz_data_old.csv (previous version)")
    print("- maz_data_withDensity_old.csv (previous version)")

def copy_files_to_box():
    """Copy final files to Box destination for TM2 model"""
    import shutil
    from pathlib import Path
    
    print("\n--- COPYING FILES TO BOX ---")
    
    # Source: where our script saves the files
    source_dir = Path(TARGET_DIR)
    
    # Destination: Box location for TM2 model (same as source in this case, but keeping for clarity)
    dest_dir = Path(r'C:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse')
    
    # Files to copy
    files_to_copy = [
        'maz_data.csv',
        'maz_data_withDensity.csv'
    ]
    
    # Ensure destination directory exists
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    for fname in files_to_copy:
        src = source_dir / fname
        dst = dest_dir / fname
        
        if src.exists():
            try:
                shutil.copy2(src, dst)
                print(f"✅ Copied: {fname} -> {dest_dir}")
            except Exception as e:
                print(f"❌ Error copying {fname}: {e}")
        else:
            print(f"⚠️ Source file not found: {src}")
    
    print("Box sync complete!")

if __name__ == "__main__":
    merge_and_update()
    rename_final_files()
