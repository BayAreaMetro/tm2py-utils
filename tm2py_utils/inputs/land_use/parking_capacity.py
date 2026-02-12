from pathlib import Path
import pandas as pd
import geopandas as gpd
import numpy as np
import os
import sys

# Import job_counts module to get MAZ employment data
from job_counts import get_jobs_maz

# Import configuration and utilities
from setup import (
    PARKING_RAW_DATA_DIR,
    ANALYSIS_CRS,
    SQUARE_METERS_PER_ACRE,
    ensure_directories
)
from utils import load_maz_shp, get_output_filename


def overlay_maz_blockgroups(maz, parking_capacity):
    """
    Spatially overlay MAZ and block group geometries to create MAZ-BlockGroup mapping.
    
    Parameters:
        maz (GeoDataFrame): MAZ polygons with geometry
        parking_capacity (GeoDataFrame): Block group parking data with geometry
        
    Returns:
        GeoDataFrame: MAZ-BlockGroup intersections with calculated areas
    """
    print(f"Performing spatial overlay of MAZ and block groups...")
    print(f"  Number of MAZs: {len(maz):,}")
    print(f"  Number of block groups: {len(parking_capacity):,}")
    
    # Spatial overlay to find intersections
    overlay = gpd.overlay(maz, parking_capacity, how='intersection')
    print(f"  Number of MAZ-BlockGroup intersections: {len(overlay):,}")
    
    # Calculate intersection area in acres
    overlay['maz_acres'] = overlay.geometry.area / SQUARE_METERS_PER_ACRE
    
    # Check for MAZs spanning multiple block groups
    mazs_multiple_bg = overlay.groupby('MAZ_NODE')['blkgrpid'].nunique()
    mazs_spanning = (mazs_multiple_bg > 1).sum()
    if mazs_spanning > 0:
        print(f"  ⚠ Warning: {mazs_spanning:,} MAZs span multiple block groups")
        print(f"    (This is handled by summing allocated parking across contributing block groups)")
    
    return overlay


def calculate_allocation_weights(overlay_df, jobs_maz):
    """
    Calculate allocation weights for distributing block group parking to MAZs.
    Uses employment-based weights with area fallback for off-street non-residential,
    and pure area weights for on-street parking.
    
    Parameters:
        overlay_df (GeoDataFrame): MAZ-BlockGroup intersections with areas
        jobs_maz (DataFrame): MAZ employment data with emp_total
        
    Returns:
        DataFrame: overlay_df with allocation weights added
    """
    print(f"Calculating allocation weights...")
    
    # Ensure consistent data types for merge (jobs_maz has string MAZ_NODE)
    overlay_df['MAZ_NODE'] = overlay_df['MAZ_NODE'].astype(str)
    overlay_df['TAZ_NODE'] = overlay_df['TAZ_NODE'].astype(str)
    
    # Merge employment data
    weights_df = overlay_df.merge(
        jobs_maz[['MAZ_NODE', 'TAZ_NODE', 'emp_total']], 
        on='MAZ_NODE', 
        how='left',
        suffixes=('', '_emp')
    )
    
    # Fill any missing employment with 0
    weights_df['emp_total'] = weights_df['emp_total'].fillna(0)
    
    # Calculate block group totals
    weights_df['bg_total_acres'] = weights_df.groupby('blkgrpid')['maz_acres'].transform('sum')
    weights_df['bg_total_emp'] = weights_df.groupby('blkgrpid')['emp_total'].transform('sum')
    
    # Calculate raw shares
    weights_df['area_share'] = np.where(
        weights_df['bg_total_acres'] > 0,
        weights_df['maz_acres'] / weights_df['bg_total_acres'],
        0
    )
    
    weights_df['emp_share'] = np.where(
        weights_df['bg_total_emp'] > 0,
        weights_df['emp_total'] / weights_df['bg_total_emp'],
        0
    )
    
    # Create hybrid weight for off-street non-residential:
    # Use employment share when available, area share as fallback
    weights_df['weight_offnres'] = np.where(
        weights_df['bg_total_emp'] > 0,
        weights_df['emp_share'],
        weights_df['area_share']
    )
    
    # Use pure area weight for on-street parking
    weights_df['weight_onall'] = weights_df['area_share']
    
    # Report on fallback usage
    zero_emp_bgs = (weights_df['bg_total_emp'] == 0).sum()
    if zero_emp_bgs > 0:
        unique_zero_emp_bgs = weights_df[weights_df['bg_total_emp'] == 0]['blkgrpid'].nunique()
        print(f"  {unique_zero_emp_bgs:,} block groups have zero employment - using area fallback")
    
    return weights_df


