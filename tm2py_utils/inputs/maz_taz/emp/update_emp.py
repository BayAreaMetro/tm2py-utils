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
TARGET_DIR = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse"
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
    maz_density_merged = pd.merge(
        maz_density,
        jobs,
        left_on=MAZ_DENSITY_MAZ_COL,
        right_on=JOBS_MAZ_COL,
        how="right"  # include all jobs MAZs
    )
    for col in maz_density.columns:
        if col != MAZ_DENSITY_MAZ_COL and col in maz_density_merged.columns:
            maz_density_merged[col] = maz_density_merged[col].fillna(0)


    # Keep jobs columns in case of conflict: drop _x, rename _y to original
    cols_to_drop = [col for col in maz_density_merged.columns if col.endswith('_x') and col[:-2] + '_y' in maz_density_merged.columns]
    maz_density_merged = maz_density_merged.drop(columns=cols_to_drop)
    maz_density_merged.columns = [col[:-2] if col.endswith('_y') else col for col in maz_density_merged.columns]

    # Save updated file
    maz_density_merged.to_csv(OUTPUT_MAZ_DENSITY, index=False)

    # --- Reminder for density columns ---
    print("\nTODO: Implement logic to recalculate density columns: EmpDen, RetEmpDen, EmpDenBin, DuDenBin, PopEmpDen, etc.")

if __name__ == "__main__":
    merge_and_update()
