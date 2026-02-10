"""
MAZ Land Use Input Creation Pipeline

This module orchestrates the complete process of creating MAZ-level land use inputs
for Travel Model Two (TM2) and ActivitySim. It integrates employment, enrollment,
and parking data into a unified dataset.

Pipeline Steps:
1. Employment: Spatially join business firms to MAZ, aggregate to 27-way steelhead categories
2. Enrollment: Spatially join schools/colleges to MAZ, aggregate by grade level and type
3. Parking: Integrate observed costs, capacity, and estimated costs for unobserved areas

Data Sources:
- Employment: Esri Business Analyst 2023, NAICS crosswalk  
- Enrollment: CA public schools, private schools (CPRS), IPEDS colleges
- Parking: SpotHero scrapes, SF/Oakland/SJ published meter data, ACS block group capacity

Outputs:
- Interim cache: jobs_maz_*.gpkg, enrollment_maz_*.gpkg, parking_capacity.gpkg
- Final: maz_data_v{VERSION}_{VINTAGE}.csv with all attributes

Usage:
    python -m tm2py_utils.inputs.land_use.land_use_pipeline [--no-cache] [--validate-parking]
    OR
    from land_use_pipeline import run_pipeline
    landuse_maz = run_pipeline(use_cache=True)
"""

import pytidycensus
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
import argparse
import logging
from datetime import datetime
import sys
from io import StringIO
from contextlib import contextmanager

# Import configuration
from setup import (
    ANALYSIS_CRS,
    WGS84_CRS,
    SQUARE_METERS_PER_ACRE,
    CENSUS_API_KEY,
    SYNTH_POP_FILE,
    get_output_filename,
    ensure_directories,
    INTERIM_CACHE_DIR,
    BOX_LANDUSE_BASE
)

# Import utilities
from utils import load_maz_shp

# Import core data modules
from job_counts import get_jobs_maz
from enrollment_counts import get_enrollment_maz

# Import parking modules  
from parking_published import published_cost
from parking_area import merge_parking_area
from parking_estimation import merge_estimated_costs


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
# Census Place Loading (for Parking)
# ============================================================================

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


# ============================================================================
# MAZ Base Data Loading
# ============================================================================

def load_maz_base_data(use_maz_orig=False):
    """
    Load MAZ shapefile with employment, enrollment, and population data.
    
    Args:
        use_maz_orig (bool): If True, uses MAZ v2.2. Otherwise uses version from setup.
    
    Returns:
        GeoDataFrame: MAZ with geometry, employment, enrollment, population, and acres
    """
    print(f"\n{'='*70}")
    print(f"Loading MAZ Base Data")
    print(f"{'='*70}\n")
    
    # Load MAZ shapefile
    print(f"Loading MAZ shapefile...")
    maz = load_maz_shp(use_maz_orig=use_maz_orig).to_crs(ANALYSIS_CRS)
    print(f"  Loaded {len(maz):,} MAZ polygons")
    
    # Calculate acres from geometry
    maz['ACRES'] = maz.geometry.area / SQUARE_METERS_PER_ACRE
    
    # Ensure MAZ_NODE and TAZ_NODE are strings for consistent merging
    maz['MAZ_NODE'] = maz['MAZ_NODE'].astype(str)
    maz['TAZ_NODE'] = maz['TAZ_NODE'].astype(str)
    
    return maz