def allocate_parking_to_maz(weights_df, maz_gdf):
    """
    Normalize weights within each block group and allocate parking to MAZ level.
    
    Parameters:
        weights_df (DataFrame): MAZ-BlockGroup data with raw weights and parking values
        maz_gdf (GeoDataFrame): MAZ polygons with geometry
        
    Returns:
        GeoDataFrame: MAZ-level parking allocation with MAZ_NODE, TAZ_NODE, emp_total, on_all, off_nres, geometry
    """
    print(f"Normalizing weights and allocating parking to MAZ level...")
    
    # Normalize weights to sum to 1.0 within each block group
    weights_df['weight_offnres_norm'] = (
        weights_df['weight_offnres'] / 
        weights_df.groupby('blkgrpid')['weight_offnres'].transform('sum')
    )
    
    weights_df['weight_onall_norm'] = (
        weights_df['weight_onall'] / 
        weights_df.groupby('blkgrpid')['weight_onall'].transform('sum')
    )
    
    # Apply weights to allocate parking
    weights_df['off_nres_allocated'] = weights_df['off_nres'] * weights_df['weight_offnres_norm']
    weights_df['on_all_allocated'] = weights_df['on_all'] * weights_df['weight_onall_norm']
    
    # Aggregate to MAZ level (summing across multiple block groups if MAZ spans them)
    parking_maz = weights_df.groupby(['MAZ_NODE', 'TAZ_NODE'], as_index=False).agg({
        'off_nres_allocated': 'sum',
        'on_all_allocated': 'sum',
        'emp_total': 'first'  # Employment is constant per MAZ, take first value
    })
    
    # Rename to final column names
    parking_maz = parking_maz.rename(columns={
        'off_nres_allocated': 'off_nres',
        'on_all_allocated': 'on_all'
    })
    
    # Fill any NaN with 0
    parking_maz = parking_maz.fillna(0)
    
    # Clip any negative values to 0 (safety check)
    parking_maz['off_nres'] = parking_maz['off_nres'].clip(lower=0)
    parking_maz['on_all'] = parking_maz['on_all'].clip(lower=0)
    
    # Merge with MAZ geometry to create GeoDataFrame
    # Ensure MAZ_NODE types match
    maz_gdf_copy = maz_gdf.copy()
    maz_gdf_copy['MAZ_NODE'] = maz_gdf_copy['MAZ_NODE'].astype(str)
    parking_maz = parking_maz.merge(
        maz_gdf_copy[['MAZ_NODE', 'geometry']], 
        on='MAZ_NODE', 
        how='left'
    )
    parking_maz = gpd.GeoDataFrame(parking_maz, geometry='geometry', crs=ANALYSIS_CRS)
    
    # Reorder columns for clarity
    column_order = ['MAZ_NODE', 'TAZ_NODE', 'emp_total', 'off_nres', 'on_all', 'geometry']
    parking_maz = parking_maz[column_order]
    
    print(f"  Total MAZs with allocated parking: {len(parking_maz):,}")
    
    return parking_maz


