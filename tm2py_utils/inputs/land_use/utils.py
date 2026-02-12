
from pathlib import Path
import os
import sys
from io import StringIO
from contextlib import contextmanager
import logging
import pandas as pd
import geopandas as gpd
import pytidycensus

# Import configuration from setup module
from setup import (
    MAZ_TAZ_DIR, 
    ANALYSIS_CRS,
    WGS84_CRS,
    M_DRIVE_BASE,
    MAZ_VERSION,
    DATA_VINTAGE,
    INTERIM_CACHE_DIR,
    FINAL_OUTPUT_DIR,
    SQUARE_METERS_PER_ACRE,
    CENSUS_API_KEY
)


# ============================================================================
# Logging Utilities
# ============================================================================

@contextmanager
def redirect_stdout_to_logger():
    """Context manager to redirect stdout (print statements) to logger."""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        yield
    finally:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        if output.strip():
            for line in output.splitlines():
                if line.strip():
                    logging.info(line)



# ============================================================================
# File Naming Utilities
# ============================================================================

def get_output_filename(data_type, extension="csv", spatial=False):
    """
    Generate standardized output filename.
    
    Args:
        data_type (str): Type of data (e.g., 'jobs_maz', 'enrollment_maz', 'maz_landuse')
        extension (str): File extension ('csv', 'gpkg', etc.)
        spatial (bool): If True, returns path to interim cache (for spatial data)
    
    Returns:
        Path: Full path to output file
    """
    filename = f"{data_type}_v{MAZ_VERSION}_{DATA_VINTAGE}.{extension}"
    
    if spatial or extension == "gpkg":
        return INTERIM_CACHE_DIR / filename
    else:
        return FINAL_OUTPUT_DIR / filename


# ============================================================================
# Data Loading Utilities
# ============================================================================

def load_maz_shp():
    """
    Loads the MAZ shapefile.
    
    Returns:
        GeoDataFrame: MAZ polygons with MAZ_NODE, TAZ_NODE, ACRES, and geometry columns.
                     MAZ_NODE and TAZ_NODE are returned as strings for consistent merging.
    """
    print(f"\n{'='*70}")
    print(f"Loading MAZ Shapefile")
    print(f"{'='*70}\n")
    
    print(f"Loading MAZ shapefile...")
    maz_shp = os.path.join(MAZ_TAZ_DIR, f"mazs_TM2_{MAZ_VERSION}.shp")
    maz = gpd.read_file(maz_shp).to_crs(ANALYSIS_CRS)
    print(f"  Loaded MAZ v{MAZ_VERSION} from: {maz_shp}")

    maz = maz[["MAZ_NODE", "TAZ_NODE", "geometry"]]
    print(f"  Loaded {len(maz):,} MAZ polygons")
    
    # Calculate acres from geometry
    maz['ACRES'] = maz.geometry.area / SQUARE_METERS_PER_ACRE
    
    # Ensure MAZ_NODE and TAZ_NODE are strings for consistent merging
    maz['MAZ_NODE'] = maz['MAZ_NODE'].astype(str)
    maz['TAZ_NODE'] = maz['TAZ_NODE'].astype(str)

    return maz


def spatial_join_to_maz(points_gdf, maz_gdf):
    """
    Spatially joins point features to MAZ polygons using a two-step approach:
    1. Join points within MAZ polygons (fast, catches majority)
    2. Join remaining points to nearest MAZ (catches edge cases)
    
    This ensures every point gets assigned to a MAZ, even if slightly outside polygon boundaries
    due to geocoding errors or topology issues.
    
    Args:
        points_gdf (GeoDataFrame): Point features to join to MAZ (e.g., firms, schools).
        maz_gdf (GeoDataFrame): MAZ polygons with MAZ_NODE and TAZ_NODE columns.
    
    Returns:
        DataFrame: Input points with added MAZ_NODE and TAZ_NODE columns (geometry dropped).
    """
    print(f"Spatially joining {len(points_gdf)} points to MAZ...")
    
    # Step 1: Spatial join using 'within' predicate (points inside MAZ polygons)
    joined = gpd.sjoin(points_gdf, maz_gdf, how="left", predicate="within")
    joined = joined.drop(columns=['index_right'], errors='ignore')
    
    matched_count = joined["MAZ_NODE"].notnull().sum()
    print(f"  Step 1 (within): {matched_count:,} / {len(points_gdf):,} points matched to MAZ")
    
    # Step 2: Nearest neighbor join for unmatched points
    unmatched = joined[joined["MAZ_NODE"].isnull()]
    if len(unmatched) > 0:
        print(f"  Step 2 (nearest): Assigning {len(unmatched):,} unmatched points to nearest MAZ...")
        
        # Prepare unmatched subset as GeoDataFrame, drop null MAZ/TAZ columns
        unmatched_gdf = gpd.GeoDataFrame(
            unmatched, 
            geometry="geometry", 
            crs=points_gdf.crs
        ).drop(columns=["MAZ_NODE", "TAZ_NODE"], errors='ignore')
        
        # Nearest neighbor spatial join
        nearest_joined = gpd.sjoin_nearest(unmatched_gdf, maz_gdf, how="left")
        nearest_joined = nearest_joined.drop(columns=['index_right'], errors='ignore')
        
        # Convert to DataFrame and concatenate with successfully matched points
        nearest_joined = pd.DataFrame(nearest_joined)
        matched = pd.DataFrame(joined[joined["MAZ_NODE"].notnull()])
        joined = pd.concat([matched, nearest_joined], ignore_index=True)
        
        still_unmatched = joined["MAZ_NODE"].isnull().sum()
        if still_unmatched > 0:
            print(f"  WARNING: {still_unmatched} points still unmatched after nearest join!")
        else:
            print(f"  Step 2 complete: All points now assigned to MAZ")
    
    total_matched = joined["MAZ_NODE"].notnull().sum()
    print(f"  Final: {total_matched:,} / {len(points_gdf):,} points assigned to MAZ")
    
    return joined