def merge_employment_data(maz, use_cache=False, use_maz_orig=False):
    """
    Merge employment data into MAZ.
    
    Args:
        maz (GeoDataFrame): MAZ base data
        use_cache (bool): If True, reads from interim cache. If False, regenerates data.
        use_maz_orig (bool): MAZ version parameter to pass to get_jobs_maz
    
    Returns:
        GeoDataFrame: MAZ with employment columns added
    """
    print(f"\n{'='*70}")
    print(f"Adding Employment Data")
    print(f"{'='*70}\n")
    
    if use_cache:
        cache_file = get_output_filename("jobs_maz", extension="gpkg", spatial=True)
        if cache_file.exists():
            print(f"  Loading employment from cache: {cache_file}")
            jobs_maz = gpd.read_file(cache_file)
            jobs_maz = pd.DataFrame(jobs_maz.drop(columns='geometry'))  # Drop geometry, use MAZ geometry
            print(f"  Loaded employment for {len(jobs_maz):,} MAZs from cache")
        else:
            print(f"  Cache file not found: {cache_file}")
            print(f"  Regenerating employment data...")
            jobs_maz = get_jobs_maz(write=True, use_maz_orig=use_maz_orig)
    else:
        print(f"  Generating employment data...")
        jobs_maz = get_jobs_maz(write=True, use_maz_orig=use_maz_orig)
    
    # Ensure consistent data types
    jobs_maz['MAZ_NODE'] = jobs_maz['MAZ_NODE'].astype(str)
    if 'TAZ_NODE' in jobs_maz.columns:
        jobs_maz = jobs_maz.drop(columns=['TAZ_NODE'])
    
    # Merge employment columns (exclude geometry)
    emp_columns = [col for col in jobs_maz.columns if col != 'geometry']
    maz = maz.merge(
        jobs_maz[emp_columns],
        on='MAZ_NODE',
        how='left',
        validate="1:1"
    )
    
    print(f"  Employment data merged successfully")
    print(f"  Total regional employment: {maz['emp_total'].sum():,.0f}")
    
    return maz


def merge_enrollment_data(maz, use_cache=False, use_maz_orig=False):
    """
    Merge enrollment data into MAZ.
    
    Args:
        maz (GeoDataFrame): MAZ base data
        use_cache (bool): If True, reads from interim cache. If False, regenerates data.
        use_maz_orig (bool): MAZ version parameter to pass to get_enrollment_maz
    
    Returns:
        GeoDataFrame: MAZ with enrollment columns added
    """
    print(f"\n{'='*70}")
    print(f"Adding Enrollment Data")
    print(f"{'='*70}\n")
    
    if use_cache:
        cache_file = get_output_filename("enrollment_maz", extension="gpkg", spatial=True)
        if cache_file.exists():
            print(f"  Loading enrollment from cache: {cache_file}")
            enroll_maz = gpd.read_file(cache_file)
            enroll_maz = pd.DataFrame(enroll_maz.drop(columns='geometry'))  # Drop geometry, use MAZ geometry
            print(f"  Loaded enrollment for {len(enroll_maz):,} MAZs from cache")
        else:
            print(f"  Cache file not found: {cache_file}")
            print(f"  Regenerating enrollment data...")
            enroll_maz = get_enrollment_maz(write=True, use_maz_orig=use_maz_orig)
    else:
        print(f"  Generating enrollment data...")
        enroll_maz = get_enrollment_maz(write=True, use_maz_orig=use_maz_orig)
    
    # Ensure consistent data types
    enroll_maz['MAZ_NODE'] = enroll_maz['MAZ_NODE'].astype(str)
    if 'TAZ_NODE' in enroll_maz.columns:
        enroll_maz = enroll_maz.drop(columns=['TAZ_NODE'])
    
    # Merge enrollment columns (exclude geometry)
    enroll_columns = [col for col in enroll_maz.columns if col != 'geometry']
    maz = maz.merge(
        enroll_maz[enroll_columns],
        on='MAZ_NODE',
        how='left',
        validate="1:1"
    )
    
    print(f"  Enrollment data merged successfully")
    print(f"  Total K-8 enrollment: {maz['EnrollGradeKto8'].sum():,.0f}")
    print(f"  Total 9-12 enrollment: {maz['EnrollGrade9to12'].sum():,.0f}")
    print(f"  Total college enrollment: {maz['collegeEnroll'].sum():,.0f}")
    
    return maz


def merge_population_data(maz):
    """
    Merge synthetic population data into MAZ.
    
    Args:
        maz (GeoDataFrame): MAZ base data
    
    Returns:
        GeoDataFrame: MAZ with population and household columns added
    """
    print(f"\n{'='*70}")
    print(f"Adding Population Data")
    print(f"{'='*70}\n")
    
    print(f"  Loading synthetic population from: {SYNTH_POP_FILE}")
    pop_maz = pd.read_csv(SYNTH_POP_FILE)
    pop_maz = pop_maz[["MAZ_NODE", "POP", "HH"]]
    pop_maz['MAZ_NODE'] = pop_maz['MAZ_NODE'].astype(str)
    
    # Merge pop/hh data
    maz = maz.merge(pop_maz, on="MAZ_NODE", how='left', validate="1:1")
    
    print(f"  Population data merged successfully")
    print(f"  Total population: {maz['POP'].sum():,.0f}")
    print(f"  Total households: {maz['HH'].sum():,.0f}")
    
    return maz