def get_parking_maz(write=False, use_maz_orig=False):
    """
    Main function to allocate block group parking capacity to MAZ level.
    Uses hybrid allocation: employment-weighted for off-street non-residential,
    area-weighted for on-street parking.
    
    Parameters:
        write (bool): If True, writes output to interim cache as GeoPackage
        use_maz_orig (bool): If True, uses MAZ v2.2 shapefile. Otherwise uses version from setup.
        
    Returns:
        DataFrame: MAZ-level parking with columns [MAZ_NODE, TAZ_NODE, off_nres, on_all]
    """
    ensure_directories()
    
    print(f"\n{'='*60}")
    print(f"Allocating Block Group Parking Capacity to MAZ Level")
    print(f"{'='*60}\n")
    
    # Load data
    print(f"Loading input data...")
    parking_capacity = gpd.read_file(
        PARKING_RAW_DATA_DIR / "2123-Dataset" / "parking_density_Employee_Capita" / "parking_density_Employee_Capita.shp"
    ).to_crs(ANALYSIS_CRS)
    parking_capacity = parking_capacity[["blkgrpid", "on_all", "off_nres", "geometry"]]
    
    # Clean negative values (data quality issue in source)
    neg_on_all = (parking_capacity['on_all'] < 0).sum()
    neg_off_nres = (parking_capacity['off_nres'] < 0).sum()
    if neg_on_all > 0 or neg_off_nres > 0:
        print(f"  ⚠ Warning: Found negative parking values in source data:")
        if neg_on_all > 0:
            print(f"    on_all: {neg_on_all:,} block groups with negative values")
        if neg_off_nres > 0:
            print(f"    off_nres: {neg_off_nres:,} block groups with negative values")
        print(f"  Clipping negative values to 0...")
        parking_capacity['on_all'] = parking_capacity['on_all'].clip(lower=0)
        parking_capacity['off_nres'] = parking_capacity['off_nres'].clip(lower=0)
    
    print(f"  Loaded {len(parking_capacity):,} block groups with parking data")
    
    # Load MAZ shapefile
    maz = load_maz_shp(use_maz_orig=use_maz_orig).to_crs(ANALYSIS_CRS)
    print(f"  Loaded {len(maz):,} MAZ polygons")
    
    # Load employment data
    print(f"\nLoading MAZ employment data...")
    jobs_maz = get_jobs_maz(write=False)
    print(f"  Loaded employment for {len(jobs_maz):,} MAZs")
    
    # Spatial overlay
    overlay_df = overlay_maz_blockgroups(maz, parking_capacity)
    
    # Calculate weights
    weights_df = calculate_allocation_weights(overlay_df, jobs_maz)
    
    # Allocate parking
    parking_maz = allocate_parking_to_maz(weights_df, maz)
    
    # Validation
    print(f"\nValidating results...")
    original_total_offnres = parking_capacity['off_nres'].sum()
    original_total_onall = parking_capacity['on_all'].sum()
    allocated_total_offnres = parking_maz['off_nres'].sum()
    allocated_total_onall = parking_maz['on_all'].sum()
    
    print(f"  Original block group totals:")
    print(f"    off_nres: {original_total_offnres:,.0f}")
    print(f"    on_all: {original_total_onall:,.0f}")
    print(f"  Allocated MAZ totals:")
    print(f"    off_nres: {allocated_total_offnres:,.0f}")
    print(f"    on_all: {allocated_total_onall:,.0f}")
    
    # Check conservation (within 0.1% tolerance)
    offnres_diff_pct = abs(allocated_total_offnres - original_total_offnres) / original_total_offnres * 100
    onall_diff_pct = abs(allocated_total_onall - original_total_onall) / original_total_onall * 100
    
    if offnres_diff_pct < 0.1 and onall_diff_pct < 0.1:
        print(f"  ✓ Conservation check passed (< 0.1% difference)")
    else:
        print(f"  ⚠ Warning: Conservation check failed")
        print(f"    off_nres difference: {offnres_diff_pct:.2f}%")
        print(f"    on_all difference: {onall_diff_pct:.2f}%")
    
    # Write output if requested
    if write:
        OUT_FILE = get_output_filename("parking_capacity", extension="gpkg", spatial=True)
        print(f"\nWriting parking MAZ data to: {OUT_FILE}")
        parking_maz.to_file(OUT_FILE, driver="GPKG", index=False)
    
    print(f"\n{'='*60}")
    print(f"Parking allocation complete!")
    print(f"{'='*60}\n")
    
    return parking_maz


def main():
    """
    Execute script directly with optional command-line flags.
    Usage:
        python parking_capacity.py [--write] [--use-maz-orig]
    """
    use_maz_orig = "--use-maz-orig" in sys.argv
    write = "--write" in sys.argv
    
    parking_maz = get_parking_maz(write=write, use_maz_orig=use_maz_orig)
    print(f"\nParking capacity processing complete.")
    print(f"Total MAZ records: {len(parking_maz)}")
    print(f"Total off-street parking: {parking_maz['off_nres'].sum():,.0f}")
    print(f"Total on-street parking: {parking_maz['on_all'].sum():,.0f}")


if __name__ == "__main__":
    main()