#%%
import pytidycensus
import pandas as pd
import geopandas as gpd
from pathlib import Path

# Import job_counts module to get MAZ employment data
from job_counts import get_jobs_maz

# Import utils module directly to avoid loading full package
utils_path = Path(__file__).parent / "utils.py"
import importlib.util
spec = importlib.util.spec_from_file_location("utils", utils_path)
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)

ANALYSIS_CRS = "EPSG:26910"
WGS84_CRS = "EPSG:4326"
OUTPUT_DIR = Path(__file__).parent / "outputs"
SQUARE_METERS_PER_ACRE = 4046.86

#%%

def load_bay_area_places():
    # Set Census API key
    pytidycensus.set_census_api_key("a3928abdddafbb9bbd88399816c55c82337c3ca6")

    # Load census place geographies for California
    places = pytidycensus.get_acs(
        geography="place",
        variables=["B01001_001E"],  # Total population
        state="CA",
        year=2021,
        geometry=True
    ) 

    counties = pytidycensus.get_acs(
        geography="county",
        variables=["B01001_001E"],  # Total population
        state="CA",
        year=2021,
        geometry=True
    ) 

    COUNTY_FIPS = {
        "Alameda": "001",
        "Contra Costa": "013",
        "Marin": "041",
        "Napa": "055",
        "San Francisco": "075",
        "San Mateo": "081",
        "Santa Clara": "085",
        "Solano": "095",
        "Sonoma": "097",
    }


    counties = counties[counties["county"].isin(COUNTY_FIPS.values())]
    counties = counties[["county", "geometry"]]

    places = places.rename(columns={"GEOID": "place_id", "NAME": "place_name"})

    places = gpd.sjoin(places, counties, how="inner", predicate="intersects")
    places = places[["place_id", "place_name", "geometry"]]

    places = places[~places["place_name"].str.contains("CDP,")]
    
    # Convert to analysis CRS for spatial operations
    print(f"  Converting places from {places.crs} to {ANALYSIS_CRS}")
    places = places.to_crs(ANALYSIS_CRS)
    
    return places


def load_maz_data():
    # Load MAZ shapefile
    print(f"Loading MAZ shapefile...")
    maz = utils.load_maz_shp().to_crs(ANALYSIS_CRS)
    print(f"  Loaded {len(maz):,} MAZ polygons")
    
    # Calculate acres from geometry
    maz['ACRES'] = maz.geometry.area / SQUARE_METERS_PER_ACRE

    # Load employment data
    print(f"\nLoading MAZ employment data...")
    jobs_maz = get_jobs_maz(write=False)
    print(f"  Loaded employment for {len(jobs_maz):,} MAZs")
    print(f"  Jobs MAZ columns: {list(jobs_maz.columns)[:10]}...")  # Debug: show first 10 columns
    
    # Merge the synthetic pop data
    SYNTH_POP_FILE = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\maz_data.csv")
    pop_maz = pd.read_csv(SYNTH_POP_FILE)
    pop_maz = pop_maz[["MAZ_NODE", "POP", "HH"]]
    
    # Ensure consistent data types for all dataframes
    maz['MAZ_NODE'] = maz['MAZ_NODE'].astype(str)
    maz['TAZ_NODE'] = maz['TAZ_NODE'].astype(str)
    jobs_maz['MAZ_NODE'] = jobs_maz['MAZ_NODE'].astype(str)
    jobs_maz['TAZ_NODE'] = jobs_maz['TAZ_NODE'].astype(str)
    pop_maz['MAZ_NODE'] = pop_maz['MAZ_NODE'].astype(str)

    # Merge job data
    maz = maz.merge(
        jobs_maz[['MAZ_NODE', 'TAZ_NODE', 'emp_total', 'ret_loc', 'ret_reg',
                   'prof', 'fire', 'info', 'serv_bus', 'gov', 'eat', 'art_rec']], 
        on='MAZ_NODE', 
        how='left',
        validate="1:1"
    )

    # Merge pop/hh data
    maz = maz.merge(pop_maz, on="MAZ_NODE", how='left',
        validate="1:1"
    )

    return maz

def spatial_join_maz_to_place(maz, places):
    # Ensure both are in same CRS
    print(f"  MAZ CRS: {maz.crs}")
    print(f"  Places CRS: {places.crs}")
    
    if maz.crs != places.crs:
        print(f"  WARNING: CRS mismatch! Converting places to {maz.crs}")
        places = places.to_crs(maz.crs)
    
    # Perform spatial overlay to get intersection areas
    print(f"  Performing spatial overlay...")
    overlay = gpd.overlay(maz, places, how='intersection')
    print(f"  Found {len(overlay):,} MAZ-place intersections")
    
    if len(overlay) == 0:
        print("  ERROR: No intersections found! Check geometries and CRS.")
        return maz
    
    # Calculate the area of each intersection
    overlay['intersection_area'] = overlay.geometry.area
    
    # For each MAZ, find the place with the largest intersection area
    idx_max_area = overlay.groupby('MAZ_NODE')['intersection_area'].idxmax()
    maz_place = overlay.loc[idx_max_area, ['MAZ_NODE', 'place_id', 'place_name']]
    print(f"  Assigned {len(maz_place):,} unique MAZs to places")
    
    # Merge back to original MAZ data
    maz = maz.merge(maz_place, on='MAZ_NODE', how='left')
    
    # Report on unmatched MAZs
    unmatched = maz['place_id'].isna().sum()
    if unmatched > 0:
        print(f"  WARNING: {unmatched:,} MAZs did not match any place")
    
    return maz


def main():
    """Main entry point that sequences the workflow."""
    print("Loading Bay Area census places...")
    places = load_bay_area_places()
    print(f"  Loaded {len(places):,} places")
    
    print("\nLoading MAZ data...")
    maz = load_maz_data()
    
    print("\nPerforming spatial join of MAZ to places...")
    maz = spatial_join_maz_to_place(maz, places)
    print(f"  Completed spatial join for {len(maz):,} MAZs")
    
    return maz


if __name__ == "__main__":
    maz_with_places = main()



# %%