# ============================================================================
# Parking Data Integration
# ============================================================================

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


def merge_scraped_cost(maz):
    """Merge scraped parking costs from SpotHero data."""
    print(f"\n{'='*70}")
    print(f"Merging Scraped Parking Costs (SpotHero)")
    print(f"{'='*70}\n")
    
    scraped_file = INTERIM_CACHE_DIR / "parking_scrape_location_cost.parquet"
    
    print(f"  Loading scraped parking data from: {scraped_file}")
    scraped = gpd.read_parquet(scraped_file).to_crs(ANALYSIS_CRS)
    
    # Filter to daily and monthly parking types
    daily = scraped[scraped['parking_type'] == 'daily'].copy()
    monthly = scraped[scraped['parking_type'] == 'monthly'].copy()
    
    print(f"  Loaded {len(daily):,} daily parking locations and {len(monthly):,} monthly parking locations")
    
    # Spatial join to MAZ
    if len(daily) > 0:
        daily_maz = gpd.sjoin(maz[['MAZ_NODE', 'geometry']], daily, how='left', predicate='intersects')
        daily_avg = daily_maz.groupby('MAZ_NODE')['price_value'].mean().reset_index()
        daily_avg = daily_avg.rename(columns={'price_value': 'dparkcost'})
        maz = maz.merge(daily_avg, on='MAZ_NODE', how='left')
    else:
        maz['dparkcost'] = None
    
    if len(monthly) > 0:
        monthly_maz = gpd.sjoin(maz[['MAZ_NODE', 'geometry']], monthly, how='left', predicate='intersects')
        monthly_avg = monthly_maz.groupby('MAZ_NODE')['price_value'].mean().reset_index()
        monthly_avg = monthly_avg.rename(columns={'price_value': 'mparkcost'})
        maz = maz.merge(monthly_avg, on='MAZ_NODE', how='left')
    else:
        maz['mparkcost'] = None
    
    # Round to 2 decimal places
    if 'dparkcost' in maz.columns:
        maz['dparkcost'] = maz['dparkcost'].round(2)
    if 'mparkcost' in maz.columns:
        maz['mparkcost'] = maz['mparkcost'].round(2)
    
    print(f"  Scraped costs merged")
    print(f"  MAZs with daily parking cost: {maz['dparkcost'].notnull().sum():,}")
    print(f"  MAZs with monthly parking cost: {maz['mparkcost'].notnull().sum():,}")
    
    return maz


def merge_published_cost(maz):
    """Merge published parking meter costs from SF, Oakland, San Jose."""
    print(f"\n{'='*70}")
    print(f"Merging Published Parking Meter Costs")
    print(f"{'='*70}\n")
    
    hparkcost_maz = published_cost()
    # Ensure MAZ_NODE is string for merge
    hparkcost_maz['MAZ_NODE'] = hparkcost_maz['MAZ_NODE'].astype(str)
    maz = maz.merge(hparkcost_maz[['MAZ_NODE', 'hparkcost']], on='MAZ_NODE', how='left')
    
    # Round to 2 decimal places
    if 'hparkcost' in maz.columns:
        maz['hparkcost'] = maz['hparkcost'].round(2)
    
    print(f"  Published costs merged")
    print(f"  MAZs with hourly parking cost: {maz['hparkcost'].notnull().sum():,}")
    
    return maz


