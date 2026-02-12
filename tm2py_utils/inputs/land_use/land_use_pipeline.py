"""
MAZ Land Use Input Creation Pipeline

This module orchestrates the complete process of creating MAZ-level land use inputs
for Travel Model Two (TM2). It integrates employment, enrollment,
and parking data into a unified dataset.

High-Level Steps:
1. Employment: Spatially join business firms to MAZ, aggregate to 27-way steelhead categories
2. Enrollment: Spatially join schools/colleges to MAZ, aggregate by grade level and type
3. Parking: Integrate observed costs, capacity, and estimated costs for unobserved areas


Outputs:
- Interim cache: jobs_maz_*.gpkg, enrollment_maz_*.gpkg, parking_capacity.gpkg
- Final: maz_data_v{VERSION}_{VINTAGE}.csv with all attributes

Usage:
    python -m tm2py_utils.inputs.land_use.land_use_pipeline [--no-cache] [--validate-parking]
    OR
    from land_use_pipeline import run_pipeline
    landuse_maz = run_pipeline(use_cache=True)
"""
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
import argparse
import logging
from datetime import datetime

# Import configuration
from setup import (
    ANALYSIS_CRS,
    WGS84_CRS,
    SQUARE_METERS_PER_ACRE,
    CENSUS_API_KEY,
    SYNTH_POP_FILE,
    ensure_directories,
    INTERIM_CACHE_DIR,
    BOX_LANDUSE_BASE
)

# Import utilities
from utils import (
    load_maz_shp,
    deflate_parking_costs,
    get_output_filename,
    redirect_stdout_to_logger,
    load_bay_area_places,
    spatial_join_maz_to_place
)

# Import core modules
from job_counts import get_jobs_maz
from enrollment_counts import get_enrollment_maz
from parking_published import published_cost
from parking_area import merge_parking_area
from parking_estimation import (
    estimate_and_validate_hourly_parking_models,
    apply_hourly_parking_model,
    estimate_parking_by_county_threshold,
    backfill_downtown_daily_costs,
    update_monthly_stalls_with_predicted_costs,
    update_parkarea_with_predicted_costs
)


# ============================================================================
# Define merging functions
# ============================================================================

def merge_employment_data(maz, use_cache=False):
    """
    Merge employment data into MAZ.
    
    Args:
        maz (GeoDataFrame): MAZ data
        use_cache (bool): If True, reads from interim cache. If False, regenerates data.
    
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
            jobs_maz = get_jobs_maz(write=True)
    else:
        print(f"  Generating employment data...")
        jobs_maz = get_jobs_maz(write=True)
    
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


def merge_enrollment_data(maz, use_cache=False):
    """
    Merge enrollment data into MAZ.

    Args:
        maz (GeoDataFrame): MAZ data
        use_cache (bool): If True, reads from interim cache. If False, regenerates data.

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
            enroll_maz = get_enrollment_maz(write=True)
    else:
        print(f"  Generating enrollment data...")
        enroll_maz = get_enrollment_maz(write=True)
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
        maz (GeoDataFrame): MAZ data
    
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



def merge_scraped_cost(maz):
    """
    Merge scraped parking costs from SpotHero data.
    
    Args:
        maz (GeoDataFrame): MAZ data
    
    Returns:
        GeoDataFrame: MAZ with dparkcost and mparkcost columns added
    """
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
    """
    Merge published parking meter costs from SF, Oakland, San Jose.
    python
    Args:
        maz (GeoDataFrame): MAZ data
    
    Returns:
        GeoDataFrame: MAZ with hparkcost column added
    """
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


