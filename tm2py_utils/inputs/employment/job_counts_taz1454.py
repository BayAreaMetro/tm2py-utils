
from naics_xwalk import create_naics_xwalk
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd
import unittest

"""
For comparing tm2/tm1 employment inputs only.  Similar to job_counts.py but we load and join to TM1 TAZ 
instead of TM2 taz because there's isn't a clean correspondence between the two.  Generates TAZ1-level
jobs counts by TM2 sector categories using 2023 Esri Business Analyst.
"""

FIRMS_DIR = Path(r"M:/Data/BusinessData")
ANALYSIS_CRS = "EPSG:26910"
# taz_TAZ_DIR = Path(__file__).parent.parent / "taz_taz" / "shapefiles"
TAZ_SHP = Path(r"E:\Box\Modeling and Surveys\Urban Modeling\Spatial\Zones\TAZ1454\zones1454.shp")


def load_firms_gdf():
    """
    Loads firm data and extract naics six digit precision.  Currently hardcoded 
    to 2023 Esri Business Analyst dataset but the datasource but might change to LEHD/QCEW.  

    Returns:
        GeoDataFrame: Contains business firm data with extracted 'naicssix' column.

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


def load_taz_shp():
    """
    Load taz shapefile from TM1.
    
    Returns:
        gpd.GeoDataFrame: 1454 taz polygons with TAZ ids
    """
    print(f"Loading taz shapefile...")
    # taz_shp = os.path.join(taz_TAZ_DIR, "tazs_TM2_2_4.shp")
    taz = gpd.read_file(TAZ_SHP).to_crs(ANALYSIS_CRS)
    taz = taz[["zone_id", "geometry"]]
    taz = taz.rename(columns={"zone_id": "taz"})

    return taz


def spatil_join_firms_to_taz(firms, taz):
    """
    Spatially joins firm to taz polygons.  Performed in two steps:
    1. Attempts to join each firm to a taz using the 'within' predicate (i.e., firms located inside a taz).
    2. For firms not matched in the first step, assigns them to the nearest taz using a nearest neighbor spatial join.
    Parameters:
        firms (GeoDataFrame): Firm locations.
        taz (GeoDataFrame): taz polygons.
    Returns:
        DataFrame: A DataFrame of firms with taz assignments.
    """

    # Spatial join 1 - within predicate
    print(f"Number of business records before spatial join to taz: {len(firms)}")
    firms = gpd.sjoin(firms, taz, how="left", predicate="within")
    firms = firms.drop(columns=['index_right'])
    print(f"Number of business records after spatial join to taz: {len(firms)}")
    print(f"Number of firms successfully joined to a taz:", firms["taz"].notnull().sum())

    # Spatial join 2 - nearest for any leftovers
    firms_missed = firms[firms["taz"].isnull()]
    if len(firms_missed) > 0:

        print(f"Number of firms unsuccessfully joined to a taz: {len(firms_missed)}")

        # Ensure the missed subset is still a gdf; drop any null taz columns left over from the first attempt
        firms_missed = gpd.GeoDataFrame(firms_missed, geometry="geometry", crs=ANALYSIS_CRS).drop(columns=["taz"])
        
        print(f"Joining unmatched firms to nearest taz...")
        firms_nearest = gpd.sjoin_nearest(firms_missed, taz, how="left")
        print(f"Number of unmatched firms after nearest join operation:", firms_nearest["taz"].isnull().sum())
        firms_nearest = pd.DataFrame(firms_nearest)

        # Filter firms that successfully joined to taz in first step and concatenate results
        firms = pd.DataFrame(firms[firms["taz"].notnull()])
        firms = pd.concat([firms, firms_nearest])
        print(f"Total number firms now joined to a taz: ", firms["taz"].notnull().sum())

    return firms

def summarize_jobs_by_taz(firms_taz, taz):
    """
    Summarizes job counts by taz and 6-way employment categories to facilitate comparison with TM1 employment inpute.  
    Brings back taz records without firms so that the full universe of tazs is included in the output.
    
    Parameters:
        firms_taz (DataFrame): Firm-level data with taz assignment.
        taz (GeoDataFrame): taz polygons.
    Returns:
        jobs_taz (DataFrame): One row per taz with job count columns for each employment category.
    """
    print(f"Summarizing jobs by taz and steelhead categories...")
    # Reduce to needed columns and tally jobs
    firms_taz = firms_taz[["taz", "steelhead", "EMPNUM"]]
    print(f"Total jobs by steelhead category: ", firms_taz.groupby(["steelhead"], as_index=False)["EMPNUM"].sum())
    jobs_taz = firms_taz.groupby(["taz", "steelhead"], as_index=False)["EMPNUM"].sum()
   
    # Spread the steelhead column
    jobs_taz = jobs_taz.pivot(index=["taz"], columns="steelhead", values="EMPNUM").reset_index()

    # Concatenate taz with jobs and taz w/o jobs so we have a full set of taz
    taz_no_firms = taz[~taz["taz"].isin(firms_taz["taz"])].drop(columns="geometry")
    jobs_taz = pd.concat([jobs_taz, taz_no_firms]).reset_index(drop=True)

    # Remove trailing decimal and zero from ID cols
    # jobs_taz["taz"] = jobs_taz["taz"].astype(str).str.replace(r"\.0$", "", regex=True)
    # jobs_taz["taz"] = jobs_taz["taz"].astype(str).str.replace(r"\.0$", "", regex=True)
    jobs_taz["taz"] = jobs_taz["taz"].astype(str)
    jobs_taz["taz"] = jobs_taz["taz"].astype(str)
    jobs_taz = jobs_taz.fillna(0)

    # Create total jobs column
    jobs_taz["emp_total"] = jobs_taz.sum(axis=1, numeric_only=True)
    print(f"Total jobs in region from 2023 Esri Business Analyst dataset: ", jobs_taz["emp_total"].sum())
    print(f"Total unique taz ids in unprocessed taz data: ", len(taz["taz"].unique()))
    print(f"Total unique taz ids in processed taz data: ", len(jobs_taz["taz"].unique()))

    return jobs_taz


def get_jobs_taz(write=False):
    """
    Loads data, performs spatial joins, and summarizes jobs.
    Parameters:
        write (bool, optional): If True, writes the resulting jobs_taz DataFrame to a CSV file.
    Returns:
        DataFrame: jobs_taz with job counts by taz and steelhead categories.
    """
    naics_xwalk = create_naics_xwalk()
    firms = load_firms_gdf().merge(naics_xwalk, how="left", on="naicssix")
    taz = load_taz_shp()
    firms_taz = spatil_join_firms_to_taz(firms, taz)
    jobs_taz = summarize_jobs_by_taz(firms_taz, taz)
    if write==True:
        OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\jobs_taz1454_2023.csv"
        jobs_taz.to_csv(OUT_FILE)        
    return jobs_taz

def main():
    """
    An option to execute the script directly.  Not sure yet how this will fit into the pipeline.
    """
    jobs_taz = get_jobs_taz()

if __name__ == "__main__":
    main()