def merge_capacity(maz, use_cache=False, use_maz_orig=False):
    """
    Merge parking capacity data to MAZ and create stall columns.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE and mparkcost from merge_scraped_cost)
        use_cache: If True, reads from interim cache. If False, regenerates data.
        use_maz_orig: MAZ version parameter to pass to get_parking_maz
    
    Returns:
        GeoDataFrame: maz with added parking stall columns
    """
    print(f"\n{'='*70}")
    print(f"Merging Parking Capacity Data")
    print(f"{'='*70}\n")
    
    # Store original count for validation
    original_count = len(maz)
    
    capacity_file = get_output_filename("parking_capacity", extension="gpkg", spatial=True)
    
    # Check if capacity file exists in cache
    if use_cache and capacity_file.exists():
        print(f"  Loading capacity from cache: {capacity_file}")
        capacity = gpd.read_file(capacity_file)
        capacity = pd.DataFrame(capacity.drop(columns='geometry'))
        # Drop emp_total if it exists (to avoid merge conflicts)
        if 'emp_total' in capacity.columns:
            capacity = capacity.drop(columns=['emp_total'])
    else:
        if not use_cache:
            print(f"  Generating parking capacity data...")
        else:
            print(f"  Cache file not found: {capacity_file}")
            print(f"  Generating parking capacity data...")
        
        from parking_capacity import get_parking_maz
        capacity_gdf = get_parking_maz(write=True, use_maz_orig=use_maz_orig)
        capacity = pd.DataFrame(capacity_gdf.drop(columns='geometry', errors='ignore'))
        if 'emp_total' in capacity.columns:
            capacity = capacity.drop(columns=['emp_total'])
    
    print(f"  Loaded capacity data for {len(capacity):,} MAZs")
    
    # Merge capacity columns
    capacity['MAZ_NODE'] = capacity['MAZ_NODE'].astype(str)
    maz = maz.merge(capacity[['MAZ_NODE', 'on_all', 'off_nres']], on='MAZ_NODE', how='left', validate="1:1")
    
    # Validate no records were lost
    if len(maz) != original_count:
        print(f"  WARNING: Record count mismatch. Expected {original_count:,}, got {len(maz):,}")
    else:
        print(f"  ✓ All {original_count:,} MAZ records retained")
    
    # Fill missing capacity with 0
    maz['on_all'] = maz['on_all'].fillna(0)
    maz['off_nres'] = maz['off_nres'].fillna(0)
    
    # Clip any negative values to 0 (safety check for data quality issues)
    neg_on = (maz['on_all'] < 0).sum()
    neg_off = (maz['off_nres'] < 0).sum()
    if neg_on > 0 or neg_off > 0:
        print(f"  ⚠ Warning: Found {neg_on + neg_off:,} MAZs with negative capacity values (clipping to 0)")
        maz['on_all'] = maz['on_all'].clip(lower=0)
        maz['off_nres'] = maz['off_nres'].clip(lower=0)
    
    # Create hourly stalls columns (on-street parking)
    maz['hstallsoth'] = maz['on_all'].round(0)
    maz['hstallssam'] = maz['on_all'].round(0)
    print(f"  Created hourly stalls columns (hstallsoth, hstallssam) from on_all")
    
    # Create daily stalls columns (off-street non-residential)
    maz['dstallsoth'] = maz['off_nres'].round(0)
    maz['dstallssam'] = maz['off_nres'].round(0)
    print(f"  Created daily stalls columns (dstallsoth, dstallssam) from off_nres")
    
    # Create monthly stalls columns (off-street non-residential, only where monthly parking cost exists)
    # NOTE: This is a preliminary assignment based on observed costs only.
    # Monthly stalls will be recalculated after merge_estimated_costs() adds predicted monthly costs.
    if 'mparkcost' in maz.columns:
        # Create condition without modifying the original mparkcost column
        has_monthly_cost = maz['mparkcost'].fillna(0) > 0
        maz['mstallsoth'] = maz['off_nres'].where(has_monthly_cost, 0).round(0)
        maz['mstallssam'] = maz['off_nres'].where(has_monthly_cost, 0).round(0)
        print(f"  Created monthly stalls columns (mstallsoth, mstallssam) from off_nres where mparkcost > 0 (observed only)")
    else:
        # mparkcost not yet available, set to 0 for now (will be updated after merge_scraped_cost)
        maz['mstallsoth'] = 0
        maz['mstallssam'] = 0
        print(f"  Created monthly stalls columns (mstallsoth, mstallssam) - set to 0 (mparkcost not available yet)")
    
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


