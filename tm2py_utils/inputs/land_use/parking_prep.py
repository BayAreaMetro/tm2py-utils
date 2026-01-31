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

def merge_scraped_cost(maz):
    """
    Spatially join parking scrape data to MAZ zones and calculate average costs.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE)
    
    Returns:
        GeoDataFrame: maz with added dparkcost and mparkcost columns
    """
    INPUT_DIR = Path(r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse')
    INPUT_FILE = 'parking_scrape_location_cost.parquet'

    print("Loading parking scrape data...")
    parking_scrape = gpd.read_parquet(INPUT_DIR / INPUT_FILE)
    parking_scrape = parking_scrape[["spot_id", "parking_type", "price_value", "geometry"]]
    print(f"  Loaded {len(parking_scrape):,} parking spots")
    
    # Ensure both are in the same CRS
    print(f"  Parking scrape CRS: {parking_scrape.crs}")
    print(f"  MAZ CRS: {maz.crs}")
    if parking_scrape.crs != maz.crs:
        print(f"  Converting parking scrape to {maz.crs}")
        parking_scrape = parking_scrape.to_crs(maz.crs)
    
    # Spatial join: assign MAZ_NODE to each parking spot
    print("  Performing spatial join...")
    parking_with_maz = gpd.sjoin(
        parking_scrape[['geometry', 'price_value', 'parking_type']], 
        maz[['geometry', 'MAZ_NODE']], 
        how='left',
        predicate='within'
    )
    print(f"  Matched {parking_with_maz['MAZ_NODE'].notna().sum():,} spots to MAZs")
    
    # Group by MAZ_NODE and parking_type, calculate average price
    print("  Calculating average prices by MAZ and parking type...")
    avg_prices = parking_with_maz.groupby(['MAZ_NODE', 'parking_type'])['price_value'].mean().reset_index()
    print(f"  Calculated averages for {len(avg_prices):,} MAZ-parking_type combinations")
    
    # Pivot to get daily and monthly as separate columns
    avg_prices_pivot = avg_prices.pivot(
        index='MAZ_NODE', 
        columns='parking_type', 
        values='price_value'
    ).reset_index()
    
    # Rename columns
    avg_prices_pivot = avg_prices_pivot.rename(columns={
        'daily': 'dparkcost',
        'monthly': 'mparkcost'
    })
    print(f"  Created dparkcost and mparkcost columns")
    
    # Merge back to maz
    print("  Merging parking costs back to MAZ...")
    maz = maz.merge(avg_prices_pivot, on='MAZ_NODE', how='left')
    
    # Report statistics
    mazs_with_daily = maz['dparkcost'].notna().sum()
    mazs_with_monthly = maz['mparkcost'].notna().sum()
    print(f"  MAZs with daily parking cost: {mazs_with_daily:,}/{len(maz):,}")
    print(f"  MAZs with monthly parking cost: {mazs_with_monthly:,}/{len(maz):,}")
    
    if mazs_with_daily > 0:
        print(f"  Daily parking cost range: ${maz['dparkcost'].min():.2f} - ${maz['dparkcost'].max():.2f}")
        print(f"  Daily parking cost mean: ${maz['dparkcost'].mean():.2f}")
    if mazs_with_monthly > 0:
        print(f"  Monthly parking cost range: ${maz['mparkcost'].min():.2f} - ${maz['mparkcost'].max():.2f}")
        print(f"  Monthly parking cost mean: ${maz['mparkcost'].mean():.2f}")
    
    return maz

# def merge_published_cost():
#     # bring in the publised cost data here

def merge_capacity(maz):
    """
    Merge parking capacity data to MAZ and create stall columns.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE and mparkcost from merge_scraped_cost)
    
    Returns:
        GeoDataFrame: maz with added parking stall columns
    """
    INPUT_DIR = Path(r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse')
    INPUT_FILE = 'parking_capacity.gpkg'

    print("Loading parking capacity data...")
    parking_capacity = gpd.read_file(INPUT_DIR / INPUT_FILE)
    parking_capacity = parking_capacity.drop(columns=["emp_total"])
    print(f"  Loaded capacity data for {len(parking_capacity):,} MAZs")
    
    # Store original count for validation
    original_count = len(maz)
    
    # Ensure consistent data types
    parking_capacity['MAZ_NODE'] = parking_capacity['MAZ_NODE'].astype(str)
    
    # Merge capacity data to maz (left join to keep all MAZ records)
    print("  Merging capacity data to MAZ...")
    maz = maz.merge(
        parking_capacity[['MAZ_NODE', 'on_all', 'off_nres']], 
        on='MAZ_NODE', 
        how='left',
        validate="1:1"
    )
    
    # Validate no records were lost
    if len(maz) != original_count:
        print(f"  WARNING: Record count changed from {original_count:,} to {len(maz):,}")
    else:
        print(f"  ✓ All {original_count:,} MAZ records retained")
    
    # Fill NaN values with 0 for MAZs without capacity data
    maz['on_all'] = maz['on_all'].fillna(0)
    maz['off_nres'] = maz['off_nres'].fillna(0)
    
    # Create hourly stalls columns (on-street parking)
    maz['hstallsoth'] = maz['on_all']
    maz['hstallssam'] = maz['on_all']
    print(f"  Created hourly stalls columns (hstallsoth, hstallssam) from on_all")
    
    # Create daily stalls columns (off-street non-residential)
    maz['dstallsoth'] = maz['off_nres']
    maz['dstallssam'] = maz['off_nres']
    print(f"  Created daily stalls columns (dstallsoth, dstallssam) from off_nres")
    
    # Create monthly stalls columns (off-street non-residential, only where monthly parking cost exists)
    # Fill NaN in mparkcost with 0 for comparison
    maz['mparkcost'] = maz['mparkcost'].fillna(0)
    maz['mstallsoth'] = maz['off_nres'].where(maz['mparkcost'] > 0, 0)
    maz['mstallssam'] = maz['off_nres'].where(maz['mparkcost'] > 0, 0)
    print(f"  Created monthly stalls columns (mstallsoth, mstallssam) from off_nres where mparkcost > 0")
    
    # Report statistics
    total_mazs = len(maz)
    mazs_with_hourly = (maz['hstallsoth'] > 0).sum()
    mazs_with_daily = (maz['dstallsoth'] > 0).sum()
    mazs_with_monthly = (maz['mstallsoth'] > 0).sum()
    
    print(f"  MAZs with hourly stalls: {mazs_with_hourly:,}/{total_mazs:,}")
    print(f"  MAZs with daily stalls: {mazs_with_daily:,}/{total_mazs:,}")
    print(f"  MAZs with monthly stalls: {mazs_with_monthly:,}/{total_mazs:,}")
    
    if mazs_with_hourly > 0:
        print(f"  Total hourly stalls: {maz['hstallsoth'].sum():,.0f}")
    if mazs_with_daily > 0:
        print(f"  Total daily stalls: {maz['dstallsoth'].sum():,.0f}")
    if mazs_with_monthly > 0:
        print(f"  Total monthly stalls: {maz['mstallsoth'].sum():,.0f}")
    
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
    
    print("\nMerging parking scrape data...")
    maz = merge_scraped_cost(maz)
    print(f"  Completed parking cost merge")
    
    print("\nMerging parking capacity data...")
    maz = merge_capacity(maz)
    print(f"  Completed parking capacity merge")
    
    return maz


if __name__ == "__main__":
    maz_prepped = main()

