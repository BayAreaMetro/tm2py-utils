
from naics_xwalk import create_naics_xwalk
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import unittest


FIRMS_DIR = Path(r"M:/Data/BusinessData")
ANALYSIS_CRS = "EPSG:26910"
MAZ_TAZ_DIR = Path(__file__).parent.parent / "maz_taz" / "shapefiles"


def load_firms_gdf():
    """
    Loads firm data and preps for merging with NAICS steelhead xwalk and MAZ.  Currently hardcoded 
    to 2023 Esri Business Analyst dataset but the datasource will likely change to LEHD/QCEW.  

    Returns:
        GeoDataFrame: Contains business firm data with the extracted 'naicssix' column for the 
        6-digit NAICS codes, projected to the analysis CRS.

    """
    print(f"Loading business data...")
    gdb = os.path.join(FIRMS_DIR, "Businesses_2023.gdb")
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


def load_maz_shp():
    """
    Load MAZ shapefile.  Currently hard coded to version2_4.
    
    Returns:
        gpd.GeoDataFrame: MAZ polygons with MAZ/TAZ ids
    """
    print(f"Loading maz shapefile...")
    maz_shp = os.path.join(MAZ_TAZ_DIR, "mazs_TM2_2_4.shp")
    maz = gpd.read_file(maz_shp).to_crs(ANALYSIS_CRS)
    maz = maz[["maz", "taz", "geometry"]]

    return maz


def spatil_join_firms_to_maz(firms, maz):
    """
    Spatially joins firm to MAZ polygons.  Performed in two steps:
    1. Attempts to join each firm to a MAZ using the 'within' predicate (i.e., firms located inside a MAZ).
    2. For firms not matched in the first step, assigns them to the nearest MAZ using a nearest neighbor spatial join.
    Parameters:
        firms (GeoDataFrame): Firm locations.
        maz (GeoDataFrame): MAZ polygons.
    Returns:
        DataFrame: A DataFrame of firms with MAZ assignments.
    """

    # Spatial join 1 - within predicate
    print(f"Number of business records before spatial join to maz: {len(firms)}")
    firms = gpd.sjoin(firms, maz, how="left", predicate="within")
    firms = firms.drop(columns=['index_right'])
    print(f"Number of business records after spatial join to maz: {len(firms)}")
    print(f"Number of firms successfully joined to a MAZ:", firms["maz"].notnull().sum())

    # Spatial join 2 - nearest for any leftovers
    firms_missed = firms[firms["maz"].isnull()]
    if len(firms_missed) > 0:

        print(f"Number of firms unsuccessfully joined to a MAZ: {len(firms_missed)}")

        # Ensure the missed subset is still a gdf; drop any null MAZ/TAZ columns left over from the first attempt
        firms_missed = gpd.GeoDataFrame(firms_missed, geometry="geometry", crs=ANALYSIS_CRS).drop(columns=["maz", "taz"])
        
        print(f"Joining unmatched firms to nearest MAZ...")
        firms_nearest = gpd.sjoin_nearest(firms_missed, maz, how="left")
        print(f"Number of unmatched firms after nearest join operation:", firms_nearest["maz"].isnull().sum())
        firms_nearest = pd.DataFrame(firms_nearest)

        # Filter firms that successfully joined to maz in first step and concatenate results
        firms = pd.DataFrame(firms[firms["maz"].notnull()])
        firms = pd.concat([firms, firms_nearest])
        print(f"Total number firms now joined to a maz: ", firms["maz"].notnull().sum())

    return firms

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
    firms_maz = firms_maz[["maz", "taz", "steelhead", "EMPNUM"]]
    print(f"Total jobs by steelhead category: ", firms_maz.groupby(["steelhead"], as_index=False)["EMPNUM"].sum())
    jobs_maz = firms_maz.groupby(["maz", "taz", "steelhead"], as_index=False)["EMPNUM"].sum()
   
    # Spread the steelhead column
    jobs_maz = jobs_maz.pivot(index=["maz", "taz"], columns="steelhead", values="EMPNUM").reset_index()

    # Concatenate maz with jobs and maz w/o jobs so we have a full set of maz
    maz_no_firms = maz[~maz["maz"].isin(firms_maz["maz"])].drop(columns="geometry")
    jobs_maz = pd.concat([jobs_maz, maz_no_firms]).reset_index(drop=True)

    # Final formatting
    jobs_maz["maz"] = jobs_maz["maz"].astype(str)
    jobs_maz["taz"] = jobs_maz["taz"].astype(str)
    jobs_maz = jobs_maz.fillna(0)

    # Create total jobs column
    jobs_maz["emp_total"] = jobs_maz.sum(axis=1, numeric_only=True)
    print(f"Total jobs in region from 2023 Esri Business Analyst dataset: ", jobs_maz["emp_total"].sum())
    print(f"Total unique MAZ ids in unprocessed MAZ data: ", len(maz["maz"].unique()))
    print(f"Total unique MAZ ids in processed MAZ data: ", len(jobs_maz["maz"].unique()))

    return jobs_maz


def get_jobs_maz():
    """
    Loads data, performs spatial joins, and summarizes jobs.
    Returns:
        DataFrame: jobs_maz with job counts by MAZ and steelhead categories.
    """
    naics_xwalk = create_naics_xwalk()
    firms = load_firms_gdf().merge(naics_xwalk, how="left", on="naicssix")
    maz = load_maz_shp()
    firms_maz = spatil_join_firms_to_maz(firms, maz)
    jobs_maz = summarize_jobs_by_maz(firms_maz, maz)
    return jobs_maz

def main():
    """
    An option to execute the script directly.  Not sure yet how this will fit into the pipeline.
    """
    jobs_maz = get_jobs_maz()

if __name__ == "__main__":
    main()