#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PopSim TM2 Crosswalk Creator

Creates complete geographic crosswalk for PopulationSim TM2 including:
1. Basic MAZ-TAZ-PUMA-COUNTY mapping from shapefiles (area-based PUMA assignment)
2. Enhanced crosswalk with block/block group mappings for census data integration

This script combines the functionality of create_tm2_crosswalk.py and build_complete_crosswalk.py
into a single standalone script that doesn't rely on tm2_control_utils or unified_tm2_config.

PIPELINE INTEGRATION:
The script automatically detects and writes to the PopulationSim pipeline directory when available.

SIMPLE USAGE (auto-detects pipeline directory):
    python popsim_tm2_crosswalk_creator.py \\
        --maz-shapefile "C:/path/to/mazs_TM2_2_5.shp" \\
        --puma-shapefile "C:/path/to/tl_2022_06_puma20.shp" \\
        --county-shapefile "C:/path/to/Counties.shp" \\
        --blocks-file "C:/path/to/blocks_mazs_tazs_2.5.csv" \\
        --verbose

If you're in a populationsim repository, it will automatically write to:
    output_2023/populationsim_working_dir/data/

If not in a populationsim repo, it falls back to:
    ./crosswalks/

CUSTOM OUTPUT DIRECTORY:
    python popsim_tm2_crosswalk_creator.py \\
        --maz-shapefile "..." \\
        --puma-shapefile "..." \\
        --county-shapefile "..." \\
        --blocks-file "..." \\
        --output-dir "my_custom_directory" \\
        --verbose

The pipeline expects these specific filenames:
- geo_cross_walk_tm2_maz.csv (basic crosswalk)
- geo_cross_walk_tm2_block10.csv (enhanced crosswalk)

EXAMPLE USAGE:
    python popsim_tm2_crosswalk_creator.py \\
        --maz-shapefile "C:/path/to/mazs_TM2_2_5.shp" \\
        --puma-shapefile "C:/path/to/tl_2022_06_puma20.shp" \\
        --county-shapefile "C:/path/to/Counties.shp" \\
        --blocks-file "C:/path/to/blocks_mazs_tazs_2.5.csv" \\
        --output-dir "crosswalks" \\
        --verbose

    # For tm2py-utils repository:
    python popsim_tm2_crosswalk_creator.py \\
        --maz-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/shapefiles/mazs_TM2_2_5.shp" \\
        --puma-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/shapefiles/tl_2022_06_puma20.shp" \\
        --county-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/shapefiles/Counties.shp" \\
        --blocks-file "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/blocks_mazs_tazs_2.5.csv" \\
        --output-dir "crosswalks" \\
        --verbose

INPUTS:
- MAZ shapefile with TAZ relationships
- PUMA shapefile (US Census TIGER/Line)
- County shapefile (California counties)
- Blocks CSV file with MAZ assignments

OUTPUTS - TWO CROSSWALKS CREATED:

1. BASIC CROSSWALK (geo_cross_walk_tm2_maz.csv):
   - Length: Number of MAZs (~39,600 records)
   - Structure: One row per MAZ with TAZ, PUMA, and County assignments
   - Purpose: Core geographic mapping for PopulationSim control generation
   - Columns: MAZ_NODE, TAZ_NODE, PUMA, COUNTY, county_name
   - Used by: Control generation scripts that need MAZ-level geography mapping

2. ENHANCED CROSSWALK (geo_cross_walk_tm2_block10.csv):
   - Length: Number of census blocks (~109,000 records)
   - Structure: One row per census block with complete geographic hierarchy
   - Purpose: Detailed census data integration and block-level analysis
   - Columns: MAZ_NODE, TAZ_NODE, PUMA, COUNTY, county_name, GEOID_block, 
             GEOID_block_group, GEOID_tract, GEOID_county
   - Used by: Census data processing, demographic analysis, validation

WHY TWO CROSSWALKS?
- Basic: Efficient MAZ-level operations for control generation and model setup
- Enhanced: Detailed block-level mapping for census data aggregation and validation
- Different granularities serve different analytical needs in the modeling pipeline

USAGE IN THE TM2 MODELING PIPELINE:

