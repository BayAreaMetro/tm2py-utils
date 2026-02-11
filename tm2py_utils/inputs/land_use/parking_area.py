"""
Parking Area Classification Module - Local Moran's I

This module assigns parkarea codes to MAZ zones based on downtown employment concentration
patterns within each place_name. Uses Local Moran's I analysis to identify
statistically significant employment clusters.

Architecture (Stage 1 - this module):
- **parkarea = 1**: Core downtown area (High-High LISA cluster)
- **parkarea = 2**: Within 1/4 mile of downtown core
- **parkarea = 0**: Unassigned (temporary - will be assigned to 3 or 4 in Stage 2)

Stage 2 assignments (by land_use_pipeline.update_parkarea_with_predicted_costs):
- **parkarea = 3**: Paid parking (has observed or predicted costs)
- **parkarea = 4**: Free parking / no parking cost

Methodology:
1. Filter places by minimum downtown employment threshold (default: 100 jobs)
2. Calculate Local Moran's I statistic for each MAZ using Queen contiguity weights
3. Identify significant High-High clusters (HH quadrant with p-value <= 0.05)
4. Extract largest High-High cluster by employment as downtown (parkarea=1)
5. Assign parkarea=2 to MAZs within 1/4 mile buffer of parkarea=1

Local Moran's I Analysis:
- **Statistical significance**: Downtown defined by spatial autocorrelation, not arbitrary thresholds
- **Adaptive boundaries**: Responds to each city's unique employment distribution
- **LISA quadrants**: Identifies High-High, High-Low, Low-High, Low-Low patterns
- **Interpretable**: I-statistic shows local correlation strength, p-value shows confidence

LISA Categories:
- **HH (High-High)**: High employment surrounded by high employment (downtown core)
- **HL (High-Low)**: High employment surrounded by low employment (isolated centers)
- **LH (Low-High)**: Low employment surrounded by high employment (edge zones)
- **LL (Low-Low)**: Low employment surrounded by low employment (suburban/rural)
- **NS (Not Significant)**: No significant spatial autocorrelation

Dependencies:
- libpysal: Spatial weights matrix construction
- esda: Local Moran's I statistics

Entry Point:
- merge_parking_area(): Main function called from parking_prep.py
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx
import warnings
import sys
import os
from contextlib import contextmanager
from shapely.ops import unary_union
from libpysal.weights import Queen
from esda.moran import Moran_Local


@contextmanager
def suppress_output():
    """Context manager to suppress stdout and stderr."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        # Flush any pending output first
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Redirect to devnull
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        # Close devnull files
        if sys.stdout != old_stdout:
            sys.stdout.close()
        if sys.stderr != old_stderr:
            sys.stderr.close()
        
        # Restore original streams
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def assign_parkarea_by_local_morans_i(mazs_gdf, emp_col='downtown_emp', 
                                       significance_level=0.05,
                                       max_area_percentile=0.90, min_cluster_mazs=5,
                                       min_cluster_employment=100):
    """
    Assign parkarea=1 using Local Moran's I analysis.
    
    Identifies statistically significant High-High clusters of downtown employment.
    Downtown = largest High-High cluster by employment where high employment is 
    surrounded by high employment neighbors.
    
    Args:
        mazs_gdf: GeoDataFrame of MAZs within a single place
        emp_col: Employment column name (default: 'downtown_emp')
        significance_level: P-value threshold for significance (default: 0.05)
        max_area_percentile: Exclude MAZs larger than this percentile (default: 0.90 = top 10%)
        min_cluster_mazs: Minimum MAZs required for valid cluster (default: 5)
        min_cluster_employment: Minimum employment required for valid cluster (default: 100)
    
    Returns:
        tuple: (parkarea_mask, moran_categories, metrics_dict)
            - parkarea_mask: Boolean Series for parkarea=1 assignment
            - moran_categories: Series with LISA categories ('HH', 'HL', 'LH', 'LL', 'NS')
            - metrics_dict: Dict with Local Moran's I statistics and cluster info
    """
    # Calculate area and filter out very large MAZs (top 10% by default)
    if 'area_m2' not in mazs_gdf.columns:
        mazs_gdf = mazs_gdf.copy()
        mazs_gdf['area_m2'] = mazs_gdf.geometry.area
    
    area_threshold = mazs_gdf['area_m2'].quantile(max_area_percentile)
    n_before_filter = len(mazs_gdf)
    mazs_gdf = mazs_gdf[mazs_gdf['area_m2'] <= area_threshold].copy()
    n_filtered = n_before_filter - len(mazs_gdf)
    
    # Check for minimum MAZ count (Local Moran's I requires at least 3 observations)
    if len(mazs_gdf) < 3:
        # Return empty results for places with too few MAZs
        category_counts = {'HH': 0, 'HL': 0, 'LH': 0, 'LL': 0, 'NS': len(mazs_gdf)}
        return pd.Series(False, index=mazs_gdf.index), pd.Series('NS', index=mazs_gdf.index), {
            'n_high_high': 0,
            'n_high_low': 0,
            'n_downtown_candidate': 0,
            'n_components': 0,
            'largest_component_size': 0,
            'mean_moran_i': 0,
            'max_moran_i': 0,
            'lisa_counts': category_counts
        }
    
    # Build spatial weights matrix using Queen contiguity (suppress warnings about islands/disconnected components)
    with warnings.catch_warnings(), suppress_output():
        warnings.filterwarnings('ignore', category=UserWarning)
        warnings.filterwarnings('ignore')  # Suppress all warnings during this operation
        w = Queen.from_dataframe(mazs_gdf, use_index=True, silence_warnings=True)
    
    # Calculate Local Moran's I statistic for each MAZ (suppress division warnings)
    employment_values = mazs_gdf[emp_col].values
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning)
        moran_local = Moran_Local(employment_values, w, transformation='r', permutations=999)
    
    # Map LISA quadrants to categories
    # q=1: HH (High-High), q=2: LH (Low-High), q=3: LL (Low-Low), q=4: HL (High-Low)
    lisa_categories = pd.Series('NS', index=mazs_gdf.index)
    
    # Only assign category if statistically significant
    is_significant = moran_local.p_sim <= significance_level
    
    quadrant_map = {1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}
    for idx, (quad, sig) in enumerate(zip(moran_local.q, is_significant)):
        if sig:
            lisa_categories.iloc[idx] = quadrant_map.get(quad, 'NS')
    
    # Identify High-High and High-Low clusters
    # HH: high employment surrounded by high employment (downtown core)
    # HL: high employment surrounded by low employment (edge of downtown)
    is_high_high = (moran_local.q == 1) & (moran_local.p_sim <= significance_level)
    is_high_low = (moran_local.q == 4) & (moran_local.p_sim <= significance_level)
    
    # Combine HH and HL for downtown cluster identification
    is_downtown_candidate = is_high_high | is_high_low
    
    # Count total HH and HL MAZs found
    n_high_high = is_high_high.sum()
    n_high_low = is_high_low.sum()
    n_downtown_candidate = is_downtown_candidate.sum()
    
    # Count all LISA categories
    category_counts = lisa_categories.value_counts().to_dict()
    
    if n_downtown_candidate == 0:
        # No significant HH or HL clusters found
        return pd.Series(False, index=mazs_gdf.index), lisa_categories, {
            'n_high_high': 0,
            'n_high_low': 0,
            'n_downtown_candidate': 0,
            'n_components': 0,
            'largest_component_size': 0,
            'mean_moran_i': 0,
            'max_moran_i': 0,
            'lisa_counts': category_counts
        }
    
    # Build graph of HH+HL MAZs to find contiguous clusters
    downtown_indices = mazs_gdf[is_downtown_candidate].index.tolist()
    G = nx.Graph()
    
    for idx in downtown_indices:
        G.add_node(idx)
    
    # Add edges between spatially adjacent HH/HL MAZs
    for idx1 in downtown_indices:
        for idx2 in downtown_indices:
            if idx1 < idx2:
                geom1 = mazs_gdf.loc[idx1, 'geometry']
                geom2 = mazs_gdf.loc[idx2, 'geometry']
                if geom1.touches(geom2) or geom1.intersects(geom2):
                    G.add_edge(idx1, idx2)
    
    # Find all connected components
    components = list(nx.connected_components(G))
    n_components = len(components)
    
    if n_components == 0:
        return pd.Series(False, index=mazs_gdf.index), lisa_categories, {
            'n_high_high': n_high_high,
            'n_high_low': n_high_low,
            'n_downtown_candidate': n_downtown_candidate,
            'n_components': 0,
            'n_valid_components': 0,
            'n_filtered_by_area': n_filtered,
            'largest_component_size': 0,
            'mean_moran_i': moran_local.Is[is_downtown_candidate].mean(),
            'max_moran_i': moran_local.Is[is_downtown_candidate].max(),
            'lisa_counts': category_counts
        }
    
    # Filter components by size constraints
    valid_components = []
    for comp in components:
        comp_list = list(comp)
        comp_size = len(comp_list)
        comp_emp = mazs_gdf.loc[comp_list, emp_col].sum()
        
        if comp_size >= min_cluster_mazs and comp_emp >= min_cluster_employment:
            valid_components.append((comp, comp_size, comp_emp))
    
    if not valid_components:
        # No components meet minimum size criteria
        return pd.Series(False, index=mazs_gdf.index), lisa_categories, {
            'n_high_high': n_high_high,
            'n_high_low': n_high_low,
            'n_downtown_candidate': n_downtown_candidate,
            'n_components': n_components,
            'n_valid_components': 0,
            'n_filtered_by_area': n_filtered,
            'largest_component_size': 0,
            'mean_moran_i': moran_local.Is[is_downtown_candidate].mean(),
            'max_moran_i': moran_local.Is[is_downtown_candidate].max(),
            'lisa_counts': category_counts
        }
    
    # Select largest valid component by total employment (ONLY ONE PER PLACE)
    largest_component, largest_size, largest_emp = max(valid_components, 
                                                       key=lambda x: x[2])
    largest_component = largest_component
    
    # Fill holes: include MAZs completely surrounded by the cluster
    # This captures isolated MAZs that should logically be part of downtown
    cluster_indices = set(largest_component)
    n_filled = 0
    
    for idx in mazs_gdf.index:
        if idx not in cluster_indices:
            # Check if this MAZ is completely surrounded by cluster MAZs
            geom = mazs_gdf.loc[idx, 'geometry']
            neighbors = []
            
            # Find all touching/adjacent MAZs
            for cluster_idx in cluster_indices:
                cluster_geom = mazs_gdf.loc[cluster_idx, 'geometry']
                if geom.touches(cluster_geom) or geom.intersects(cluster_geom):
                    neighbors.append(cluster_idx)
            
            # If this MAZ has neighbors, check if ALL its spatial neighbors are in cluster
            if neighbors:
                all_neighbors_in_cluster = True
                for other_idx in mazs_gdf.index:
                    if other_idx != idx and other_idx not in cluster_indices:
                        other_geom = mazs_gdf.loc[other_idx, 'geometry']
                        if geom.touches(other_geom) or geom.intersects(other_geom):
                            # Found a neighbor NOT in cluster
                            all_neighbors_in_cluster = False
                            break
                
                # If all neighbors are in cluster, add this MAZ
                if all_neighbors_in_cluster:
                    cluster_indices.add(idx)
                    n_filled += 1
    
    # Spatial containment: iteratively include MAZs within convex hull of cluster
    # Run until no new MAZs are added (convex hull stops expanding)
    n_spatially_contained = 0
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        new_indices_added = []
        
        # Create convex hull of current cluster geometries
        cluster_union = mazs_gdf.loc[list(cluster_indices), 'geometry'].unary_union
        cluster_convex_hull = cluster_union.convex_hull
        
        # Check each non-cluster MAZ for containment within convex hull
        for idx in mazs_gdf.index:
            if idx not in cluster_indices:
                maz_geom = mazs_gdf.loc[idx, 'geometry']
                maz_centroid = maz_geom.centroid
                
                # Check if MAZ centroid falls within cluster convex hull
                if cluster_convex_hull.contains(maz_centroid):
                    new_indices_added.append(idx)
        
        # Add newly contained MAZs to cluster
        if new_indices_added:
            cluster_indices.update(new_indices_added)
            n_spatially_contained += len(new_indices_added)
        else:
            # No new MAZs added, convergence reached
            break
    
    # Create mask for parkarea=1
    parkarea_mask = pd.Series(False, index=mazs_gdf.index)
    parkarea_mask[list(cluster_indices)] = True
    
    # Collect metrics
    metrics = {
        'n_high_high': n_high_high,
        'n_high_low': n_high_low,
        'n_downtown_candidate': n_downtown_candidate,
        'n_components': n_components,
        'n_valid_components': len(valid_components),
        'n_filtered_by_area': n_filtered,
        'n_filled_holes': n_filled,
        'n_spatially_contained': n_spatially_contained,
        'containment_iterations': iteration,
        'area_threshold_m2': area_threshold,
        'largest_component_size': len(cluster_indices),
        'mean_moran_i': moran_local.Is[is_downtown_candidate].mean(),
        'max_moran_i': moran_local.Is[is_downtown_candidate].max(),
        'mean_p_value': moran_local.p_sim[is_downtown_candidate].mean(),
        'lisa_counts': category_counts
    }
    
    return parkarea_mask, lisa_categories, metrics