def update_monthly_stalls_with_predicted_costs(maz):
    """
    Update monthly stalls to reflect both observed and predicted monthly parking costs.
    
    This must be called AFTER merge_estimated_costs() adds predicted monthly costs,
    since merge_capacity() runs before cost estimation and only captures observed costs.
    
    Args:
        maz: GeoDataFrame with off_nres capacity and final mparkcost (observed + predicted)
    
    Returns:
        GeoDataFrame: maz with updated mstallsoth and mstallssam columns
    """
    print(f"\n{'='*70}")
    print(f"Updating Monthly Stalls with Predicted Costs")
    print(f"{'='*70}\n")
    
    # Recalculate monthly stalls based on final mparkcost (observed + predicted)
    if 'mparkcost' in maz.columns and 'off_nres' in maz.columns:
        # Create condition without modifying the original mparkcost column
        has_monthly_cost = maz['mparkcost'].fillna(0) > 0
        maz['mstallsoth'] = maz['off_nres'].where(has_monthly_cost, 0).round(0)
        maz['mstallssam'] = maz['off_nres'].where(has_monthly_cost, 0).round(0)
        
        mazs_with_monthly = (maz['mstallsoth'] > 0).sum()
        total_mazs = len(maz)
        print(f"  Updated monthly stalls for {mazs_with_monthly:,}/{total_mazs:,} MAZs")
        
        if mazs_with_monthly > 0:
            print(f"  Total monthly stalls: {maz['mstallsoth'].sum():,.0f}")
    else:
        print(f"  ⚠ Warning: mparkcost or off_nres column not found, skipping update")
    
    return maz


def update_parkarea_with_predicted_costs(maz):
    """
    Update parkarea classification to include predicted parking costs.
    
    parkarea codes:
    - 0: No paid parking (default)
    - 1: Downtown core (from Local Moran's I analysis)
    - 3: Paid parking (predicted or observed outside downtown)
    - 4: Other areas with some parking but not paid
    """
    # Start with parkarea already assigned by merge_parking_area (0 or 1)
    # parkarea=1 already set for downtown cores
    
   # Set parkarea=3 for non-downtown MAZs with any parking cost (observed or predicted)
    has_parking_cost = (
        (maz['hparkcost'].notnull() & (maz['hparkcost'] > 0)) |
        (maz['dparkcost'].notnull() & (maz['dparkcost'] > 0)) |
        (maz['mparkcost'].notnull() & (maz['mparkcost'] > 0))
    )
    
    maz.loc[has_parking_cost & (maz['parkarea'] != 1), 'parkarea'] = 3
    
    # Set parkarea=4 for MAZs with parking capacity but no cost
    has_capacity = ((maz['on_all'] > 0) | (maz['off_nres'] > 0))
    no_cost = ~has_parking_cost
    
    maz.loc[has_capacity & no_cost & (maz['parkarea'] != 1), 'parkarea'] = 4
    
    # Report final distribution
    print(f"\n  Final parkarea distribution:")
    for code in sorted(maz['parkarea'].unique()):
        count = (maz['parkarea'] == code).sum()
        print(f"    parkarea={int(code)}: {count:,} MAZs")
    
    return maz


# ============================================================================
# Main Pipeline Orchestration
# ============================================================================