1. BASIC CROSSWALK (geo_cross_walk_tm2_maz.csv) is used by:
   - Control generation scripts (create_baseyear_controls_23_tm2.py)
     * MAZ household totals aggregation (functions that read 'main_crosswalk')
     * TAZ-level control summarization 
     * County-level scaling and validation
   - Seed population creation (create_seed_population_tm2_refactored.py)
     * PUMA validation and filtering for PUMS data
     * Geographic assignment of synthetic households
   - Pipeline processing (tm2_pipeline.py)
     * TAZ-PUMA mapping validation and fixes
     * Multi-PUMA assignment resolution
   - Post-processing (postprocess_recode.py)
     * Geographic recoding of synthesized population
     * Summary statistics by geographic level

2. ENHANCED CROSSWALK (geo_cross_walk_tm2_block10.csv) is used by:
   - Control generation scripts (create_baseyear_controls_23_tm2.py)
     * Census block group data aggregation (functions that read 'enhanced_crosswalk')
     * Detailed demographic data processing from ACS
     * Block-level population and housing unit totals
   - Census data integration workflows
     * American Community Survey data mapping to model geography
     * Decennial Census block data aggregation to MAZ level
     * Validation of synthetic population against census benchmarks

The basic crosswalk provides the core geographic relationships needed for most modeling 
operations, while the enhanced crosswalk enables detailed census data integration and 
fine-grained validation at the block level.

