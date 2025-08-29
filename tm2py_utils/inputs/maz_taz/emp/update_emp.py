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

import os
import pandas as pd

# Paths to files
TARGET_DIR = r"C:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse"
JOBS_FILE = os.path.join(TARGET_DIR, "jobs_maz_2023_v1.csv")
MAZ_DATA_FILE = os.path.join(TARGET_DIR, "maz_data.csv")
MAZ_DENSITY_FILE = os.path.join(TARGET_DIR, "maz_data_withDensity.csv")
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

    print_column_summary(jobs, maz_data, maz_density)

    if jobs is None or maz_data is None or maz_density is None:
        print("\nOne or more input files could not be loaded. Exiting script.")
        return

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
        how="right"  # include all jobs MAZs
    )
    for col in maz_density.columns:
        if col != 'MAZ_ORIGINAL' and col in maz_density_merged.columns:
            maz_density_merged[col] = maz_density_merged[col].fillna(0)



    # --- Ensure only a single MAZ column is carried forward ---
    # Acceptable variants: 'MAZ', 'MAZ_x', 'MAZ_y', 'maz'
    maz_variants = [col for col in maz_density_merged.columns if col.lower() == 'maz' or col.lower().startswith('maz_')]
    # Prefer 'MAZ', then 'MAZ_x', then 'maz', then 'MAZ_y'
    keep_maz = None
    for candidate in ['MAZ', 'MAZ_x', 'maz', 'MAZ_y']:
        if candidate in maz_density_merged.columns:
            keep_maz = candidate
            break
    if keep_maz:
        maz_density_merged = maz_density_merged.rename(columns={keep_maz: 'MAZ'})
    # Drop all other MAZ variants
    drop_maz = [col for col in maz_variants if col != keep_maz and col != 'MAZ']
    if drop_maz:
        maz_density_merged = maz_density_merged.drop(columns=drop_maz)

    # Keep jobs columns in case of conflict: drop _x, rename _y to original (except for MAZ)
    cols_to_drop = [col for col in maz_density_merged.columns if col.endswith('_x') and col[:-2] + '_y' in maz_density_merged.columns and col[:-2] != 'MAZ']
    maz_density_merged = maz_density_merged.drop(columns=cols_to_drop)
    maz_density_merged.columns = [col[:-2] if col.endswith('_y') and col[:-2] != 'MAZ' else col for col in maz_density_merged.columns]



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
        maz_density_merged["PopEmpDenPerMi"] = (maz_density_merged["POP"] + maz_density_merged["emp_total"]) / (10 * maz_density_merged["ACRES"] * sq_mi_acre)

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

    # Save updated file
    maz_density_merged.to_csv(OUTPUT_MAZ_DENSITY, index=False)
    print('TO DO: Figure out what IntDenBin is, and update.')



if __name__ == "__main__":
    merge_and_update()