def run_pipeline(
    use_cache=True,
    use_maz_orig=False,
    validate_parking=True,
    compare_parking_models=True,
    commercial_density_threshold=1.0,
    daily_percentile=0.95,
    monthly_percentile=0.99
):
    """
    Execute the complete MAZ land use input creation pipeline.
    
    Args:
        use_cache (bool): If True, reads employment/enrollment from interim cache when available
        use_maz_orig (bool): If True, uses MAZ v2.2. Otherwise uses version from setup.
        validate_parking (bool): If True, performs leave-one-city-out cross-validation for parking cost estimation
        compare_parking_models (bool): If True, compares multiple ML models for parking cost estimation
        commercial_density_threshold (float): Minimum commercial employment density for paid parking (jobs/acre)
        daily_percentile (float): County-level percentile threshold for daily parking cost estimation
        monthly_percentile (float): County-level percentile threshold for monthly parking cost estimation
    
    Returns:
        GeoDataFrame: Complete MAZ land use dataset with employment, enrollment, population, and parking
    """
    ensure_directories()
    
    ################## create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ################## console handler - INFO level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)
    ################## file handler - DEBUG level
    log_file = BOX_LANDUSE_BASE / "land_use_pipeline.log"
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                      datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(fh)
    
    # High-level console output
    print(f"\n{'='*80}")
    print(f"MAZ LAND USE INPUT CREATION PIPELINE")
    print(f"{'='*80}")
    print(f"  Log file: {log_file}")
    print(f"  Cache enabled: {use_cache}")
    print(f"  Validation: {validate_parking}")
    print(f"  Model comparison: {compare_parking_models}\n")
    
    # Detailed logging
    logging.info("="*80)
    logging.info("MAZ LAND USE INPUT CREATION PIPELINE")
    logging.info("="*80)
    logging.info(f"Configuration:")
    logging.info(f"  Use cached interim data: {use_cache}")
    logging.info(f"  MAZ version: {'2.2 (original)' if use_maz_orig else 'from setup.py'}")
    logging.info(f"  Validate parking estimation: {validate_parking}")
    logging.info(f"  Compare parking models: {compare_parking_models}")
    logging.info(f"  Commercial density threshold: {commercial_density_threshold}")
    logging.info(f"  Daily percentile: {daily_percentile}")
    logging.info(f"  Monthly percentile: {monthly_percentile}")
    
    # Step 1: Load MAZ base data
    print("▶ Step 1/11: Loading MAZ base data...")
    logging.info("="*80)
    logging.info("STEP 1: Loading MAZ base data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = load_maz_base_data(use_maz_orig=use_maz_orig)
    logging.info(f"Loaded {len(maz):,} MAZ zones")
    print(f"  ✓ Loaded {len(maz):,} MAZ zones\n")
    
    # Step 2: Merge employment data
    print("▶ Step 2/11: Processing employment data...")
    logging.info("="*80)
    logging.info("STEP 2: Processing employment data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_employment_data(maz, use_cache=use_cache, use_maz_orig=use_maz_orig)
    print(f"  ✓ Employment data merged\n")
    
    # Step 3: Merge enrollment data
    print("▶ Step 3/11: Processing enrollment data...")
    logging.info("="*80)
    logging.info("STEP 3: Processing enrollment data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_enrollment_data(maz, use_cache=use_cache, use_maz_orig=use_maz_orig)
    print(f"  ✓ Enrollment data merged\n")
    
    # Step 4: Merge population data
    print("▶ Step 4/11: Processing population data...")
    logging.info("="*80)
    logging.info("STEP 4: Processing population data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_population_data(maz)
    print(f"  ✓ Population data merged\n")
    
    # Step 5: Spatial join to Census places (for parking analysis)
    print("▶ Step 5/11: Joining Census place boundaries...")
    logging.info("="*80)
    logging.info("STEP 5: Joining Census place boundaries")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        places = load_bay_area_places()
        logging.info(f"Loaded {len(places):,} places")
        maz = spatial_join_maz_to_place(maz, places)
    print(f"  ✓ Joined {len(places):,} places\n")
    
    # Step 6: Merge parking data
    print("▶ Step 6/11: Merging parking cost data...")
    logging.info("="*80)
    logging.info("STEP 6: Merging parking cost data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_scraped_cost(maz)
        maz = merge_published_cost(maz)
        maz = merge_capacity(maz, use_cache=use_cache, use_maz_orig=use_maz_orig)
    print(f"  ✓ Parking cost data merged\n")
    
    # Step 7: Assign parking areas using Local Moran's I
    print("▶ Step 7/11: Assigning parking areas (Local Moran's I)...")
    logging.info("="*80)
    logging.info("STEP 7: Assigning parking areas")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_parking_area(maz, min_place_employment=100, significance_level=0.05)
    print(f"  ✓ Parking areas assigned\n")
    
    # Step 8: Estimate parking costs for unobserved areas
    print("▶ Step 8/11: Estimating parking costs (ML models)...")
    logging.info("="*80)
    logging.info("STEP 8: Estimating parking costs")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_estimated_costs(
            maz,
            run_validation=validate_parking,
            compare_models_flag=compare_parking_models,
            use_best_model=True,
            commercial_density_threshold=commercial_density_threshold,
            daily_percentile=daily_percentile,
            monthly_percentile=monthly_percentile,
            probability_threshold=0.3  # Optimized via cross-validation
        )
    
    # Round parking cost columns to 2 decimal places (after prediction)
    for cost_col in ['hparkcost', 'dparkcost', 'mparkcost']:
        if cost_col in maz.columns:
            maz[cost_col] = maz[cost_col].round(2)
    
    print(f"  ✓ Parking costs estimated\n")
    
    # Step 8.5: Update monthly stalls with predicted costs
    print("▶ Step 9/11: Updating monthly stalls with predicted costs...")
    logging.info("="*80)
    logging.info("STEP 9: Updating monthly stalls with predicted costs")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = update_monthly_stalls_with_predicted_costs(maz)
    print(f"  ✓ Monthly stalls updated\n")
    
    # Step 9: Update parkarea classification with predicted costs
    print("▶ Step 10/11: Updating parkarea classifications...")
    logging.info("="*80)
    logging.info("STEP 10: Updating parkarea classifications")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = update_parkarea_with_predicted_costs(maz)
    print(f"  ✓ Parkarea classifications updated\n")
    
    # Step 10: Write final output
    print("▶ Step 11/11: Writing final output...")
    logging.info("="*80)
    logging.info("STEP 11: Writing final output")
    logging.info("="*80)
    
    # Clean up duplicate TAZ_NODE columns in maz before creating output
    dup_cols = [col for col in maz.columns if col.endswith('_x') or col.endswith('_y')]
    if dup_cols:
        logging.warning(f"Found duplicate columns in maz GeoDataFrame: {dup_cols}")
        logging.warning(f"Dropping these columns from maz")
        maz = maz.drop(columns=dup_cols)
    
    # Remove interim processing columns from maz
    interim_cols = ['place_id', 'on_all', 'off_nres', 'commercial_emp', 'downtown_emp', 
                    'commercial_emp_den', 'downtown_emp_den', 'emp_total_den', 
                    'pop_den', 'moran_category']
    cols_to_drop = [col for col in interim_cols if col in maz.columns]
    if cols_to_drop:
        logging.info(f"Removing interim processing columns from maz: {cols_to_drop}")
        maz = maz.drop(columns=cols_to_drop)
    else:
        logging.info(f"No interim columns found to remove from maz (checked: {interim_cols})")
    
    # Drop geometry for final tabular output
    landuse_maz = pd.DataFrame(maz.drop(columns='geometry'))
    
    output_file = get_output_filename("maz_data", extension="csv", spatial=False)
    logging.info(f"Writing MAZ land use data to: {output_file}")
    landuse_maz.to_csv(output_file, index=False)
    print(f"  ✓ Output written to: {output_file.name}\n")
    
    # Final summary
    
    logging.info("="*80)
    logging.info("PIPELINE COMPLETE")
    logging.info("="*80)
    logging.info(f"Total MAZ records: {len(landuse_maz):,}")
    logging.info(f"Total columns: {len(landuse_maz.columns)}")
    logging.info(f"Output file: {output_file}")
    
    print("="*80)
    print("PIPELINE COMPLETE!")
    print("="*80)
    print(f"  Total MAZ records: {len(landuse_maz):,}")
    print(f"  Total columns: {len(landuse_maz.columns)}")
    print(f"  See {BOX_LANDUSE_BASE / 'land_use_pipeline.log'} for detailed processing log")
    
    return maz


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Command-line interface for the land use pipeline."""
    parser = argparse.ArgumentParser(
        description="MAZ Land Use Input Creation Pipeline for TM2/ActivitySim"
    )
    parser.add_argument(
        "--no-cache",
        action="store_false",
        dest="use_cache",
        help="Skip cached employment/enrollment data and regenerate from raw sources"
    )
    parser.add_argument(
        "--use-maz-orig",
        action="store_true",
        help="Use original MAZ v2.2 shapefile instead of version from setup.py"
    )
    parser.add_argument(
        "--no-validate-parking",
        action="store_false",
        dest="validate_parking",
        help="Skip leave-one-city-out cross-validation for parking cost estimation"
    )
    parser.add_argument(
        "--no-compare-parking-models",
        action="store_false",
        dest="compare_parking_models",
        help="Skip comparison of multiple ML models for parking cost estimation"
    )
    
    args = parser.parse_args()
    
    maz = run_pipeline(
        use_cache=args.use_cache,
        use_maz_orig=args.use_maz_orig,
        validate_parking=args.validate_parking,
        compare_parking_models=args.compare_parking_models
    )
    
    print(f"\nPipeline execution complete!")
    
    return maz


if __name__ == "__main__":
    main()