def cat_names(cat):
    """Helper function to return full LISA category names."""
    names = {
        'HH': 'High-High',
        'HL': 'High-Low',
        'LH': 'Low-High',
        'LL': 'Low-Low',
        'NS': 'Not Significant'
    }
    return names.get(cat, 'Unknown')


def merge_parking_area(maz, min_place_employment=100, 
                       significance_level=0.05,
                       max_area_percentile=0.90, min_cluster_mazs=5,
                       min_cluster_employment=100, emp_col='downtown_emp'):
    """
    Merge parking area classifications to MAZ data - main entry point called from parking_prep.py.
    
    Assigns parkarea field to MAZ zones using Local Moran's I analysis.
    Identifies statistically significant High-High employment clusters as downtown areas.
    
    Only processes places with total downtown_emp >= min_place_employment.
    
    This function follows the pattern of merge_scraped_cost, merge_published_cost, etc.
    in parking_prep.py workflow.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have place_name, employment sectors, geometry, ACRES)
        min_place_employment: Minimum total downtown_emp for place to have parkarea=1 (default: 100)
        significance_level: P-value threshold for LISA significance (default: 0.05)
        emp_col: Employment column name for weighting (default: 'downtown_emp')
    
    Returns:
        GeoDataFrame: maz with parkarea and moran_category columns added
    """
    # Ensure downtown_emp exists by calling add_density_features if needed
    if emp_col not in maz.columns:
        print(f"  {emp_col} not found. Calculating density features first...")
        from parking_estimation import add_density_features
        maz = add_density_features(maz)
    
    # Call the core assignment function
    maz = assign_parking_areas(maz, min_place_employment, significance_level,
                              max_area_percentile, min_cluster_mazs, min_cluster_employment, emp_col)
    
    return maz