def merge_capacity(maz, use_cache=False):
    """
    Merge parking capacity data to MAZ and create stall columns.
    
    Args:
        maz (GeoDataFrame): MAZ data
        use_cache (bool): If True, reads from interim cache. If False, regenerates data.
    
    Returns:
        GeoDataFrame: MAZ with parking stall columns added
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
        capacity_gdf = get_parking_maz(write=True)
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
    # Monthly stalls will be recalculated after merge_estimated_cost() adds predicted monthly costs.
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


def merge_estimated_cost(
    maz,
    validate_parking=True,
    compare_parking_models=True,
    commercial_density_threshold=1.0,
    daily_percentile=0.95,
    monthly_percentile=0.99,
    probability_threshold=0.3
):
    """
    Merge estimated parking costs for hourly, daily, and monthly parking.
    
    This function orchestrates the complete parking cost estimation workflow:
    1. Run model selection and validation for hourly parking
    2. Estimate hourly parking costs using the selected model
    3. Estimate daily/monthly parking costs using county-level density thresholds
    
    Args:
        maz (GeoDataFrame): MAZ data with employment, enrollment, capacity, and observed costs
        validate_parking (bool): If True, performs leave-one-city-out cross-validation
        compare_parking_models (bool): If True, compares multiple ML models
        commercial_density_threshold (float): Minimum commercial employment density for paid parking (jobs/acre)
        daily_percentile (float): County-level percentile threshold for daily parking cost estimation
        monthly_percentile (float): County-level percentile threshold for monthly parking cost estimation
        probability_threshold (float): Classification threshold for model predictions
    
    Returns:
        GeoDataFrame: MAZ with estimated hparkcost, dparkcost, mparkcost for areas with unobserved data
    """
    print(f"\n{'='*70}")
    print(f"Estimating Parking Costs")
    print(f"{'='*70}\n")
    
    # Step 1: Run model selection and validation for hourly parking
    selected_model, selected_model_name = estimate_and_validate_hourly_parking_models(
        maz,
        run_validation=validate_parking,
        compare_models_flag=compare_parking_models,
        use_best_model=True,
        commercial_density_threshold=commercial_density_threshold
    )
    
    # Step 2: Estimate hourly parking costs
    print(f"\n{'='*70}")
    print(f"Applying Hourly Parking Cost Model")
    print(f"{'='*70}\n")
    maz = apply_hourly_parking_model(
        maz,
        commercial_density_threshold,
        probability_threshold,
        model=selected_model,
        model_name=selected_model_name
    )
    
    # Step 3: Estimate daily/monthly parking costs
    print(f"\n{'='*70}")
    print(f"Estimating Daily/Monthly Parking Costs")
    print(f"{'='*70}\n")
    maz = estimate_parking_by_county_threshold(
        maz, daily_percentile, monthly_percentile
    )
    
    print(f"\n  Parking cost estimation complete")
    
    return maz


# ============================================================================
# Main Pipeline Orchestration
# ============================================================================

def run_pipeline(
    use_cache=True,
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
        validate_parking (bool): If True, performs leave-one-city-out cross-validation for parking cost estimation
        compare_parking_models (bool): If True, compares multiple ML models for parking cost estimation
        commercial_density_threshold (float): Minimum commercial employment density for paid parking (jobs/acre)
        daily_percentile (float): County-level percentile threshold for daily parking cost estimation
        monthly_percentile (float): County-level percentile threshold for monthly parking cost estimation
    
    Returns:
        GeoDataFrame: Complete MAZ land use dataset with employment, enrollment, parking, and synthesized population
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
    log_file = get_output_filename("maz_data", extension="log", spatial=False)
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
    logging.info(f"  Validate parking estimation: {validate_parking}")
    logging.info(f"  Compare parking models: {compare_parking_models}")
    logging.info(f"  Commercial density threshold: {commercial_density_threshold}")
    logging.info(f"  Daily cost percentile: {daily_percentile}")
    logging.info(f"  Monthly cost percentile: {monthly_percentile}")
    
    # Step 1: Load MAZ data
    print("▶ Step 1/13: Loading MAZ data...")
    logging.info("="*80)
    logging.info("STEP 1: Loading MAZ data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = load_maz_shp()
    # Step 2: Merge employment data
    print("▶ Step 2/13: Processing employment data...")
    logging.info("="*80)
    logging.info("STEP 2: Processing employment data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_employment_data(maz, use_cache=use_cache)
    print(f"  ✓ Employment data merged\n")
    
    # Step 3: Merge enrollment data
    print("▶ Step 3/13: Processing enrollment data...")
    logging.info("="*80)
    logging.info("STEP 3: Processing enrollment data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_enrollment_data(maz, use_cache=use_cache)
    print(f"  ✓ Enrollment data merged\n")
    
    # Step 4: Merge population data
    print("▶ Step 4/13: Processing population data...")
    logging.info("="*80)
    logging.info("STEP 4: Processing population data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_population_data(maz)
    print(f"  ✓ Population data merged\n")
    
    # Step 5: Spatial join to Census places (for parking analysis)
    print("▶ Step 5/13: Joining Census place boundaries...")
    logging.info("="*80)
    logging.info("STEP 5: Joining Census place boundaries")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        places = load_bay_area_places()
        logging.info(f"Loaded {len(places):,} places")
        maz = spatial_join_maz_to_place(maz, places)
    print(f"  ✓ Joined {len(places):,} places\n")
    
    # Step 6: Merge parking data
    print("▶ Step 6/13: Merging parking cost data...")
    logging.info("="*80)
    logging.info("STEP 6: Merging parking cost data")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_scraped_cost(maz)
        maz = merge_published_cost(maz)
        maz = merge_capacity(maz, use_cache=use_cache)
    print(f"  ✓ Parking cost data merged\n")
    
    # Step 7: Assign initial parking areas
    print("▶ Step 7/13: Assigning parking areas...")
    logging.info("="*80)
    logging.info("STEP 7: Assigning parking areas")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_parking_area(maz, min_place_employment=100, significance_level=0.05)
    print(f"  ✓ Parking areas assigned\n")
    
    # Step 8: Estimate parking costs for unobserved areas
    print("▶ Step 8/13: Estimating parking costs...")
    logging.info("="*80)
    logging.info("STEP 8: Estimating parking costs")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = merge_estimated_cost(
            maz,
            validate_parking=validate_parking,
            compare_parking_models=compare_parking_models,
            commercial_density_threshold=commercial_density_threshold,
            daily_percentile=daily_percentile,
            monthly_percentile=monthly_percentile,
            probability_threshold=0.3  # Optimized via cross-validation
        )
    
    print(f"  ✓ Parking costs estimated\n")
    
    # Step 9: Backfill downtown daily costs
    print("▶ Step 9/13: Backfilling downtown daily costs...")
    logging.info("="*80)
    logging.info("STEP 9: Backfilling downtown daily costs")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = backfill_downtown_daily_costs(maz)
    print(f"  ✓ Downtown daily costs backfilled\n")
    
    # Step 10: Deflate parking costs to 2010 dollars
    print("▶ Step 10/13: Deflating parking costs to 2010 dollars...")
    logging.info("="*80)
    logging.info("STEP 10: Deflating parking costs to 2010 dollars")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = deflate_parking_costs(maz, from_year=2023, to_year=2010)
    print(f"  ✓ Parking costs deflated to 2010 dollars\n")
    
    # Step 11: Update monthly stalls with predicted costs
    print("▶ Step 11/13: Updating monthly stalls with predicted costs...")
    logging.info("="*80)
    logging.info("STEP 11: Updating monthly stalls with predicted costs")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = update_monthly_stalls_with_predicted_costs(maz)
    print(f"  ✓ Monthly stalls updated\n")
    
    # Step 11: Update parkarea classification with predicted costs (parkarea 3)
    print("▶ Step 12/13: Updating parkarea classifications...")
    logging.info("="*80)
    logging.info("STEP 12: Updating parkarea classifications")
    logging.info("="*80)
    with redirect_stdout_to_logger():
        maz = update_parkarea_with_predicted_costs(maz)
    print(f"  ✓ Parkarea classifications updated\n")
    
    # Step 12: Write final output
    print("▶ Step 13/13: Writing final output...")
    logging.info("="*80)
    logging.info("STEP 13: Writing final output")
    logging.info("="*80)
    
    # Clean up any duplicate TAZ_NODE columns in maz before creating output
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
    print(f"  See {log_file} for detailed processing log")
    
    return maz


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """
    Command-line interface for the land use pipeline.
    
    Returns:
        GeoDataFrame: Complete MAZ land use dataset
    """
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
        validate_parking=args.validate_parking,
        compare_parking_models=args.compare_parking_models
    )
    
    print(f"\nPipeline execution complete!")
    
    return maz


if __name__ == "__main__":
    main()