def load_bay_area_places():
    """Load Census place boundaries for Bay Area counties."""
    # Set Census API key
    pytidycensus.set_census_api_key(CENSUS_API_KEY)

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
        "Sonoma": "097"
    }
    
    # Filter to Bay Area counties
    bay_counties = counties[counties['GEOID'].str[2:].isin(COUNTY_FIPS.values())]
    
    # Add county names
    fips_to_name = {v: k for k, v in COUNTY_FIPS.items()}
    bay_counties['county_name'] = bay_counties['GEOID'].str[2:].map(fips_to_name)
    
    # Get place IDs that intersect Bay Area counties
    places_gdf = gpd.GeoDataFrame(places, geometry='geometry', crs=WGS84_CRS)
    counties_gdf = gpd.GeoDataFrame(bay_counties, geometry='geometry', crs=WGS84_CRS)
    
    # Spatial join to get places in Bay Area
    places_in_bay = gpd.sjoin(places_gdf, counties_gdf[['geometry', 'county_name']], how='inner', predicate='intersects')
    
    # Extract place info
    places_in_bay['place_id'] = places_in_bay['GEOID']
    places_in_bay['place_name'] = places_in_bay['NAME'].str.replace(' city, California', '').str.replace(' town, California', '').str.replace(', California', '')
    
    # Convert to analysis CRS
    places_in_bay = places_in_bay.to_crs(ANALYSIS_CRS)
    places_in_bay = places_in_bay[['place_id', 'place_name', 'county_name', 'geometry']]
    
    return places_in_bay


def spatial_join_maz_to_place(maz, places):
    """Spatially join MAZ to Census places by largest intersection area."""
    print(f"\n{'='*70}")
    print(f"Spatial Join: MAZ to Census Places")
    print(f"{'='*70}\n")
    
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
    maz_place = overlay.loc[idx_max_area, ['MAZ_NODE', 'place_id', 'place_name', 'county_name']]
    
    # Merge place info back to maz
    maz = maz.merge(maz_place, on='MAZ_NODE', how='left')
    
    print(f"  Completed spatial join")
    print(f"  MAZs in cities: {maz['place_name'].notnull().sum():,}")
    print(f"  MAZs outside cities: {maz['place_name'].isnull().sum():,}")
    
    return maz

# ============================================================================
# Inflation Handling Utilities
# ============================================================================

def get_cpi_deflator(from_year=2023, to_year=2010):
    """
    Calculate CPI deflator to convert monetary values between years.
    
    Args:
        from_year (int): Year of original data (default: 2023)
        to_year (int): Target year for TM2 (default: 2010)
    
    Returns:
        float: Deflator multiplier (value in to_year = value in from_year * deflator)
    
    Example:
        # Convert 2023 parking cost to 2010 dollars
        cost_2010 = cost_2023 * get_cpi_deflator(2023, 2010)
        # Deflator = 218.056 / 304.702 = 0.7155
    """
    from setup import CPI_VALUES
    
    if from_year not in CPI_VALUES:
        raise ValueError(f"CPI value not available for year {from_year}. "
                        f"Available years: {list(CPI_VALUES.keys())}")
    if to_year not in CPI_VALUES:
        raise ValueError(f"CPI value not available for year {to_year}. "
                        f"Available years: {list(CPI_VALUES.keys())}")
    
    return CPI_VALUES[to_year] / CPI_VALUES[from_year]


def deflate_parking_costs(maz, from_year=2023, to_year=2010):
    """
    Deflate parking cost variables from source year to target year using CPI-U.
    
    Applies deflation to:
    - hparkcost (hourly parking cost)
    - dparkcost (daily parking cost)  
    - mparkcost (monthly parking cost)
    
    Args:
        maz (GeoDataFrame): MAZ data with parking cost columns
        from_year (int): Source year of cost data (default: 2023)
        to_year (int): Target year for deflation (default: 2010)
    
    Returns:
        GeoDataFrame: maz with deflated parking costs
    """
    print(f"\n{'='*70}")
    print(f"Deflating Parking Costs to {to_year} Dollars")
    print(f"{'='*70}\n")
    
    deflator = get_cpi_deflator(from_year, to_year)
    print(f"  CPI deflator ({from_year} → {to_year}): {deflator:.4f}")
    
    cost_columns = ['hparkcost', 'dparkcost', 'mparkcost']
    
    for col in cost_columns:
        non_null_count = maz[col].notnull().sum()
        
        # Store original mean for reporting (non-zero values only)
        non_zero_mask = maz[col] > 0
        original_mean = maz.loc[non_zero_mask, col].mean() if non_zero_mask.any() else 0
        
        # Apply deflator to non-null values
        maz[col] = maz[col] * deflator
        
        # Round to 2 decimal places
        maz[col] = maz[col].round(2)
        
        # Report deflation (recalculate mask after deflation)
        non_zero_mask = maz[col] > 0
        deflated_mean = maz.loc[non_zero_mask, col].mean() if non_zero_mask.any() else 0
        print(f"  {col}:")
        print(f"    MAZs with data: {non_null_count:,}")
        print(f"    Mean ({from_year}$): ${original_mean:.2f}")
        print(f"    Mean ({to_year}$): ${deflated_mean:.2f}")
    
    return maz