def assign_parking_areas(maz, min_place_employment=100, 
                         significance_level=0.05,
                         max_area_percentile=0.90, min_cluster_mazs=5,
                         min_cluster_employment=100, emp_col='downtown_emp'):
    """
    Assign parkarea field to MAZ zones using Local Moran's I analysis.
    
    Identifies statistically significant High-High employment clusters as downtown areas.
    
    Only processes places with total downtown_emp >= min_place_employment.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have place_name, downtown_emp, geometry, ACRES)
        min_place_employment: Minimum total downtown_emp for place to have parkarea=1 (default: 100)
        significance_level: P-value threshold for LISA significance (default: 0.05)
        emp_col: Employment column name for weighting (default: 'downtown_emp')
    
    Returns:
        GeoDataFrame: maz with parkarea and moran_category columns added
    """
    print("\n" + "="*80)
    print("PARKING AREA ASSIGNMENT - LOCAL MORAN'S I ANALYSIS")
    print("="*80)
    print(f"Minimum place employment: {min_place_employment:,} {emp_col}")
    print(f"Significance level: {significance_level} (p-value threshold)")
    print(f"LISA categories: HH (High-High), HL (High-Low), LH (Low-High), LL (Low-Low), NS (Not Significant)")
    
    # Ensure downtown_emp exists
    if emp_col not in maz.columns:
        raise ValueError(f"Column '{emp_col}' not found in MAZ data. Run add_density_features() first.")
    
    # Initialize parkarea and moran_category columns
    maz['parkarea'] = 0
    maz['moran_category'] = 'NS'
    
    # Filter to MAZs with place_name (cities only)
    maz_in_cities = maz[maz['place_name'].notna()].copy()
    
    print(f"\nTotal MAZs: {len(maz):,}")
    print(f"MAZs in cities (have place_name): {len(maz_in_cities):,}")
    
    # Calculate total employment by place
    place_employment = maz_in_cities.groupby('place_name')[emp_col].sum().sort_values(ascending=False)
    
    # Filter to places meeting minimum threshold
    eligible_places = place_employment[place_employment >= min_place_employment]
    
    print(f"\nPlaces with >={min_place_employment:,} {emp_col}: {len(eligible_places)}")
    print(f"Total {emp_col} in eligible places: {eligible_places.sum():,.0f} ({eligible_places.sum()/maz_in_cities[emp_col].sum()*100:.1f}% of all)")
    
    if len(eligible_places) == 0:
        print("\nWARNING: No places meet minimum employment threshold. All parkarea = 0.")
        return maz
    
    # Process each eligible place
    place_results = []
    
    print(f"\n{'='*80}")
    print("PROCESSING ELIGIBLE PLACES")
    print(f"{'='*80}\n")
    
    for place_name in eligible_places.index:
        place_mazs = maz_in_cities[maz_in_cities['place_name'] == place_name].copy()
        place_emp = place_employment[place_name]
        
        print(f"  {place_name} ({len(place_mazs):,} MAZs, {place_emp:,.0f} {emp_col})")
        
        # Assign parkarea using Local Moran's I analysis
        parkarea_mask, moran_categories, moran_metrics = assign_parkarea_by_local_morans_i(
            place_mazs, emp_col, significance_level,
            max_area_percentile, min_cluster_mazs, min_cluster_employment
        )
        
        # Reset parkarea for this place, then update with selected cluster only
        maz.loc[place_mazs.index, 'parkarea'] = 0
        maz.loc[parkarea_mask[parkarea_mask].index, 'parkarea'] = 1
        
        # Update main dataframe with all LISA categories
        maz.loc[moran_categories.index, 'moran_category'] = moran_categories
        
        # Count downtown MAZs and employment
        parkarea_mazs = place_mazs.loc[parkarea_mask[parkarea_mask].index]
        n_downtown_mazs = len(parkarea_mazs)
        downtown_employment = parkarea_mazs[emp_col].sum() if n_downtown_mazs > 0 else 0
        
        # Report LISA category counts
        lisa_counts = moran_metrics.get('lisa_counts', {})
        lisa_str = ', '.join([f"{cat}={count}" for cat, count in sorted(lisa_counts.items())])
        
        # Report
        print(f"    LISA categories: {lisa_str}")
        print(f"    High-High MAZs: {moran_metrics['n_high_high']}, High-Low MAZs: {moran_metrics.get('n_high_low', 0)}, Total downtown candidates: {moran_metrics.get('n_downtown_candidate', 0)}")
        print(f"    Filtered by area: {moran_metrics.get('n_filtered_by_area', 0)} MAZs (>{moran_metrics.get('area_threshold_m2', 0):,.0f} m²)")
        print(f"    Connected HH+HL clusters: {moran_metrics['n_components']} total, {moran_metrics.get('n_valid_components', 0)} valid (≥{min_cluster_mazs} MAZs, ≥{min_cluster_employment} emp)")
        print(f"    Holes filled: {moran_metrics.get('n_filled_holes', 0)} MAZs completely surrounded by cluster")
        print(f"    Perimeter additions: {moran_metrics.get('n_perimeter_added', 0)} MAZs with >90% perimeter touching cluster")
        print(f"    Downtown (parkarea=1): {n_downtown_mazs} MAZs, "
              f"{downtown_employment:,.0f} emp, "
              f"mean_I={moran_metrics.get('mean_moran_i', 0):.3f}")
        
        # Store place results
        place_results.append({
            'place_name': place_name,
            'county_name': place_mazs['county_name'].iloc[0] if 'county_name' in place_mazs.columns else None,
            'total_mazs': len(place_mazs),
            'total_employment': place_emp,
            'n_high_high': moran_metrics['n_high_high'],
            'n_high_low': moran_metrics.get('n_high_low', 0),
            'n_downtown_candidate': moran_metrics.get('n_downtown_candidate', 0),
            'n_hh_clusters': moran_metrics['n_components'],
            'mean_moran_i': moran_metrics.get('mean_moran_i', 0),
            'max_moran_i': moran_metrics.get('max_moran_i', 0),
            'n_mazs_downtown': n_downtown_mazs,
            'downtown_employment': downtown_employment,
            **{f'lisa_{cat}': lisa_counts.get(cat, 0) for cat in ['HH', 'HL', 'LH', 'LL', 'NS']}
        })
    
    # Create results dataframe
    df_results = pd.DataFrame(place_results)
    
    # Print summary statistics
    print(f"\n{'='*80}")
    print("LOCAL MORAN'S I SUMMARY")
    print(f"{'='*80}\n")
    
    print("Statistics Across All Eligible Places:\n")
    print(f"{'Metric':<40} {'Mean':>12} {'Median':>12} {'Max':>12}")
    print("─" * 80)
    
    # LISA metrics
    print(f"{'High-High MAZs per place':<40} {df_results['n_high_high'].mean():>12.1f} {df_results['n_high_high'].median():>12.0f} {df_results['n_high_high'].max():>12.0f}")
    print(f"{'High-Low MAZs per place':<40} {df_results['n_high_low'].mean():>12.1f} {df_results['n_high_low'].median():>12.0f} {df_results['n_high_low'].max():>12.0f}")
    print(f"{'Downtown candidates (HH+HL) per place':<40} {df_results['n_downtown_candidate'].mean():>12.1f} {df_results['n_downtown_candidate'].median():>12.0f} {df_results['n_downtown_candidate'].max():>12.0f}")
    print(f"{'HH+HL clusters per place':<40} {df_results['n_hh_clusters'].mean():>12.1f} {df_results['n_hh_clusters'].median():>12.0f} {df_results['n_hh_clusters'].max():>12.0f}")
    print(f"{"Mean Local Moran's I":<40} {df_results['mean_moran_i'].mean():>12.3f} {df_results['mean_moran_i'].median():>12.3f} {df_results['mean_moran_i'].max():>12.3f}")
    
    print()
    
    # Downtown metrics
    print(f"{'Downtown MAZs per place':<40} {df_results['n_mazs_downtown'].mean():>12.1f} {df_results['n_mazs_downtown'].median():>12.0f} {df_results['n_mazs_downtown'].max():>12.0f}")
    print(f"{'Downtown employment per place':<40} {df_results['downtown_employment'].mean():>12,.0f} {df_results['downtown_employment'].median():>12,.0f} {df_results['downtown_employment'].max():>12,.0f}")
    
    # Calculate employment capture percentage
    df_results['emp_capture_pct'] = (df_results['downtown_employment'] / df_results['total_employment']) * 100
    print(f"{'Employment captured (%)':<40} {df_results['emp_capture_pct'].mean():>12.1f} {df_results['emp_capture_pct'].median():>12.1f} {df_results['emp_capture_pct'].max():>12.1f}")
    
    print("─" * 80)
    
    # Print LISA category distribution across all places
    print(f"\n{'='*80}")
    print("LISA CATEGORY DISTRIBUTION ACROSS ALL PLACES")
    print(f"{'='*80}\n")
    
    total_lisa_counts = {cat: df_results[f'lisa_{cat}'].sum() for cat in ['HH', 'HL', 'LH', 'LL', 'NS']}
    total_categorized = sum(total_lisa_counts.values())
    
    for cat in ['HH', 'HL', 'LH', 'LL', 'NS']:
        count = total_lisa_counts[cat]
        pct = (count / total_categorized * 100) if total_categorized > 0 else 0
        print(f"  {cat} ({cat_names(cat):<20}): {count:>8,} MAZs ({pct:>5.1f}%)")
    
    print(f"\n  Total categorized MAZs: {total_categorized:,}")
    
    # Print top 10 largest downtowns by employment
    print(f"\n{'='*80}")
    print("TOP 10 LARGEST DOWNTOWNS BY EMPLOYMENT")
    print(f"{'='*80}\n")
    
    df_top = df_results.nlargest(10, 'total_employment')
    
    print(f"{'Place':<25} {'County':<15} {'Total Emp':>12} {'DT MAZs':>10} {'DT Emp':>12} {'Moran I':>10}")
    print("─" * 100)
    
    for _, row in df_top.iterrows():
        place = row['place_name'][:24]
        county = (row['county_name'][:14] if pd.notna(row['county_name']) else 'N/A')
        total_emp = row['total_employment']
        dt_mazs = row['n_mazs_downtown']
        dt_emp = row['downtown_employment']
        moran_i = row['mean_moran_i']
        
        print(f"{place:<25} {county:<15} {total_emp:>12,.0f} {int(dt_mazs):>10} {dt_emp:>12,.0f} {moran_i:>10.3f}")
    
    # Assign parkarea=2: MAZs within 1/4 mile of parkarea=1
    print(f"\n{'='*80}")
    print("ASSIGNING PARKAREA=2 (WITHIN 1/4 MILE OF DOWNTOWN)")
    print(f"{'='*80}\n")
    
    QUARTER_MILE_METERS = 402.336  # 1/4 mile = 402.336 meters
    
    # Get all parkarea=1 MAZs and create buffer
    downtown_mazs = maz[maz['parkarea'] == 1].copy()
    
    if len(downtown_mazs) > 0:
        # Create union of all downtown geometries and buffer by 1/4 mile
        downtown_union = downtown_mazs.geometry.unary_union
        downtown_buffer = downtown_union.buffer(QUARTER_MILE_METERS)
        
        # Find MAZs whose centroids fall within buffer (excluding parkarea=1)
        maz_centroids = maz.geometry.centroid
        within_buffer = maz_centroids.within(downtown_buffer)
        not_downtown = maz['parkarea'] != 1
        
        # Assign parkarea=2
        parkarea_2_mask = within_buffer & not_downtown
        maz.loc[parkarea_2_mask, 'parkarea'] = 2
        
        n_parkarea_2 = parkarea_2_mask.sum()
        print(f"  Assigned parkarea=2 to {n_parkarea_2:,} MAZs within 1/4 mile of downtown")
    else:
        print("  No parkarea=1 MAZs found, skipping parkarea=2 assignment")
        n_parkarea_2 = 0
    
    # Print Stage 1 summary (parkarea 0, 1, 2 only)
    # Note: parkarea=3 and parkarea=4 are assigned in Stage 2 by
    # land_use_pipeline.update_parkarea_with_predicted_costs() after cost estimation
    print(f"\n{'='*80}")
    print("STAGE 1 PARKING AREA CLASSIFICATION COMPLETE")
    print(f"{'='*80}\n")
    
    # Stage 1 counts
    n_parkarea_0 = (maz['parkarea'] == 0).sum()
    n_parkarea_1 = (maz['parkarea'] == 1).sum()
    n_parkarea_2 = (maz['parkarea'] == 2).sum()
    total_mazs = len(maz)
    
    print(f"{'Category':<40} {'MAZs':>12} {'Percent':>10}")
    print("─" * 65)
    print(f"{'parkarea=0 (Temporary - to be assigned)':<40} {n_parkarea_0:>12,} {n_parkarea_0/total_mazs*100:>9.1f}%")
    print(f"{'parkarea=1 (Downtown core)':<40} {n_parkarea_1:>12,} {n_parkarea_1/total_mazs*100:>9.1f}%")
    print(f"{'parkarea=2 (Within 1/4 mi of downtown)':<40} {n_parkarea_2:>12,} {n_parkarea_2/total_mazs*100:>9.1f}%")
    print("─" * 65)
    print(f"{'Total':<40} {total_mazs:>12,} {100.0:>9.1f}%")
    print(f"\n  NOTE: parkarea=0 will be assigned to parkarea=3 (paid parking) or parkarea=4 (other)")
    print(f"  after cost estimation to include predicted parking costs. Final output has no parkarea=0.")
    
    print(f"\n  Places with parkarea=1 (downtown): {(df_results['n_mazs_downtown'] > 0).sum()} of {len(eligible_places)}")
    
    # Note: Not storing df_results as attribute to avoid GeoDataFrame serialization issues
    # Place-level statistics are printed above and can be exported separately if needed
    
    return maz
