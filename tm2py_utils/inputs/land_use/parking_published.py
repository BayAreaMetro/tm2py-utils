"""Process published parking meter cost data from SF, San Jose, and Oakland.

Spatially joins hourly parking meter costs (hparkcost) from city-published data to MAZ zones.
"""

import pandas as pd
import geopandas as gpd
import re
from pathlib import Path

RAW_DATA_DIR = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\raw_data\parking")
ANALYSIS_CRS = "EPSG:26910"


def extract_hourly_cost(config_string):
    """Extract hourly cost using regex - finds first $X.XX pattern."""
    if pd.isna(config_string):
        return 2.0  # Default to 2.0 for missing values
    
    # Match pattern like $2.00 or $ 2.00 or $1.50 or $2
    match = re.search(r'\$\s*(\d+\.?\d*)', str(config_string))
    if match:
        return float(match.group(1))
    return 2.0  # Default to 2.0 if no $ found


def published_cost():
    """
    Load and process published parking meter costs by MAZ.
    
    Spatially joins hourly parking costs from Oakland meters (points), 
    San Jose meters (points), and San Francisco meter districts (polygons) to MAZ zones.
    
    Returns:
        DataFrame: MAZ_NODE and hparkcost columns
    """
    from utils import load_maz_shp
    
    print("Loading published parking meter cost data...")
    
    # Load MAZ shapefile
    maz = load_maz_shp()
    
    # Load Oakland meters
    print("  Loading Oakland meters...")
    oak_meters = gpd.read_file(RAW_DATA_DIR / "City_of_Oakland_Parking_Meters_20260107.geojson")
    oak_meters['hparkcost'] = oak_meters['config__na'].apply(extract_hourly_cost)
    oak_meters = oak_meters[["hparkcost", "geometry"]]
    print(f"    Loaded {len(oak_meters):,} Oakland meters")
    
    # Load San Jose meters
    print("  Loading San Jose meters...")
    sj_meters = gpd.read_file(RAW_DATA_DIR / "Parking_Meters.geojson")
    sj_meters = sj_meters.rename(columns={"PARKINGRATE": "hparkcost"})
    sj_meters["hparkcost"] = sj_meters["hparkcost"].fillna(2.0).replace(0, 2.0)
    sj_meters = sj_meters[["hparkcost", "geometry"]]
    print(f"    Loaded {len(sj_meters):,} San Jose meters")
    
    # Load San Francisco meter districts
    print("  Loading San Francisco meter districts...")
    sf_rates = pd.read_csv(RAW_DATA_DIR / "January 2026 Parking Meter Rate Change Data.csv")
    sf_park_distr = gpd.read_file(RAW_DATA_DIR / "Parking_Management_Districts_20260203.geojson")
    
    # Average Final Rate by Parking Management District
    avg_rates = sf_rates.groupby('Parking Management District')['Final Rate'].mean().reset_index()
    avg_rates.columns = ['Parking Management District', 'hparkcost']
    
    # Join to sf_park_distr
    sf_park_distr = sf_park_distr.merge(
        avg_rates, 
        left_on='pm_district_name', 
        right_on='Parking Management District', 
        how='left'
    )
    sf_park_distr = sf_park_distr.drop(columns=['Parking Management District'])
    
    sf_meter_areas = sf_park_distr[["hparkcost", "geometry"]]
    sf_meter_areas = sf_meter_areas[~sf_meter_areas["hparkcost"].isnull()]
    print(f"    Loaded {len(sf_meter_areas):,} San Francisco meter districts")
    
    # Ensure CRS consistency
    print(f"  Converting all datasets to {ANALYSIS_CRS}...")
    oak_meters = oak_meters.to_crs(ANALYSIS_CRS)
    sj_meters = sj_meters.to_crs(ANALYSIS_CRS)
    sf_meter_areas = sf_meter_areas.to_crs(ANALYSIS_CRS)
    
    # Store original count for validation
    original_count = len(maz)
    
    # Spatial join: Oakland point meters to MAZ
    print("  Spatial join: Oakland meters to MAZ...")
    oak_joined = gpd.sjoin(maz, oak_meters, how="inner", predicate="intersects")
    oak_by_maz = oak_joined.groupby('MAZ_NODE')['hparkcost'].mean().reset_index()
    oak_by_maz.columns = ['MAZ_NODE', 'hparkcost_oak']
    print(f"    Oakland: {len(oak_by_maz):,} MAZs with parking meter costs")
    
    # Spatial join: San Jose point meters to MAZ
    print("  Spatial join: San Jose meters to MAZ...")
    sj_joined = gpd.sjoin(maz, sj_meters, how="inner", predicate="intersects")
    sj_by_maz = sj_joined.groupby('MAZ_NODE')['hparkcost'].mean().reset_index()
    sj_by_maz.columns = ['MAZ_NODE', 'hparkcost_sj']
    print(f"    San Jose: {len(sj_by_maz):,} MAZs with parking meter costs")
    
    # Spatial join: SF polygon meter areas to MAZ (50% area threshold)
    print("  Spatial join: San Francisco meter districts to MAZ (50% threshold)...")
    sf_overlay = gpd.overlay(maz, sf_meter_areas, how="intersection")
    
    # Calculate original MAZ areas
    maz_areas = maz.copy()
    maz_areas['maz_area'] = maz_areas.geometry.area
    
    # Calculate intersection areas and percentage
    sf_overlay['intersection_area'] = sf_overlay.geometry.area
    sf_overlay = sf_overlay.merge(
        maz_areas[['MAZ_NODE', 'maz_area']], 
        on='MAZ_NODE', 
        how='left'
    )
    sf_overlay['pct_of_maz'] = sf_overlay['intersection_area'] / sf_overlay['maz_area']
    
    # Filter for MAZs where intersection >= 50% of MAZ area
    sf_filtered = sf_overlay[sf_overlay['pct_of_maz'] >= 0.5].copy()
    sf_by_maz = sf_filtered.groupby('MAZ_NODE')['hparkcost'].mean().reset_index()
    sf_by_maz.columns = ['MAZ_NODE', 'hparkcost_sf']
    print(f"    San Francisco: {len(sf_by_maz):,} MAZs with parking meter costs")
    
    # Merge all sources back to complete MAZ set
    print("  Merging all sources to MAZ...")
    maz = maz.merge(oak_by_maz, on='MAZ_NODE', how='left')
    maz = maz.merge(sj_by_maz, on='MAZ_NODE', how='left')
    maz = maz.merge(sf_by_maz, on='MAZ_NODE', how='left')
    
    # Combine into single hparkcost column (coalesce across sources)
    # Since SF/SJ/OAK are geographically distinct, only one should have a value per MAZ
    maz['hparkcost'] = maz[['hparkcost_oak', 'hparkcost_sj', 'hparkcost_sf']].bfill(axis=1).iloc[:, 0]
    
    # Drop intermediate columns
    maz = maz.drop(columns=['hparkcost_oak', 'hparkcost_sj', 'hparkcost_sf'])
    
    # Validate no records were lost
    if len(maz) != original_count:
        print(f"  WARNING: Record count changed from {original_count:,} to {len(maz):,}")
    else:
        print(f"  ✓ All {original_count:,} MAZ records retained")
    
    # Report statistics
    mazs_with_hparkcost = maz['hparkcost'].notna().sum()
    mazs_without_hparkcost = maz['hparkcost'].isna().sum()
    print(f"  MAZs with hparkcost: {mazs_with_hparkcost:,}/{len(maz):,}")
    print(f"  MAZs without hparkcost: {mazs_without_hparkcost:,}/{len(maz):,}")
    
    if mazs_with_hparkcost > 0:
        print(f"  hparkcost range: ${maz['hparkcost'].min():.2f} - ${maz['hparkcost'].max():.2f}")
        print(f"  hparkcost mean: ${maz['hparkcost'].mean():.2f}")
    
    # Return just MAZ_NODE and hparkcost columns
    return maz[['MAZ_NODE', 'hparkcost']].copy()