DATA SOURCES:
- MAZ/TAZ Shapefiles: TM2py-utils repository
- PUMA Shapefiles: US Census TIGER/Line files  
- County Shapefiles: California Open Data Portal
- Blocks file: TM2py-utils blocks with MAZ assignments
"""

import argparse
import geopandas as gpd
import numpy as np
import pandas as pd
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# California Bay Area County FIPS codes (1-9 county system)
BAY_AREA_COUNTIES = {
    1: {'name': 'San Francisco', 'fips': '075'},
    2: {'name': 'San Mateo', 'fips': '081'},
    3: {'name': 'Santa Clara', 'fips': '085'},
    4: {'name': 'Alameda', 'fips': '001'},
    5: {'name': 'Contra Costa', 'fips': '013'},
    6: {'name': 'Solano', 'fips': '095'},
    7: {'name': 'Napa', 'fips': '055'},
    8: {'name': 'Sonoma', 'fips': '097'},
    9: {'name': 'Marin', 'fips': '041'}
}

def add_aggregate_geography_columns(table_df):
    """
    Given a table with column GEOID_block, creates columns for GEOID_[county,tract,block group]
    """
    if "GEOID_block" in table_df.columns:
        # Ensure block GEOIDs are properly zero-padded to 15 digits
        table_df["GEOID_block"] = table_df["GEOID_block"].astype(str).str.zfill(15)
        table_df["GEOID_county"] = table_df["GEOID_block"].str[:5]
        table_df["GEOID_tract"] = table_df["GEOID_block"].str[:11]
        table_df["GEOID_block group"] = table_df["GEOID_block"].str[:12]

def create_basic_crosswalk(maz_shapefile, puma_shapefile, county_shapefile, output_file, verbose=True):
    """
    Create basic TM2 crosswalk with area-based PUMA assignment
    """
    
    if verbose:
        print("=" * 60)
        print("TM2 BASIC CROSSWALK CREATION")
        print("=" * 60)
        print("Area-based TAZ-PUMA assignment for maximum accuracy")
    
    # Load MAZ shapefile (contains TAZ relationships)
    if verbose:
        print(f"\\nStep 1: Loading MAZ shapefile...")
        print(f"  File: {maz_shapefile}")
    
    if not maz_shapefile.exists():
        print(f"ERROR: MAZ shapefile not found: {maz_shapefile}")
        return None
        
    try:
        maz_gdf = gpd.read_file(maz_shapefile, engine='pyogrio')
        if verbose:
            print(f"  Loaded {len(maz_gdf):,} MAZ zones")
            print(f"  CRS: {maz_gdf.crs}")
        
        # Identify MAZ and TAZ columns (updated for TM2.5 naming)
        maz_col = None
        taz_col = None
        county_col = None
        
        for col in maz_gdf.columns:
            if col.upper() in ['MAZ_NODE', 'MAZ', 'MAZ_ID', 'MAZ_ID_']:
                maz_col = col
            elif col.upper() in ['TAZ_NODE', 'TAZ', 'TAZ_ID', 'TAZ1454']:
                taz_col = col
            elif col.upper() in ['COUNTYFP10', 'COUNTY', 'CO_FIPS', 'COUNTY_FIPS']:
                county_col = col
                
        if not maz_col or not taz_col:
            print(f"ERROR: Could not identify MAZ and TAZ columns in {list(maz_gdf.columns)}")
            return None
            
        if verbose:
            print(f"  MAZ column: {maz_col}")
            print(f"  TAZ column: {taz_col}")
            print(f"  County column: {county_col}")
        
    except Exception as e:
        print(f"ERROR loading MAZ shapefile: {e}")
        return None
    
    # Load PUMA shapefile
    if verbose:
        print(f"\\nStep 2: Loading PUMA shapefile...")
        print(f"  File: {puma_shapefile}")
    
    if not puma_shapefile.exists():
        print(f"ERROR: PUMA shapefile not found: {puma_shapefile}")
        return None
        
    try:
        puma_gdf = gpd.read_file(puma_shapefile, engine='pyogrio')
        if verbose:
            print(f"  Loaded {len(puma_gdf):,} PUMA zones")
            print(f"  CRS: {puma_gdf.crs}")
        
        # Identify PUMA column
        puma_col = None
        for col in puma_gdf.columns:
            if col.upper() in ['PUMA', 'PUMACE10', 'PUMACE20', 'PUMA5CE']:
                puma_col = col
                break
                
        if not puma_col:
            print(f"ERROR: Could not identify PUMA column in {list(puma_gdf.columns)}")
            return None
            
        if verbose:
            print(f"  PUMA column: {puma_col}")
            
        # Reproject if necessary
        if maz_gdf.crs != puma_gdf.crs:
            if verbose:
                print(f"  Reprojecting PUMA from {puma_gdf.crs} to {maz_gdf.crs}")
            puma_gdf = puma_gdf.to_crs(maz_gdf.crs)
            
    except Exception as e:
        print(f"ERROR loading PUMA shapefile: {e}")
        return None
    
    # Load county shapefile
    if verbose:
        print(f"\\nStep 3: Loading County shapefile...")
        print(f"  File: {county_shapefile}")
        
    try:
        county_gdf = gpd.read_file(county_shapefile, engine='pyogrio')
        if verbose:
            print(f"  Loaded {len(county_gdf):,} counties")
            print(f"  CRS: {county_gdf.crs}")
        
        # Filter to Bay Area counties only (using FIPS codes)
        bay_area_fips = [info['fips'] for info in BAY_AREA_COUNTIES.values()]  # Keep as 3-digit codes
        bay_area_names = [info['name'] for info in BAY_AREA_COUNTIES.values()]
        
        # Try different possible FIPS column names
        fips_col = None
        for col in county_gdf.columns:
            if col.upper() in ['FIPS', 'COUNTYFP', 'CNTY_FIPS', 'COUNTY_FIPS', 'COUNTY_FIP', 'GEOID']:
                if county_gdf[col].astype(str).str.len().iloc[0] >= 3:  # Should be at least 3-5 digits
                    fips_col = col
                    break
                    
        if not fips_col:
            print(f"ERROR: Could not identify county FIPS column in {list(county_gdf.columns)}")
            return None
            
        # Filter to Bay Area counties (both FIPS and name to avoid conflicts)
        county_gdf['fips_clean'] = county_gdf[fips_col].astype(str).str.zfill(3)  # 3-digit format
        county_gdf_filtered = county_gdf[
            (county_gdf['fips_clean'].isin(bay_area_fips)) & 
            (county_gdf['CountyName'].isin(bay_area_names))
        ].copy()
        
        if verbose:
            print(f"  FIPS column: {fips_col}")
            print(f"  Filtered to {len(county_gdf_filtered)} Bay Area counties")
            print(f"  Bay Area FIPS: {sorted(county_gdf_filtered['fips_clean'].unique())}")
        
        # Reproject if necessary
        if maz_gdf.crs != county_gdf_filtered.crs:
            if verbose:
                print(f"  Reprojecting County from {county_gdf_filtered.crs} to {maz_gdf.crs}")
            county_gdf_filtered = county_gdf_filtered.to_crs(maz_gdf.crs)
            
    except Exception as e:
        print(f"ERROR loading county shapefile: {e}")
        return None
    
    # Step 4: Create TAZ centroids and assign to PUMAs
    if verbose:
        print(f"\\nStep 4: Assigning TAZs to PUMAs (area-based)...")
    
    # Group MAZs by TAZ and union geometries
    taz_geom = maz_gdf.dissolve(by=taz_col)
    
    if verbose:
        print(f"  Created {len(taz_geom)} TAZ geometries from {len(maz_gdf)} MAZs")
    
    # Spatial join TAZs to PUMAs (area-based)
    taz_puma_join = gpd.sjoin(taz_geom.reset_index(), puma_gdf[[puma_col, 'geometry']], 
                              how='left', predicate='intersects')
    
    if verbose:
        print(f"  Initial TAZ-PUMA intersections: {len(taz_puma_join)}")
    
    # For TAZs that intersect multiple PUMAs, assign to the PUMA with largest overlap
    taz_puma_areas = []
    for taz_id in taz_puma_join[taz_col].unique():
        taz_geom_single = taz_geom.loc[taz_id]
        intersecting_pumas = taz_puma_join[taz_puma_join[taz_col] == taz_id]
        
        max_area = 0
        best_puma = None
        
        for _, puma_row in intersecting_pumas.iterrows():
            puma_geom = puma_gdf[puma_gdf[puma_col] == puma_row[puma_col]].geometry.iloc[0]
            try:
                intersection_area = taz_geom_single.geometry.intersection(puma_geom).area
                if intersection_area > max_area:
                    max_area = intersection_area
                    best_puma = puma_row[puma_col]
            except:
                continue
        
        if best_puma:
            taz_puma_areas.append({taz_col: taz_id, 'PUMA': best_puma})
    
    taz_puma_df = pd.DataFrame(taz_puma_areas)
    
    if verbose:
        print(f"  Final TAZ-PUMA assignments: {len(taz_puma_df)}")
        print(f"  Unique PUMAs assigned: {taz_puma_df['PUMA'].nunique()}")
    
    # Step 5: Assign MAZs to counties using centroids
    if verbose:
        print(f"\\nStep 5: Assigning MAZs to counties (centroid-based)...")
    
    # Calculate MAZ centroids
    maz_centroids = maz_gdf.copy()
    maz_centroids['geometry'] = maz_centroids.geometry.centroid
    
    # Spatial join MAZ centroids to counties
    maz_county_join = gpd.sjoin(maz_centroids[[maz_col, 'geometry']], 
                               county_gdf_filtered[['fips_clean', 'geometry']], 
                               how='left', predicate='within')
    
    # For MAZs that failed centroid-based assignment, try using original COUNTYFP10 from MAZ shapefile
    missing_counties = maz_county_join['fips_clean'].isna()
    if missing_counties.sum() > 0:
        if verbose:
            print(f"  {missing_counties.sum()} MAZs failed centroid assignment, using MAZ shapefile county data...")
        
        # Create mapping from MAZ shapefile county codes to our 3-digit FIPS format
        maz_county_fallback = maz_gdf.loc[maz_gdf[maz_col].isin(
            maz_county_join.loc[missing_counties, maz_col]
        ), [maz_col, 'COUNTYFP10']].copy()
        
        # Convert MAZ shapefile county codes to 3-digit format
        maz_county_fallback['fips_clean'] = maz_county_fallback['COUNTYFP10'].astype(str).str.zfill(5).str[-3:]
        
        # Only keep counties that are in our Bay Area list
        bay_area_fips = [info['fips'] for info in BAY_AREA_COUNTIES.values()]
        maz_county_fallback = maz_county_fallback[maz_county_fallback['fips_clean'].isin(bay_area_fips)]
        
        # Update the failed assignments
        for _, row in maz_county_fallback.iterrows():
            mask = (maz_county_join[maz_col] == row[maz_col]) & maz_county_join['fips_clean'].isna()
            maz_county_join.loc[mask, 'fips_clean'] = row['fips_clean']
    
    if verbose:
        print(f"  MAZ-County assignments: {len(maz_county_join)}")
        missing_counties_final = maz_county_join['fips_clean'].isna().sum()
        if missing_counties_final > 0:
            print(f"  WARNING: {missing_counties_final} MAZs could not be assigned to counties")
        else:
            print(f"  SUCCESS: All MAZs assigned to counties")
    
    # Step 6: Build the basic crosswalk
    if verbose:
        print(f"\\nStep 6: Building basic crosswalk...")
    
    # Start with MAZ-TAZ relationship
    crosswalk = maz_gdf[[maz_col, taz_col]].copy()
    
    # Add PUMA assignments
    crosswalk = crosswalk.merge(taz_puma_df, on=taz_col, how='left')
    
    # Add county assignments
    maz_county_map = maz_county_join[[maz_col, 'fips_clean']].copy()
    maz_county_map.rename(columns={'fips_clean': 'COUNTYFP'}, inplace=True)
    crosswalk = crosswalk.merge(maz_county_map, on=maz_col, how='left')
    
    # Map to 1-9 county system (using 3-digit FIPS codes)
    fips_to_county = {info['fips']: county_id for county_id, info in BAY_AREA_COUNTIES.items()}
    crosswalk['COUNTY'] = crosswalk['COUNTYFP'].map(fips_to_county)
    
    # Add county names
    county_to_name = {county_id: info['name'] for county_id, info in BAY_AREA_COUNTIES.items()}
    crosswalk['county_name'] = crosswalk['COUNTY'].map(county_to_name)
    
    # Standardize column names for consistency
    if maz_col != 'MAZ_NODE':
        crosswalk = crosswalk.rename(columns={maz_col: 'MAZ_NODE'})
    if taz_col != 'TAZ_NODE':
        crosswalk = crosswalk.rename(columns={taz_col: 'TAZ_NODE'})
    
    # Clean up and reorder columns
    final_cols = ['MAZ_NODE', 'TAZ_NODE', 'PUMA', 'COUNTY', 'county_name']
    crosswalk = crosswalk[final_cols].copy()
    
    # Remove rows with missing critical data
    initial_count = len(crosswalk)
    crosswalk = crosswalk.dropna(subset=['PUMA', 'COUNTY'])
    final_count = len(crosswalk)
    
    if verbose:
        print(f"  Basic crosswalk created: {final_count:,} records")
        if initial_count != final_count:
            print(f"  Dropped {initial_count - final_count} records with missing data")
        print(f"  MAZs: {crosswalk['MAZ_NODE'].nunique()}")
        print(f"  TAZs: {crosswalk['TAZ_NODE'].nunique()}")
        print(f"  PUMAs: {crosswalk['PUMA'].nunique()}")
        print(f"  Counties: {crosswalk['COUNTY'].nunique()}")
    
    # Save basic crosswalk
    crosswalk.to_csv(output_file, index=False)
    if verbose:
        print(f"  Saved basic crosswalk to: {output_file}")
    
    return crosswalk

def enhance_crosswalk_with_blocks(basic_crosswalk, blocks_file, enhanced_output_file, verbose=True):
    """
    Enhance the basic crosswalk with block/block group mappings for census data integration
    """
    
    if verbose:
        print("\\n" + "=" * 60)
        print("ENHANCING CROSSWALK WITH BLOCK MAPPINGS")
        print("=" * 60)
    
    # Load blocks file
    if verbose:
        print(f"\\nStep 1: Loading blocks file...")
        print(f"  File: {blocks_file}")
    
    if not blocks_file.exists():
        print(f"ERROR: Blocks file not found: {blocks_file}")
        return None
        
    try:
        blocks_df = pd.read_csv(blocks_file)
        if verbose:
            print(f"  Loaded {len(blocks_df):,} block records")
            print(f"  Columns: {list(blocks_df.columns)}")
        
        # Identify block GEOID and MAZ columns
        geoid_col = None
        maz_col = None
        
        for col in blocks_df.columns:
            if 'geoid' in col.lower() or 'block' in col.lower():
                if blocks_df[col].astype(str).str.len().iloc[0] >= 14:  # Block GEOIDs should be 14-15 digits
                    geoid_col = col
            elif col.upper() in ['MAZ_NODE', 'MAZ', 'MAZ_ID']:
                maz_col = col
        
        if not geoid_col or not maz_col:
            print(f"ERROR: Could not identify GEOID or MAZ columns in blocks file")
            print(f"  Available columns: {list(blocks_df.columns)}")
            return None
            
        if verbose:
            print(f"  Block GEOID column: {geoid_col}")
            print(f"  MAZ column: {maz_col}")
        
        # Ensure consistent column naming
        blocks_df = blocks_df.rename(columns={
            geoid_col: 'GEOID_block',
            maz_col: 'MAZ_NODE'
        })
        
    except Exception as e:
        print(f"ERROR loading blocks file: {e}")
        return None
    
    # Step 2: Create aggregate geography columns
    if verbose:
        print(f"\\nStep 2: Creating aggregate geography columns...")
    
    add_aggregate_geography_columns(blocks_df)
    
    if verbose:
        print(f"  Block groups: {blocks_df['GEOID_block group'].nunique():,}")
        print(f"  Tracts: {blocks_df['GEOID_tract'].nunique():,}")
        print(f"  Counties: {blocks_df['GEOID_county'].nunique():,}")
    
    # Step 3: Create block group to TAZ mapping
    if verbose:
        print(f"\\nStep 3: Creating block group to TAZ mapping...")
    
    # Get block to MAZ to TAZ mapping
    block_maz_taz = blocks_df[['GEOID_block', 'GEOID_block group', 'GEOID_tract', 'GEOID_county', 'MAZ_NODE']].merge(
        basic_crosswalk[['MAZ_NODE', 'TAZ_NODE', 'PUMA', 'COUNTY', 'county_name']], 
        on='MAZ_NODE', 
        how='left'
    )
    
    # For block groups that span multiple TAZs, assign to TAZ with most blocks
    bg_taz_counts = block_maz_taz.groupby(['GEOID_block group', 'TAZ_NODE']).size().reset_index(name='block_count')
    dominant_taz = bg_taz_counts.loc[bg_taz_counts.groupby('GEOID_block group')['block_count'].idxmax()]
    
    if verbose:
        print(f"  Block group-TAZ relationships: {len(bg_taz_counts):,}")
        print(f"  Unique block groups: {dominant_taz['GEOID_block group'].nunique():,}")
        multi_taz_bgs = len(bg_taz_counts) - len(dominant_taz)
        if multi_taz_bgs > 0:
            print(f"  Block groups spanning multiple TAZs: {multi_taz_bgs:,}")
    
    # Step 4: Build enhanced crosswalk
    if verbose:
        print(f"\\nStep 4: Building enhanced crosswalk...")
    
    # Create the enhanced crosswalk with all geographic levels
    enhanced_crosswalk = block_maz_taz[['MAZ_NODE', 'TAZ_NODE', 'PUMA', 'COUNTY', 'county_name', 
                                       'GEOID_block', 'GEOID_block group', 'GEOID_tract', 'GEOID_county']].copy()
    
    # Remove duplicates and sort
    enhanced_crosswalk = enhanced_crosswalk.drop_duplicates().sort_values(['MAZ_NODE'])
    
    if verbose:
        print(f"  Enhanced crosswalk created: {len(enhanced_crosswalk):,} records")
        print(f"  MAZs: {enhanced_crosswalk['MAZ_NODE'].nunique():,}")
        print(f"  TAZs: {enhanced_crosswalk['TAZ_NODE'].nunique():,}")
        print(f"  Block groups: {enhanced_crosswalk['GEOID_block group'].nunique():,}")
        print(f"  Blocks: {enhanced_crosswalk['GEOID_block'].nunique():,}")
    
    # Step 5: Save enhanced crosswalk
    enhanced_crosswalk.to_csv(enhanced_output_file, index=False)
    if verbose:
        print(f"  Saved enhanced crosswalk to: {enhanced_output_file}")
    
    # Step 6: Create validation summary
    if verbose:
        print(f"\\nStep 5: Creating validation summary...")
    
    # Block group summary
    bg_summary = enhanced_crosswalk.groupby(['GEOID_block group', 'TAZ_NODE']).agg({
        'MAZ_NODE': 'count',
        'COUNTY': 'first',
        'county_name': 'first',
        'PUMA': 'first'
    }).reset_index()
    
    bg_summary.rename(columns={'MAZ_NODE': 'num_mazs'}, inplace=True)
    
    summary_file = enhanced_output_file.parent / f"{enhanced_output_file.stem}_bg_summary.csv"
    bg_summary.to_csv(summary_file, index=False)
    
    if verbose:
        print(f"  Saved block group summary to: {summary_file}")
    
    return enhanced_crosswalk

def main():
    parser = argparse.ArgumentParser(description='Create PopSim TM2 crosswalk files')
    parser.add_argument('--maz-shapefile', type=Path, required=True,
                       help='Path to MAZ shapefile with TAZ relationships')
    parser.add_argument('--puma-shapefile', type=Path, required=True,
                       help='Path to PUMA shapefile')
    parser.add_argument('--county-shapefile', type=Path, required=True,
                       help='Path to California counties shapefile')
    parser.add_argument('--blocks-file', type=Path, required=True,
                       help='Path to blocks CSV file with MAZ assignments')
    parser.add_argument('--output-dir', type=Path, required=False,
                       help='Output directory for crosswalk files (default: auto-detect pipeline directory)')
    parser.add_argument('--basic-output', type=str, default='geo_cross_walk_tm2_maz.csv',
                       help='Filename for basic crosswalk (default: geo_cross_walk_tm2_maz.csv)')
    parser.add_argument('--enhanced-output', type=str, default='geo_cross_walk_tm2_block10.csv',
                       help='Filename for enhanced crosswalk (default: geo_cross_walk_tm2_block10.csv)')
    parser.add_argument('--verbose', action='store_true', default=True,
                       help='Print detailed progress information')
    
    args = parser.parse_args()
    
    # Determine output directory with smart defaults
    if args.output_dir is None:
        # First try to auto-detect pipeline directory
        potential_dirs = [
            Path.cwd() / "output_2023/populationsim_working_dir/data",  # If run from bay_area dir
            Path.cwd().parent / "bay_area/output_2023/populationsim_working_dir/data",  # If run from parent
            Path.cwd() / "bay_area/output_2023/populationsim_working_dir/data"  # If run from repo root
        ]
        
        pipeline_dir = None
        for potential_dir in potential_dirs:
            if potential_dir.exists():
                pipeline_dir = potential_dir
                break
        
        if pipeline_dir:
            args.output_dir = pipeline_dir
            print(f"🔗 AUTO-DETECTED: Writing to pipeline directory {args.output_dir}")
        else:
            # Fall back to crosswalks if no pipeline directory found
            args.output_dir = Path.cwd() / "crosswalks"
            print(f"📁 FALLBACK: Pipeline directory not found, using {args.output_dir}")
            print("    (To write to pipeline, ensure you're in a populationsim repo with output_2023/ directory)")
    else:
        print(f"📁 CUSTOM: Writing to specified directory {args.output_dir}")
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define output file paths
    basic_output_file = args.output_dir / args.basic_output
    enhanced_output_file = args.output_dir / args.enhanced_output
    
    print("TM2 POPSIM CROSSWALK CREATOR")
    print("=" * 50)
    print(f"MAZ Shapefile: {args.maz_shapefile}")
    print(f"PUMA Shapefile: {args.puma_shapefile}")
    print(f"County Shapefile: {args.county_shapefile}")
    print(f"Blocks File: {args.blocks_file}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Basic Output: {basic_output_file}")
    print(f"Enhanced Output: {enhanced_output_file}")
    
    # Create basic crosswalk
    print("\\n" + "=" * 50)
    print("CREATING BASIC CROSSWALK")
    print("=" * 50)
    
    basic_crosswalk = create_basic_crosswalk(
        args.maz_shapefile, 
        args.puma_shapefile,
        args.county_shapefile,
        basic_output_file, 
        args.verbose
    )
    
    if basic_crosswalk is None:
        print("ERROR: Failed to create basic crosswalk")
        return 1
    
    # Create enhanced crosswalk
    print("\\n" + "=" * 50)
    print("CREATING ENHANCED CROSSWALK")
    print("=" * 50)
    
    enhanced_crosswalk = enhance_crosswalk_with_blocks(
        basic_crosswalk,
        args.blocks_file,
        enhanced_output_file,
        args.verbose
    )
    
    if enhanced_crosswalk is None:
        print("ERROR: Failed to create enhanced crosswalk")
        return 1
    
    print("\\n" + "=" * 50)
    print("CROSSWALK CREATION COMPLETE")
    print("=" * 50)
    print(f"✅ Basic crosswalk: {basic_output_file}")
    print(f"✅ Enhanced crosswalk: {enhanced_output_file}")
    print(f"✅ Summary files created in: {args.output_dir}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


