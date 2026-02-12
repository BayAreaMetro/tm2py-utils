
from naics_xwalk import create_naics_xwalk
from pathlib import Path
import os
import sys
import pandas as pd
import geopandas as gpd
import unittest

# Import configuration and utilities
from setup import (
    EMPLOYMENT_RAW_DATA_DIR,
    ANALYSIS_CRS,
    ensure_directories
)
from utils import load_maz_shp, spatial_join_to_maz, get_output_filename


def load_firms_gdf():
    """
    Loads firm data and preps for merging with NAICS steelhead xwalk and MAZ.  Currently hardcoded 
    to 2023 Esri Business Analyst dataset but the datasource will likely change to LEHD/QCEW.  

    Returns:
        GeoDataFrame: Contains business firm data with the extracted 'naicssix' column for the 
        6-digit NAICS codes, projected to the analysis CRS.

    """
    print(f"Loading business data...")
    gdb = os.path.join(EMPLOYMENT_RAW_DATA_DIR, "Businesses_2023.gdb")
    businesses = gpd.read_file(gdb, layer="Bay_Area_Businesses_2023").to_crs(ANALYSIS_CRS)
    
    # Extract 6-digit NAICS column
    businesses['naicssix'] = businesses['NAICS'].astype(str).str[:6]
    
    # Check for any null naicssix
    num_null = businesses['naicssix'].isnull().sum()
    if num_null > 0:
        print(f"Number of null values in firms naicssix: {num_null}")
    else:
        print(f"All businesses have a NAICS code.")

    return businesses


# Removed duplicate load_maz_shp() - now imported from utils
# Removed spatil_join_firms_to_maz() - replaced by utils.spatial_join_to_maz()

def summarize_jobs_by_maz(firms_maz, maz):
    """
    Summarizes job counts by MAZ and 27-way steelhead categories.  Brings back MAZ
    records without firms so that the full universe of MAZs is included in the output.
    
    Parameters:
        firms_maz (DataFrame): Firm-level data with MAZ assignment.
        maz (GeoDataFrame): MAZ polygons.
    Returns:
        jobs_maz (DataFrame): One row per MAZ with job count columns for each steelhead sector type.
    """
    print(f"Summarizing jobs by maz and steelhead categories...")
    # Reduce to needed columns and tally jobs
    firms_maz = firms_maz[["MAZ_NODE", "TAZ_NODE", "steelhead", "EMPNUM"]]
    print(f"Total jobs by steelhead category: ", firms_maz.groupby(["steelhead"], as_index=False)["EMPNUM"].sum())
    jobs_maz = firms_maz.groupby(["MAZ_NODE", "TAZ_NODE", "steelhead"], as_index=False)["EMPNUM"].sum()
   
    # Spread the steelhead column
    jobs_maz = jobs_maz.pivot(index=["MAZ_NODE", "TAZ_NODE"], columns="steelhead", values="EMPNUM").reset_index()

    # Concatenate maz with jobs and maz w/o jobs so we have a full set of maz
    maz_no_firms = maz[~maz["MAZ_NODE"].isin(firms_maz["MAZ_NODE"])].drop(columns="geometry")
    jobs_maz = pd.concat([jobs_maz, maz_no_firms]).reset_index(drop=True)

    # Remove trailing decimal and zero from ID cols
    jobs_maz["MAZ_NODE"] = jobs_maz["MAZ_NODE"].astype(str).str.replace(r"\.0$", "", regex=True)
    jobs_maz["TAZ_NODE"] = jobs_maz["TAZ_NODE"].astype(str).str.replace(r"\.0$", "", regex=True)
    jobs_maz = jobs_maz.fillna(0)

    # Create total jobs column
    jobs_maz["emp_total"] = jobs_maz.sum(axis=1, numeric_only=True)
    print(f"Total jobs in region from 2023 Esri Business Analyst dataset: ", jobs_maz["emp_total"].sum())
    print(f"Total unique MAZ ids in unprocessed MAZ data: ", len(maz["MAZ_NODE"].unique()))
    print(f"Total unique MAZ ids in processed MAZ data: ", len(jobs_maz["MAZ_NODE"].unique()))

    return jobs_maz


def get_jobs_maz(write=False):
    """
    Loads data, performs spatial joins, and summarizes jobs.
    Parameters:
        write (bool, optional): If True, writes the resulting jobs_maz GeoDataFrame to interim cache.
    Returns:
        DataFrame: jobs_maz with job counts by MAZ and steelhead categories.
    """
    ensure_directories()
    
    naics_xwalk = create_naics_xwalk()
    firms = load_firms_gdf().merge(naics_xwalk, how="left", on="naicssix")
    maz = load_maz_shp()
    firms_maz = spatial_join_to_maz(firms, maz)
    jobs_maz = summarize_jobs_by_maz(firms_maz, maz)
    
    if write:
        # Merge with MAZ geometry for spatial output
        # Ensure MAZ_NODE is string for merge (jobs_maz already has string MAZ_NODE from summarize step)
        maz_geom = maz[["MAZ_NODE", "geometry"]].copy()
        maz_geom["MAZ_NODE"] = maz_geom["MAZ_NODE"].astype(str)
        jobs_maz_spatial = jobs_maz.merge(
            maz_geom, 
            on="MAZ_NODE", 
            how="left"
        )
        jobs_maz_spatial = gpd.GeoDataFrame(jobs_maz_spatial, geometry="geometry", crs=ANALYSIS_CRS)
        
        OUT_FILE = get_output_filename("jobs_maz", extension="gpkg", spatial=True)
        print(f"Writing employment MAZ data to: {OUT_FILE}")
        jobs_maz_spatial.to_file(OUT_FILE, driver="GPKG")
    
    return jobs_maz

def main():
    """
    Execute script directly with optional command-line flags.
    Usage:
        python job_counts.py [--write]
    """
    write = "--write" in sys.argv
    
    jobs_maz = get_jobs_maz(write=write)
    print(f"\nJob counts processing complete.")
    print(f"Total MAZ records: {len(jobs_maz)}")
    print(f"Total employment: {jobs_maz['emp_total'].sum():,.0f}")

if __name__ == "__main__":
    main()